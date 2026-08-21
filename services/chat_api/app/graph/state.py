from typing import Any, Dict, List, Optional, TypedDict
from shared.schemas.chat import ActionLink, CitationItem, ClarifyAction
from shared.schemas.search import SearchResultItem


class ChatState(TypedDict, total=False):
    # Input
    conversation_id: str
    message: str
    host_context: Dict[str, Any]
    options: Dict[str, Any]
    site_key: str
    visitor_hash: str
    trace_id: str

    # Hydration
    lang: str
    summary: str
    profile: Dict[str, Any]
    recent_messages: List[Dict[str, Any]]

    # Guard & Shortcuts
    guard_safe: bool
    shortcut_response: Optional[str]
    shortcut_links: Optional[List[Dict[str, str]]]
    is_shortcut: bool

    # Routing
    action: str  # search | clarify | multi_step | refuse | answer_from_context
    intent: str
    search_queries: List[str]
    service_tags: List[str]
    clarify_action: Optional[ClarifyAction]
    steps: List[str]
    route_confidence: float

    # Retrieval & Search Loop
    search_results: List[SearchResultItem]
    packed_context: str
    citations: List[CitationItem]
    retrieval_loop_count: int
    is_sufficient: bool
    missing_aspects: List[str]

    # Synthesis
    draft_answer: str
    final_answer: str
    is_grounded: bool
    confidence: str  # high | medium | low

    # Timings & Observability
    timings: Dict[str, float]

    # Output & Persistence
    message_id: int
    tokens_prompt: int
    tokens_completion: int
    cost_usd: float
    latency_ms: int
    suggestions: List[str]
    action_links: List[ActionLink]
