from typing import Any, Dict, List, Tuple
from shared.schemas.search import SearchResultItem
from shared.schemas.chat import CitationItem


class PackedContext:
    def __init__(
        self,
        context_string: str,
        citations: List[CitationItem],
        total_tokens: int,
    ):
        self.context_string = context_string
        self.citations = citations
        self.total_tokens = total_tokens


def pack_retrieval_context(
    results: List[SearchResultItem],
    max_tokens_budget: int = 6000,
) -> PackedContext:
    """
    Format search results into numbered context blocks for LLM synthesis.
    """
    if not results:
        return PackedContext(context_string="", citations=[], total_tokens=0)

    context_blocks = []
    citations: List[CitationItem] = []
    seen_citation_urls = set()
    current_tokens = 0
    citation_index = 1

    for i, item in enumerate(results, start=1):
        # Build heading breadcrumb
        breadcrumb = " › ".join([item.title] + item.heading_path) if item.heading_path else item.title
        
        block = (
            f"--- [Doc #{i}] ---\n"
            f"Title: {item.title}\n"
            f"URL: {item.url}\n"
            f"Breadcrumbs: {breadcrumb}\n"
            f"Content:\n{item.text}\n"
        )
        block_tokens = len(block) // 4
        if current_tokens + block_tokens > max_tokens_budget and context_blocks:
            break

        context_blocks.append(block)
        current_tokens += block_tokens

        # Deduplicate citations so identical URLs are not repeated as duplicate chips
        if item.url not in seen_citation_urls:
            seen_citation_urls.add(item.url)
            citations.append(
                CitationItem(
                    n=citation_index,
                    title=item.title,
                    url=item.url,
                    heading_path=item.heading_path,
                    last_updated=item.last_updated,
                    score=item.score,
                )
            )
            citation_index += 1

    context_str = "\n".join(context_blocks)
    return PackedContext(
        context_string=context_str,
        citations=citations,
        total_tokens=current_tokens,
    )
