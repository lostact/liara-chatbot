from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentBase(BaseModel):
    url: str
    repo_path: Optional[str] = None
    title: str
    nav_path: List[str] = Field(default_factory=list)
    service_tag: Optional[str] = None
    lang: str = "fa"
    source: str = "repo"
    alias_of: Optional[int] = None
    status: str = "active"


class DocumentResponse(DocumentBase):
    id: int
    current_revision_id: Optional[int] = None
    simhash: Optional[int] = None
    first_seen_at: datetime
    last_seen_at: datetime
    markdown: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentRevision(BaseModel):
    id: int
    document_id: int
    content_hash: str
    markdown: str
    frontmatter: Dict[str, Any] = Field(default_factory=dict)
    git_sha: Optional[str] = None
    doc_version: Optional[str] = None
    indexed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChunkBase(BaseModel):
    document_id: int
    revision_id: int
    ordinal: int
    anchor: Optional[str] = None
    heading_path: List[str] = Field(default_factory=list)
    text: str
    embed_text: str
    text_hash: str
    token_count: int
    has_code: bool = False
    code_langs: List[str] = Field(default_factory=list)
    lang: str = "fa"
    service_tag: Optional[str] = None


class ChunkResponse(ChunkBase):
    id: int

    class Config:
        from_attributes = True
