from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatContext(BaseModel):
    page_url: Optional[str] = None
    section: Optional[str] = None
    product: Optional[str] = None
    plan: Optional[str] = None
    user_ref: Optional[str] = None
    ui_lang: Optional[str] = None


class ChatOptions(BaseModel):
    lang: str = "auto"
    stream: bool = True


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=1500)
    context: Optional[ChatContext] = None
    options: Optional[ChatOptions] = None


class CitationItem(BaseModel):
    n: int
    title: str
    url: str
    heading_path: List[str] = Field(default_factory=list)
    last_updated: Optional[str] = None
    score: Optional[float] = None


class ActionLink(BaseModel):
    label: str
    url: str


class ClarifyChoice(BaseModel):
    id: str
    label: str
    value: str


class ClarifyAction(BaseModel):
    question: str
    choices: List[ClarifyChoice] = Field(default_factory=list)


class ChatActions(BaseModel):
    suggestions: List[str] = Field(default_factory=list)
    links: List[ActionLink] = Field(default_factory=list)
    clarify: Optional[ClarifyAction] = None


class TokenUsage(BaseModel):
    prompt: int = 0
    completion: int = 0


class ChatSyncResponse(BaseModel):
    conversation_id: str
    message_id: int
    trace_id: str
    content: str
    citations: List[CitationItem] = Field(default_factory=list)
    actions: Optional[ChatActions] = None
    confidence: str = "high"
    tokens: TokenUsage = Field(default_factory=TokenUsage)
    cost_usd: float = 0.0
    latency_ms: int = 0
