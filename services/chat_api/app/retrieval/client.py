import logging
from typing import Any, Dict, List, Optional
import httpx
from shared.settings import get_settings
from shared.schemas.search import SearchRequest, SearchResponse
from shared.schemas.document import DocumentResponse
from app.retrieval.circuit_breaker import CircuitBreaker, CircuitBreakerOpenException
from app.retrieval.cache import RedisCache

logger = logging.getLogger(__name__)
settings = get_settings()


class IndexerClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        internal_token: Optional[str] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        cache: Optional[RedisCache] = None,
    ):
        self.base_url = (base_url or settings.chat_api.INDEXER_BASE_URL).rstrip("/")
        self.internal_token = internal_token or settings.security.INTERNAL_TOKEN
        self.breaker = circuit_breaker or CircuitBreaker(name="indexer_search")
        self.cache = cache or RedisCache()

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-Internal-Token": self.internal_token,
            "Content-Type": "application/json",
        }

    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        Execute search on indexer service with caching & circuit breaking.
        """
        cache_key = request.query or (request.queries[0] if request.queries else "")
        if cache_key:
            cached_res = await self.cache.get_cached_search(cache_key)
            if cached_res:
                return SearchResponse(**cached_res)

        if not self.breaker.allow_request():
            logger.warning("Circuit breaker OPEN for indexer search. Fallback mode.")
            return SearchResponse(results=[], took_ms=0)

        async with httpx.AsyncClient(timeout=settings.chat_api.CIRCUIT_BREAKER_TIMEOUT_SECS) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/internal/search",
                    json=request.model_dump(exclude_none=True),
                    headers=self._get_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                self.breaker.record_success()

                search_resp = SearchResponse(**data)
                if cache_key and search_resp.results:
                    await self.cache.set_cached_search(cache_key, data)

                return search_resp
            except Exception as e:
                self.breaker.record_failure()
                logger.error(f"Error calling indexer /internal/search at {self.base_url}: {e}", exc_info=True)
                return SearchResponse(results=[], took_ms=0)

    async def get_document(self, doc_id: int, include_markdown: bool = True) -> Optional[DocumentResponse]:
        """Fetch full document body by ID."""
        async with httpx.AsyncClient(timeout=3.0) as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/internal/documents/{doc_id}",
                    params={"include": str(include_markdown).lower()},
                    headers=self._get_headers(),
                )
                if resp.status_code == 200:
                    return DocumentResponse(**resp.json())
            except Exception as e:
                logger.error(f"Error fetching document {doc_id}: {e}")
        return None
