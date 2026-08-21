import re
from typing import Optional, Tuple
from shared.text import clean_display_text, detect_language


def is_rejected_page(
    raw_content: str,
    frontmatter: dict,
    min_token_count: int = 40,
) -> Tuple[bool, Optional[str]]:
    """
    Check if a document page should be rejected from indexing:
    - noindex in frontmatter
    - redirect page
    - too short / empty without code fences
    """
    if frontmatter.get("noindex") is True:
        return True, "marked as noindex"
    
    if frontmatter.get("redirect") or frontmatter.get("redirect_to"):
        return True, "redirect page"

    if "404" in frontmatter.get("title", "").lower():
        return True, "404 page"

    # Check length
    has_code = "```" in raw_content
    words = raw_content.split()
    if len(words) < min_token_count and not has_code:
        return True, f"page too short ({len(words)} words, no code)"

    return False, None


def clean_markdown_content(raw_text: str) -> str:
    """
    Clean and normalize markdown text for processing.
    """
    return clean_display_text(raw_text)
