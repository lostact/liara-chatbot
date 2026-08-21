import re
from typing import Any, Dict, List, Optional
from shared.text import detect_language
from app.pipeline.dedupe import compute_text_hash

# Approximate token estimator (1 token ~= 3.5 chars for mixed Persian/English)
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class RawChunk:
    def __init__(
        self,
        ordinal: int,
        heading_path: List[str],
        anchor: Optional[str],
        text: str,
        embed_text: str,
        text_hash: str,
        token_count: int,
        has_code: bool,
        code_langs: List[str],
        lang: str,
        service_tag: Optional[str],
    ):
        self.ordinal = ordinal
        self.heading_path = heading_path
        self.anchor = anchor
        self.text = text
        self.embed_text = embed_text
        self.text_hash = text_hash
        self.token_count = token_count
        self.has_code = has_code
        self.code_langs = code_langs
        self.lang = lang
        self.service_tag = service_tag


class MarkdownChunker:
    def __init__(
        self,
        target_tokens: int = 450,
        max_tokens: int = 900,
        overlap_tokens: int = 80,
    ):
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def chunk_document(
        self,
        doc_title: str,
        markdown: str,
        service_tag: Optional[str] = None,
        doc_lang: Optional[str] = None,
    ) -> List[RawChunk]:
        """
        Split markdown into heading-aware semantic chunks.
        """
        sections = self._split_by_headings(markdown)
        raw_chunks: List[RawChunk] = []
        ordinal = 0

        for heading_path, anchor, section_text in sections:
            section_chunks = self._split_section_text(section_text)
            
            for chunk_body in section_chunks:
                chunk_body = chunk_body.strip()
                if not chunk_body:
                    continue

                lang = doc_lang or detect_language(chunk_body)
                token_count = estimate_tokens(chunk_body)
                
                # Extract code langs
                code_matches = re.findall(r"```([a-zA-Z0-9_\-\+]+)?\n", chunk_body)
                has_code = bool(code_matches)
                code_langs = [m for m in code_matches if m]

                # Format contextual header
                breadcrumbs = " › ".join([doc_title] + heading_path) if heading_path else doc_title
                contextual_header = (
                    f"{breadcrumbs}\nservice: {service_tag or 'general'} | lang: {lang}\n\n"
                )
                embed_text = f"{contextual_header}{chunk_body}"
                text_hash = compute_text_hash(chunk_body)

                raw_chunks.append(
                    RawChunk(
                        ordinal=ordinal,
                        heading_path=heading_path,
                        anchor=anchor,
                        text=chunk_body,
                        embed_text=embed_text,
                        text_hash=text_hash,
                        token_count=token_count,
                        has_code=has_code,
                        code_langs=code_langs,
                        lang=lang,
                        service_tag=service_tag,
                    )
                )
                ordinal += 1

        return raw_chunks

    def _split_by_headings(self, markdown: str) -> List[tuple[List[str], Optional[str], str]]:
        """
        Splits markdown into sections by H1, H2, H3 headers.
        Returns tuples: (heading_path, anchor, section_text)
        """
        lines = markdown.splitlines(keepends=True)
        sections = []
        
        current_heading_path: List[str] = []
        current_anchor: Optional[str] = None
        current_lines: List[str] = []
        in_code_block = False

        heading_pattern = re.compile(r"^(#{1,3})\s+(.+)$")

        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith("```"):
                in_code_block = not in_code_block

            m = None if in_code_block else heading_pattern.match(stripped_line)
            if m:
                # Save previous section if non-empty
                if current_lines:
                    text = "".join(current_lines).strip()
                    # The MDX extractor keeps the HTML <title> as a short
                    # preamble before the first real heading. It is metadata,
                    # not an answerable chunk, so do not let it outrank the
                    # documentation body during retrieval.
                    is_title_only_preamble = not current_heading_path and text == doc_title.strip()
                    if text and not is_title_only_preamble:
                        sections.append((list(current_heading_path), current_anchor, text))
                    current_lines = []

                level = len(m.group(1))
                heading_title = m.group(2).strip()
                clean_anchor = re.sub(r"[^\w\s\u0600-\u06FF-]", "", heading_title).strip()
                clean_anchor = re.sub(r"[\s_]+", "-", clean_anchor).lower()

                # Adjust heading path based on level
                if level == 1:
                    current_heading_path = [heading_title]
                elif level == 2:
                    current_heading_path = current_heading_path[:1] + [heading_title]
                elif level == 3:
                    current_heading_path = current_heading_path[:2] + [heading_title]

                current_anchor = clean_anchor
                current_lines.append(line)
            else:
                current_lines.append(line)

        if current_lines:
            text = "".join(current_lines).strip()
            if text:
                sections.append((list(current_heading_path), current_anchor, text))

        if not sections:
            sections.append(([], None, markdown.strip()))

        return sections

    def _split_section_text(self, text: str) -> List[str]:
        """
        Splits a section text by paragraphs and code blocks, respecting max_tokens.
        """
        # Separate code blocks from normal text
        blocks = self._parse_blocks(text)
        
        chunks: List[str] = []
        current_chunk_parts: List[str] = []
        current_tokens = 0

        for block in blocks:
            b_tokens = estimate_tokens(block)

            if current_tokens + b_tokens > self.max_tokens and current_chunk_parts:
                chunks.append("\n\n".join(current_chunk_parts))
                current_chunk_parts = []
                current_tokens = 0

            current_chunk_parts.append(block)
            current_tokens += b_tokens

        if current_chunk_parts:
            chunks.append("\n\n".join(current_chunk_parts))

        return chunks

    def _parse_blocks(self, text: str) -> List[str]:
        """
        Splits text into paragraphs and fenced code blocks so code fences remain atomic.
        """
        pattern = re.compile(r"(```[\s\S]*?```)")
        parts = pattern.split(text)
        
        blocks: List[str] = []
        for part in parts:
            if not part.strip():
                continue
            if part.startswith("```"):
                blocks.append(part.strip())
            else:
                # Paragraph split
                paras = [p.strip() for p in re.split(r"\n\s*\n", part) if p.strip()]
                blocks.extend(paras)

        return blocks
