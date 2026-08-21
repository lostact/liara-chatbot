"""Small policy helpers for support escalation and suggestion filtering."""

from typing import Iterable


SUPPORT_TERMS = (
    "ticket",
    "support",
    "human agent",
    "contact an agent",
    "پشتیبانی",
    "تیکت",
    "کارشناس",
    "تماس با پشتیبانی",
)

INCIDENT_TERMS = (
    "outage",
    "incident",
    "billing",
    "payment",
    "refund",
    "account",
    "پرداخت",
    "صورتحساب",
    "قطعی",
    "اختلال",
    "خطا",
    "کار نمی کند",
    "کار نمیکند",
)


def should_offer_support_ticket(query: str) -> bool:
    """Return true only for explicit support or likely account/incident issues."""
    normalized = (query or "").casefold()
    return any(term in normalized for term in (*SUPPORT_TERMS, *INCIDENT_TERMS))


def clean_suggestions(values: Iterable[object], limit: int = 3) -> list[str]:
    """Keep only short, query-oriented suggestions suitable for UI chips."""
    cleaned: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        text = " ".join(value.split()).strip()
        if not text or len(text) > 160:
            continue
        if any(term in text.casefold() for term in SUPPORT_TERMS):
            continue
        if text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned
