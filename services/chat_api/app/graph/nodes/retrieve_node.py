import logging
import time
from typing import Any, Dict
from app.graph.state import ChatState
from app.retrieval.client import IndexerClient
from app.retrieval.packer import pack_retrieval_context
from shared.schemas.search import SearchFilters, SearchRequest

logger = logging.getLogger(__name__)
indexer_client = IndexerClient()


async def retrieve_node(state: ChatState) -> Dict[str, Any]:
    t0 = time.time()
    queries = state.get("search_queries") or [state.get("message", "")]
    
    filters = SearchFilters(
        lang=state.get("lang"),
    )

    req = SearchRequest(
        queries=queries,
        top_k=8,
        filters=filters,
        expand_neighbours=True,
    )

    resp = await indexer_client.search(req)
    packed = pack_retrieval_context(resp.results)

    loop_count = state.get("retrieval_loop_count", 0) + 1
    top_score = resp.results[0].score if resp.results else 0.0

    # Normalized RRF scores are in [0, 1]. Require strong agreement near the
    # top of both rankings to skip grading.
    is_sufficient = top_score >= 0.75

    timings = dict(state.get("timings") or {})
    timings["retrieve"] = round(time.time() - t0, 3)

    return {
        "search_results": resp.results,
        "packed_context": packed.context_string,
        "citations": packed.citations,
        "retrieval_loop_count": loop_count,
        "is_sufficient": is_sufficient,
        "timings": timings,
    }
