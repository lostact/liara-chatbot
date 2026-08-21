from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SyncRequest(BaseModel):
    mode: str = "incremental"  # "incremental" | "full"
    dry_run: bool = False


class SyncRunResponse(BaseModel):
    id: int
    trigger: str
    source: str
    status: str
    from_git_sha: Optional[str] = None
    to_git_sha: Optional[str] = None
    pages_seen: int = 0
    pages_changed: int = 0
    chunks_written: int = 0
    embed_tokens: int = 0
    cost_usd: float = 0.0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class ReindexRequest(BaseModel):
    full: bool = True
    embedding_model: Optional[str] = None


class RollbackRequest(BaseModel):
    document_id: int
    revision_id: int


class AdminStatusResponse(BaseModel):
    corpus_stats: Dict[str, Any] = Field(default_factory=dict)
    index_generation: int = 1
    last_sync_runs: List[SyncRunResponse] = Field(default_factory=list)
    queue_depth: int = 0
    issues_count: int = 0
