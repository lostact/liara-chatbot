from typing import List, Optional
from sqlalchemy import ColumnElement, and_, or_
from app.db.models import Chunk, Document


def build_search_filters(
    service_tags: Optional[List[str]] = None,
    lang: Optional[str] = None,
    has_code: Optional[bool] = None,
    doc_ids: Optional[List[int]] = None,
) -> List[ColumnElement]:
    """
    Build SQLAlchemy filter clauses for search queries.
    """
    conditions: List[ColumnElement] = [
        Document.status == "active",
        Document.alias_of.is_(None),
        Chunk.revision_id == Document.current_revision_id,
    ]

    if service_tags:
        conditions.append(
            or_(
                Chunk.service_tag.in_(service_tags),
                Document.service_tag.in_(service_tags),
            )
        )

    if lang:
        conditions.append(
            or_(
                Chunk.lang == lang,
                Document.lang == lang,
            )
        )

    if has_code is not None:
        conditions.append(Chunk.has_code == has_code)

    if doc_ids:
        conditions.append(Document.id.in_(doc_ids))

    return conditions
