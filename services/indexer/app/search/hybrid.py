import asyncio
from collections import defaultdict
import hashlib
import json
import logging
import sys
import time
from typing import Any, Dict, List, Optional
import redis.asyncio as aioredis
from sqlalchemy import func, select, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from shared.text import normalize_search_text
from shared.schemas.search import SearchFilters, SearchRequest, SearchResultItem, SearchResponse
from shared.settings import get_settings
from app.db.models import Chunk, Document, DocumentRevision
from app.pipeline.embed import EmbeddingProvider
from app.search.filters import build_search_filters

logger = logging.getLogger(__name__)
settings = get_settings()
# Uvicorn's web process defaults application loggers to WARNING, while the
# cron process configures INFO logging separately. Keep search timing logs
# visible in both processes without requiring a global logging reconfiguration.
logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
if not logger.handlers:
    timing_handler = logging.StreamHandler(sys.stderr)
    timing_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(timing_handler)
logger.propagate = False


class HybridSearchService:
    def __init__(
        self,
        embedder: Optional[EmbeddingProvider] = None,
        redis_client: Optional[aioredis.Redis] = None,
    ):
        self.embedder = embedder or EmbeddingProvider()
        self._redis = redis_client

    async def get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.redis.url)
        return self._redis

    def _compute_cache_key(self, request: SearchRequest, generation: int) -> str:
        q_str = f"{request.query or ''}|{sorted(request.queries or [])}"
        filters_str = request.filters.model_dump_json() if request.filters else ""
        raw = f"{normalize_search_text(q_str)}|{request.top_k}|{filters_str}|{request.expand_neighbours}"
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"search_cache:v{generation}:{h}"

    @staticmethod
    def _log_search_timing(
        timings: Dict[str, Any],
        query_count: int,
        top_k: int,
        result_count: int,
        cache_hit: bool,
        total_ms: float,
    ) -> None:
        """Emit one INFO-level line suitable for docker logs troubleshooting."""
        timing_parts = []
        for name, value in timings.items():
            if isinstance(value, list):
                formatted = ",".join(f"{item:.1f}" for item in value)
                timing_parts.append(f"{name}_ms=[{formatted}]")
            else:
                timing_parts.append(f"{name}_ms={value:.1f}")
        logger.info(
            "[Search Timing] cache_hit=%s query_count=%d top_k=%d results=%d total_ms=%.1f %s",
            cache_hit,
            query_count,
            top_k,
            result_count,
            total_ms,
            " ".join(timing_parts),
        )

    async def search(
        self,
        session: AsyncSession,
        request: SearchRequest,
    ) -> SearchResponse:
        start_time = time.time()
        perf_start = time.perf_counter()
        timings: Dict[str, Any] = {}
        cache_hit = False

        # 0. Check Redis search cache scoped to active index generation
        generation = 1
        cache_key = None
        cache_started = time.perf_counter()
        try:
            r = await self.get_redis()
            gen_val = await r.get("index:generation")
            if gen_val:
                generation = int(gen_val)
            cache_key = self._compute_cache_key(request, generation)
            cached_val = await r.get(cache_key)
            if cached_val:
                cached_data = json.loads(cached_val)
                cached_data["took_ms"] = 1
                cache_hit = True
                timings["cache"] = (time.perf_counter() - cache_started) * 1000
                self._log_search_timing(
                    timings,
                    query_count=1 + len(request.queries or []),
                    top_k=request.top_k,
                    result_count=len(cached_data.get("results", [])),
                    cache_hit=True,
                    total_ms=(time.perf_counter() - perf_start) * 1000,
                )
                return SearchResponse(**cached_data)
        except Exception as e:
            logger.warning(f"Error accessing search cache: {e}")
        timings["cache"] = (time.perf_counter() - cache_started) * 1000
        
        # 1. Prepare and deduplicate queries
        query_list: List[str] = []
        if request.query:
            query_list.append(request.query.strip())
        if request.queries:
            for q in request.queries:
                q_clean = q.strip()
                if q_clean and q_clean not in query_list:
                    query_list.append(q_clean)

        if not query_list:
            self._log_search_timing(
                timings, 0, request.top_k, 0, cache_hit, (time.perf_counter() - perf_start) * 1000
            )
            return SearchResponse(results=[], took_ms=0)

        # 2. Parallel execution: Embed all query variants in a single batch while starting lexical search
        normalized_queries = [normalize_search_text(q) for q in query_list if normalize_search_text(q)]
        if not normalized_queries:
            self._log_search_timing(
                timings, len(query_list), request.top_k, 0, cache_hit, (time.perf_counter() - perf_start) * 1000
            )
            return SearchResponse(results=[], took_ms=0)

        # Embed all query variants in one OpenAI-compatible embeddings request.
        async def timed_embed() -> List[List[float]]:
            started = time.perf_counter()
            try:
                return await self.embedder.embed_batch_api(query_list)
            finally:
                timings["embedding"] = (time.perf_counter() - started) * 1000

        embed_task = timed_embed()
        
        # Run lexical search in parallel
        async def timed_lexical() -> List[List[Dict[str, Any]]]:
            started = time.perf_counter()
            try:
                return await self._batch_lexical_search(session, normalized_queries, request.filters, limit=35)
            finally:
                timings["lexical"] = (time.perf_counter() - started) * 1000

        lexical_task = timed_lexical()

        retrieval_started = time.perf_counter()
        vectors, lex_hits_by_query = await asyncio.gather(embed_task, lexical_task)
        timings["embed_lexical_parallel"] = (time.perf_counter() - retrieval_started) * 1000

        # 3. Dense search using returned vectors
        dense_timings: List[float] = []

        async def timed_dense(vector: List[float]) -> List[Dict[str, Any]]:
            started = time.perf_counter()
            try:
                return await self._dense_search_with_vector(session, vector, request.filters, limit=35)
            finally:
                dense_timings.append((time.perf_counter() - started) * 1000)

        dense_started = time.perf_counter()
        dense_hits_by_query = await asyncio.gather(*[timed_dense(vec) for vec in vectors])
        timings["dense"] = (time.perf_counter() - dense_started) * 1000
        timings["dense_query"] = dense_timings

        # 4. Reciprocal Rank Fusion (k=60) across all queries & modalities
        fusion_started = time.perf_counter()
        rrf_k = 60.0
        rrf_scores: Dict[int, float] = defaultdict(float)
        chunk_metadata_map: Dict[int, Dict[str, Any]] = {}

        # Fuse Dense results
        for dense_hits in dense_hits_by_query:
            for rank, hit in enumerate(dense_hits):
                cid = hit["chunk_id"]
                rrf_scores[cid] += 1.0 / (rrf_k + rank + 1)
                if cid not in chunk_metadata_map:
                    chunk_metadata_map[cid] = hit

        # Fuse Lexical results
        for lex_hits in lex_hits_by_query:
            for rank, hit in enumerate(lex_hits):
                cid = hit["chunk_id"]
                rrf_scores[cid] += 1.0 / (rrf_k + rank + 1)
                if cid not in chunk_metadata_map:
                    chunk_metadata_map[cid] = hit

        timings["fusion"] = (time.perf_counter() - fusion_started) * 1000

        if not rrf_scores:
            took_ms = int((time.time() - start_time) * 1000)
            self._log_search_timing(
                timings, len(query_list), request.top_k, 0, cache_hit, (time.perf_counter() - perf_start) * 1000
            )
            return SearchResponse(results=[], took_ms=took_ms)

        # Sort by RRF score and take top 20 candidates
        sorted_cids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:20]
        # Normalize the rank-fusion score to [0, 1]. The theoretical maximum
        # is a rank-1 match in both dense and lexical search for every query
        # variant. This is a relative fusion score, not a probability.
        max_rrf_score = (len(query_list) * 2.0) / (rrf_k + 1.0)
        top_candidates = []
        for cid in sorted_cids:
            item = dict(chunk_metadata_map[cid])
            item["rrf_score"] = rrf_scores[cid]
            item["normalized_rrf_score"] = min(1.0, rrf_scores[cid] / max_rrf_score)
            top_candidates.append(item)

        # Reranking is intentionally not used: the extra network hop did not
        # justify its latency for this service's speed target.
        selection_started = time.perf_counter()
        selected_results = top_candidates[: request.top_k]
        timings["selection"] = (time.perf_counter() - selection_started) * 1000

        # 6. Fast Batch Neighbour expansion in a single SQL query
        neighbours_started = time.perf_counter()
        if request.expand_neighbours:
            selected_results = await self._expand_neighbours_batch(session, selected_results)
        timings["neighbours"] = (time.perf_counter() - neighbours_started) * 1000

        # Convert to SearchResultItem list
        results: List[SearchResultItem] = []
        for d in selected_results:
            url = d["url"]
            if d.get("anchor"):
                url = f"{url}#{d['anchor']}"

            results.append(
                SearchResultItem(
                    chunk_id=d["chunk_id"],
                    doc_id=d["doc_id"],
                    url=url,
                    anchor=d.get("anchor"),
                    title=d.get("title", ""),
                    heading_path=d.get("heading_path") or [],
                    text=d["text"],
                    # Expose the normalized RRF score. Raw dense and lexical
                    # scores use incompatible scales and remain internal.
                    score=float(d["normalized_rrf_score"]),
                    doc_version=d.get("doc_version"),
                    last_updated=d.get("last_updated"),
                    service_tag=d.get("service_tag"),
                    lang=d.get("lang", "fa"),
                )
            )

        took_ms = int((time.time() - start_time) * 1000)
        response = SearchResponse(results=results, took_ms=took_ms)

        # Store in Redis cache scoped to generation
        if cache_key:
            cache_write_started = time.perf_counter()
            try:
                r = await self.get_redis()
                await r.setex(cache_key, 86400 * 7, response.model_dump_json())
            except Exception as e:
                logger.warning(f"Error saving to search cache: {e}")
            timings["cache_write"] = (time.perf_counter() - cache_write_started) * 1000

        self._log_search_timing(
            timings,
            len(query_list),
            request.top_k,
            len(results),
            cache_hit,
            (time.perf_counter() - perf_start) * 1000,
        )

        return response

    async def _dense_search_with_vector(
        self,
        session: AsyncSession,
        query_vector: List[float],
        filters: Optional[SearchFilters],
        limit: int = 35,
    ) -> List[Dict[str, Any]]:
        base_filters = build_search_filters(
            service_tags=filters.service_tags if filters else None,
            lang=filters.lang if filters else None,
            has_code=filters.has_code if filters else None,
            doc_ids=filters.doc_ids if filters else None,
        )

        distance_col = Chunk.embedding.cosine_distance(query_vector).label("distance")

        stmt = (
            select(
                Chunk.id.label("chunk_id"),
                Chunk.document_id.label("doc_id"),
                Chunk.revision_id,
                Chunk.ordinal,
                Chunk.anchor,
                Chunk.heading_path,
                Chunk.text,
                Chunk.service_tag,
                Chunk.lang,
                Document.url,
                Document.title,
                Document.last_seen_at,
                distance_col,
            )
            .join(Document, Chunk.document_id == Document.id)
            .where(and_(*base_filters, Chunk.embedding.is_not(None)))
            .order_by(distance_col.asc())
            .limit(limit)
        )

        result = await session.execute(stmt)
        hits = []
        for row in result.all():
            score = max(0.0, 1.0 - float(row.distance))
            hits.append(
                {
                    "chunk_id": row.chunk_id,
                    "doc_id": row.doc_id,
                    "revision_id": row.revision_id,
                    "ordinal": row.ordinal,
                    "anchor": row.anchor,
                    "heading_path": row.heading_path,
                    "text": row.text,
                    "service_tag": row.service_tag,
                    "lang": row.lang,
                    "url": row.url,
                    "title": row.title,
                    "last_updated": row.last_seen_at.isoformat() if row.last_seen_at else None,
                    "score": score,
                }
            )
        return hits

    async def _batch_lexical_search(
        self,
        session: AsyncSession,
        norm_queries: List[str],
        filters: Optional[SearchFilters],
        limit: int = 35,
    ) -> List[List[Dict[str, Any]]]:
        """Execute lexical search for all normalized queries."""
        tasks = [self._lexical_search_single(session, nq, filters, limit) for nq in norm_queries]
        return await asyncio.gather(*tasks)

    async def _lexical_search_single(
        self,
        session: AsyncSession,
        norm_query: str,
        filters: Optional[SearchFilters],
        limit: int = 35,
    ) -> List[Dict[str, Any]]:
        base_filters = build_search_filters(
            service_tags=filters.service_tags if filters else None,
            lang=filters.lang if filters else None,
            has_code=filters.has_code if filters else None,
            doc_ids=filters.doc_ids if filters else None,
        )

        tsquery = func.plainto_tsquery("simple", func.immutable_unaccent(norm_query))
        ts_rank = func.ts_rank_cd(Chunk.tsv, tsquery).label("rank")
        trgm_sim = func.similarity(Chunk.text, norm_query).label("trgm_sim")

        stmt = (
            select(
                Chunk.id.label("chunk_id"),
                Chunk.document_id.label("doc_id"),
                Chunk.revision_id,
                Chunk.ordinal,
                Chunk.anchor,
                Chunk.heading_path,
                Chunk.text,
                Chunk.service_tag,
                Chunk.lang,
                Document.url,
                Document.title,
                Document.last_seen_at,
                ts_rank,
                trgm_sim,
            )
            .join(Document, Chunk.document_id == Document.id)
            .where(
                and_(
                    *base_filters,
                    or_(
                        Chunk.tsv.op("@@")(tsquery),
                        Chunk.text.op("%")(norm_query),
                    ),
                )
            )
            .order_by((ts_rank * 0.7 + trgm_sim * 0.3).desc())
            .limit(limit)
        )

        try:
            result = await session.execute(stmt)
            hits = []
            for row in result.all():
                rank_score = float(row.rank) if row.rank else 0.0
                trgm_score = float(row.trgm_sim) if row.trgm_sim else 0.0
                combined_score = rank_score * 0.7 + trgm_score * 0.3
                hits.append(
                    {
                        "chunk_id": row.chunk_id,
                        "doc_id": row.doc_id,
                        "revision_id": row.revision_id,
                        "ordinal": row.ordinal,
                        "anchor": row.anchor,
                        "heading_path": row.heading_path,
                        "text": row.text,
                        "service_tag": row.service_tag,
                        "lang": row.lang,
                        "url": row.url,
                        "title": row.title,
                        "last_updated": row.last_seen_at.isoformat() if row.last_seen_at else None,
                        "score": combined_score,
                    }
                )
            return hits
        except Exception as e:
            logger.warning(f"Lexical search execution error: {e}")
            return []

    async def _expand_neighbours_batch(
        self,
        session: AsyncSession,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Fetch all sibling chunks in a single batch SQL query.
        """
        if not results:
            return results

        # Build conditions for all candidate items
        pairs = []
        for r in results:
            rev_id = r.get("revision_id")
            ord_id = r.get("ordinal")
            if rev_id is not None and ord_id is not None:
                pairs.append((rev_id, ord_id - 1))
                pairs.append((rev_id, ord_id + 1))

        if not pairs:
            return results

        conds = [and_(Chunk.revision_id == rid, Chunk.ordinal == oid) for rid, oid in pairs]
        stmt = select(Chunk.revision_id, Chunk.ordinal, Chunk.text, Chunk.anchor).where(or_(*conds))

        res = await session.execute(stmt)
        # (rev_id, ord_id) -> (text, anchor)
        siblings_map = {(row.revision_id, row.ordinal): (row.text, row.anchor) for row in res.all()}

        expanded_results = []
        for item in results:
            item_copy = dict(item)
            rev_id = item.get("revision_id")
            ordinal = item.get("ordinal")
            anchor = item.get("anchor")

            if rev_id is not None and ordinal is not None:
                before_text = ""
                after_text = ""

                # Previous chunk
                prev_data = siblings_map.get((rev_id, ordinal - 1))
                if prev_data and prev_data[1] == anchor:
                    before_text = prev_data[0][-350:] + "\n\n"

                # Next chunk
                next_data = siblings_map.get((rev_id, ordinal + 1))
                if next_data and next_data[1] == anchor:
                    after_text = "\n\n" + next_data[0][:350]

                if before_text or after_text:
                    item_copy["text"] = f"{before_text}{item['text']}{after_text}"

            expanded_results.append(item_copy)

        return expanded_results
