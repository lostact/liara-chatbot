from typing import List, Optional
from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    service_tags: Optional[List[str]] = None
    lang: Optional[str] = None
    has_code: Optional[bool] = None
    doc_ids: Optional[List[int]] = None


class SearchRequest(BaseModel):
    query: Optional[str] = None
    queries: Optional[List[str]] = None
    top_k: int = Field(default=8, ge=1, le=50)
    filters: Optional[SearchFilters] = None
    expand_neighbours: bool = True


class SearchResultItem(BaseModel):
    chunk_id: int
    doc_id: int
    url: str
    anchor: Optional[str] = None
    title: str
    heading_path: List[str] = Field(default_factory=list)
    text: str
    score: float = Field(
        description="Normalized Reciprocal Rank Fusion score in the [0, 1] range; not a probability"
    )
    doc_version: Optional[str] = None
    last_updated: Optional[str] = None
    service_tag: Optional[str] = None
    lang: str = "fa"


class SearchResponse(BaseModel):
    results: List[SearchResultItem] = Field(default_factory=list)
    took_ms: int = 0
