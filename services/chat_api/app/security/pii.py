import re

PII_PATTERNS = [
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"(?i)(bearer\s+[a-zA-Z0-9_\-\.]{15,})"), "[BEARER_TOKEN]"),
    (re.compile(r"(?i)(sk-[a-zA-Z0-9]{20,})"), "[API_KEY]"),
    (re.compile(r"(?i)(password[\"']?\s*[:=]\s*[\"']?)([^\"'\s]{4,})"), r"\1[PASSWORD]"),
    (re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b"), "[CARD_NUMBER]"),
    (re.compile(r"\b09\d{9}\b"), "[PHONE_NUMBER]"),  # Iranian mobile number pattern
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP_ADDRESS]"),
]


def scrub_pii(text: str) -> str:
    """
    Scrub common personally identifiable information (PII) from text.
    """
    if not text:
        return ""
    scrubbed = text
    for pattern, replacement in PII_PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed
