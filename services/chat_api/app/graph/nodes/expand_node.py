import logging
from typing import Any, Dict
from app.graph.state import ChatState
from app.graph.policies import MAX_RETRIEVAL_LOOPS

logger = logging.getLogger(__name__)


async def expand_node(state: ChatState) -> Dict[str, Any]:
    current_loops = state.get("retrieval_loop_count", 0)
    logger.info(f"Expand node triggered (loop {current_loops}/{MAX_RETRIEVAL_LOOPS})")
    
    # Ready for another retrieval pass with expanded queries
    return {}
