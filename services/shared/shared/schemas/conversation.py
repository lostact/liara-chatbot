from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from shared.schemas.chat import CitationItem


class MessageItem(BaseModel):
    id: int
    seq: int
    role: str
    content: str
    citations: List[CitationItem] = Field(default_factory=list)
    route: Optional[str] = None
    confidence: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: UUID
    site_key: str
    lang: Optional[str] = None
    profile: Dict[str, Any] = Field(default_factory=dict)
    summary: Optional[str] = None
    msg_count: int = 0
    created_at: datetime
    last_activity_at: datetime
    messages: List[MessageItem] = Field(default_factory=list)

    class Config:
        from_attributes = True
