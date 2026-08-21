import re
from typing import Any, Dict, List, Tuple
import frontmatter
from shared.text import clean_display_text


def slugify_heading(heading: str) -> str:
    """
    Generate an anchor slug from a heading text.
    Preserves Persian characters, English letters, digits, and hyphens.
    """
    clean = re.sub(r"[^\w\s\u0600-\u06FF-]", "", heading).strip()
    slug = re.sub(r"[\s_]+", "-", clean)
    return slug.lower()


def transform_jsx_components(text: str) -> str:
    """
    Transform MDX/JSX components into markdown representation while extracting
    their text props and inner content for components like Callout, Tabs, Steps, Card.
    """
    # 1. Strip import and export statements (MDX)
    text = re.sub(r"^import\s+.*?;?$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^export\s+.*?;?$", "", text, flags=re.MULTILINE)

    # 2. Transform <Callout type="...">content</Callout> -> > **[type]** content
    def callout_sub(match):
        callout_type = match.group(1) or "info"
        content = match.group(2).strip()
        return f"\n> **{callout_type.upper()}**: {content}\n"

    text = re.sub(
        r"<Callout(?:\s+type=[\"'](.*?)[\"'])?[^>]*>([\s\S]*?)<\/Callout>",
        callout_sub,
        text,
    )

    # 3. Transform <Card title="..." href="...">description</Card> -> [title](href): description
    def card_sub(match):
        attrs = match.group(1)
        content = match.group(2).strip()
        title_m = re.search(r'title=[\'"](.*?)[\'"]', attrs)
        href_m = re.search(r'href=[\'"](.*?)[\'"]', attrs)
        title = title_m.group(1) if title_m else "Card"
        href = href_m.group(1) if href_m else ""
        if href:
            return f"\n- [{title}]({href}): {content}\n"
        return f"\n- **{title}**: {content}\n"

    text = re.sub(
        r"<Card([^>]*)>([\s\S]*?)<\/Card>",
        card_sub,
        text,
    )

    # Liara docs store most examples in JSX Highlight components, for example
    # <Highlight className="python">{`...`}</Highlight>. Convert these to
    # real Markdown fences before heading extraction and chunking. Otherwise
    # lines such as "# other codes ..." inside a code sample are interpreted
    # as document headings and split the useful answer across unrelated chunks.
    def highlight_sub(match):
        attrs = match.group(1)
        body = match.group(2)
        language_match = re.search(r'className=["\']([^"\']+)["\']', attrs)
        language = language_match.group(1).strip() if language_match else ""
        template_match = re.search(r"\{\s*`([\s\S]*?)`\s*\}", body)
        code = template_match.group(1) if template_match else body.strip()
        fence_language = language.split()[-1] if language else ""
        return f"\n```{fence_language}\n{code.strip()}\n```\n"

    text = re.sub(
        r"<Highlight([^>]*)>([\s\S]*?)<\/Highlight>",
        highlight_sub,
        text,
    )

    # 4. Transform <Tab label="..."> / <Tabs> -> Tab labels and body
    text = re.sub(r"<Tabs[^>]*>", "\n", text)
    text = re.sub(r"<\/Tabs>", "\n", text)

    def tab_sub(match):
        label = match.group(1) or "Tab"
        content = match.group(2).strip()
        return f"\n#### {label}\n{content}\n"

    text = re.sub(
        r"<Tab(?:\s+label=[\"'](.*?)[\"'])?[^>]*>([\s\S]*?)<\/Tab>",
        tab_sub,
        text,
    )

    # 5. Transform <Steps> -> numbered list wrapper
    text = re.sub(r"<Steps[^>]*>", "\n", text)
    text = re.sub(r"<\/Steps>", "\n", text)

    # 6. Strip any remaining self-closing or empty HTML/JSX tags not inside code blocks
    # (Be careful not to touch code blocks)
    parts = re.split(r"(```[\s\S]*?```)", text)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"<[a-zA-Z0-9_\-]+(\s+[^>]*)?\/>", "", parts[i])
        parts[i] = re.sub(r"<\/?([a-zA-Z0-9_\-]+)(?:\s+[^>]*)?>", "", parts[i])

    return "".join(parts)


def resolve_relative_links(text: str, base_url: str = "https://docs.liara.ir") -> str:
    """
    Resolve markdown relative links like [link](/paas/django) to absolute URLs.
    """
    def link_repl(match):
        label = match.group(1)
        url = match.group(2)
        if url.startswith("/"):
            url = f"{base_url.rstrip('/')}{url}"
        elif url.startswith("./") or url.startswith("../"):
            url = f"{base_url.rstrip('/')}/{url.lstrip('./')}"
        return f"[{label}]({url})"

    # Only replace outside code fences
    parts = re.split(r"(```[\s\S]*?```)", text)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_repl, parts[i])

    return "".join(parts)


class ExtractedDocument:
    def __init__(
        self,
        title: str,
        frontmatter: Dict[str, Any],
        cleaned_markdown: str,
        headings: List[Tuple[int, str, str]],  # (level, text, anchor)
    ):
        self.title = title
        self.frontmatter = frontmatter
        self.cleaned_markdown = cleaned_markdown
        self.headings = headings


def extract_document(
    raw_content: str,
    default_title: str = "",
    base_url: str = "https://docs.liara.ir",
) -> ExtractedDocument:
    """
    Extract frontmatter, clean JSX, resolve links, and collect headings.
    """
    post = frontmatter.loads(raw_content)
    fm = post.metadata or {}
    content = post.content

    # Determine title from frontmatter or first H1
    title = fm.get("title") or fm.get("pageTitle")
    if not title:
        h1_match = re.search(r"^#\s+(.+)$", content, flags=re.MULTILINE)
        if h1_match:
            title = h1_match.group(1).strip()
        else:
            title = default_title or "Untitled"

    # Transform JSX and links
    transformed = transform_jsx_components(content)
    resolved = resolve_relative_links(transformed, base_url)
    cleaned = clean_display_text(resolved)

    # Collect headings
    headings: List[Tuple[int, str, str]] = []
    heading_regex = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    for match in heading_regex.finditer(cleaned):
        level = len(match.group(1))
        heading_text = match.group(2).strip()
        anchor = slugify_heading(heading_text)
        headings.append((level, heading_text, anchor))

    return ExtractedDocument(
        title=title,
        frontmatter=fm,
        cleaned_markdown=cleaned,
        headings=headings,
    )
