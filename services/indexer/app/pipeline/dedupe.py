import hashlib
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.text import compute_simhash, hamming_distance, normalize_search_text
from app.db.models import Document


def compute_content_hash(text: str) -> str:
    """Compute sha256 hex digest of normalized markdown text."""
    normalized = normalize_search_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_text_hash(text: str) -> str:
    """Compute sha256 hex digest for chunk text deduplication."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


async def find_near_duplicate(
    session: AsyncSession,
    simhash_val: int,
    current_doc_id: Optional[int] = None,
    max_hamming_dist: int = 3,
) -> Optional[int]:
    """
    Find if an existing active document is a near-duplicate based on SimHash.
    Returns the canonical document ID if found, else None.
    """
    if simhash_val == 0:
        return None

    stmt = select(Document.id, Document.simhash).where(
        Document.status == "active",
        Document.alias_of.is_(None),
        Document.simhash.is_not(None),
    )
    if current_doc_id:
        stmt = stmt.where(Document.id != current_doc_id)

    result = await session.execute(stmt)
    rows = result.all()

    for doc_id, existing_hash in rows:
        if existing_hash is not None:
            dist = hamming_distance(simhash_val, existing_hash)
            if dist <= max_hamming_dist:
                return doc_id

    return None
