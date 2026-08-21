import re
import unicodedata
from typing import Tuple

# Arabic to Persian character mapping
ARABIC_TO_PERSIAN_MAP = {
    ord("ي"): "ی",
    ord("ى"): "ی",
    ord("ك"): "ک",
    ord("ة"): "ه",
    ord("ؤ"): "و",
    ord("إ"): "ا",
    ord("أ"): "ا",
    ord("آ"): "آ",
    ord("ء"): "",
}

# Arabic/Persian digits to ASCII
ARABIC_INDIC_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# Zero-Width Non-Joiner
ZWNJ = "\u200c"

PERSIAN_ARABIC_REGEX = re.compile(r"[\u0600-\u06FF\uFB8A\u067E\u0686\u06AF\u200C\u200D]")
LATIN_REGEX = re.compile(r"[a-zA-Z]")
WHITESPACE_REGEX = re.compile(r"\s+")
CODE_BLOCK_REGEX = re.compile(r"```[\s\S]*?```|`[^`]+`")


def normalize_unicode(text: str) -> str:
    """Normalize text using Unicode NFC form."""
    if not text:
        return ""
    return unicodedata.normalize("NFC", text)


def fold_persian_chars(text: str) -> str:
    """Standardize Persian/Arabic characters (e.g. ي -> ی, ك -> ک)."""
    if not text:
        return ""
    return text.translate(ARABIC_TO_PERSIAN_MAP)


def clean_display_text(text: str) -> str:
    """
    Standardize text for display/storage while preserving ZWNJ and original casing.
    """
    if not text:
        return ""
    text = normalize_unicode(text)
    text = fold_persian_chars(text)
    # Remove excessive repeated spaces / empty lines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_search_text(text: str) -> str:
    """
    Normalize text for lexical / keyword search:
    - Unicode NFC
    - Persian character folding
    - Arabic/Persian-Indic digits -> ASCII digits
    - Strip ZWNJ
    - Lowercase ASCII
    """
    if not text:
        return ""
    text = normalize_unicode(text)
    text = fold_persian_chars(text)
    text = text.translate(ARABIC_INDIC_DIGITS)
    text = text.replace(ZWNJ, " ")
    text = WHITESPACE_REGEX.sub(" ", text)
    return text.lower().strip()


def detect_language(text: str, default_lang: str = "fa") -> str:
    """
    Heuristic language detection based on Persian/Arabic script ratio.
    Returns 'fa' or 'en'.
    """
    if not text:
        return default_lang
    
    # Exclude code blocks from language script counting
    prose = CODE_BLOCK_REGEX.sub("", text)
    if not prose.strip():
        prose = text

    fa_chars = len(PERSIAN_ARABIC_REGEX.findall(prose))
    en_chars = len(LATIN_REGEX.findall(prose))

    total = fa_chars + en_chars
    if total == 0:
        return default_lang

    if fa_chars / total >= 0.25:
        return "fa"
    return "en"


def compute_simhash(text: str, hash_bits: int = 64) -> int:
    """
    Compute 64-bit SimHash over token 3-shingles for near-duplicate page detection.
    """
    import hashlib

    tokens = [t for t in re.findall(r"\w+", normalize_search_text(text)) if len(t) > 1]
    if not tokens:
        return 0

    shingles = [" ".join(tokens[i : i + 3]) for i in range(max(1, len(tokens) - 2))]
    if not shingles:
        shingles = tokens

    v = [0] * hash_bits
    for shingle in shingles:
        h = int(hashlib.md5(shingle.encode("utf-8")).hexdigest(), 16)
        for i in range(hash_bits):
            bit = (h >> i) & 1
            if bit == 1:
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(hash_bits):
        if v[i] > 0:
            fingerprint |= 1 << i

    # Convert unsigned 64-bit to signed 64-bit for PostgreSQL BIGINT compatibility
    if fingerprint >= (1 << 63):
        fingerprint -= (1 << 64)

    return fingerprint


def hamming_distance(hash1: int, hash2: int) -> int:
    """Compute Hamming distance between two SimHash integers."""
    x = ((hash1 & 0xFFFFFFFFFFFFFFFF) ^ (hash2 & 0xFFFFFFFFFFFFFFFF))
    dist = 0
    while x:
        dist += 1
        x &= x - 1
    return dist
