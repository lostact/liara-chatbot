import asyncio
import logging
from typing import Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from shared.settings import get_settings
from app.db.models import EmbeddingCache

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingProvider:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
        proxy: Optional[str] = None,
    ):
        self.api_key = api_key if api_key is not None else settings.ai.embedding_api_key
        self.base_url = (base_url or settings.ai.embedding_base_url).rstrip("/")
        self.model = model or settings.ai.EMBEDDING_MODEL
        self.dimensions = dimensions if dimensions is not None else settings.ai.EMBEDDING_DIMENSIONS
        self.proxy = proxy if proxy is not None else settings.ai.embedding_proxy_url
        self.proxy = self.proxy or None
        # Include the endpoint and dimensions so switching providers or
        # vector sizes cannot reuse an incompatible cached embedding.
        self.cache_model = f"{self.base_url}|{self.model}|{self.dimensions}"
        self._query_embed_cache: Dict[str, List[float]] = {}

    async def embed_batch_api(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """
        Call an OpenAI-compatible embeddings endpoint for a batch of texts.
        """
        target_model = model or self.model
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": target_model,
            "input": texts,
        }
        if settings.ai.EMBEDDING_SEND_DIMENSIONS and self.dimensions:
            payload["dimensions"] = self.dimensions

        for attempt in range(4):
            async with httpx.AsyncClient(timeout=60.0, proxy=self.proxy) as client:
                try:
                    response = await client.post(
                        f"{self.base_url}/embeddings",
                        json=payload,
                        headers=headers,
                    )
                    if response.status_code == 429:
                        wait_time = 3.0 * (attempt + 1)
                        logger.warning(
                            f"[OpenAI-compatible Embeddings] Rate limited (429) on model={target_model}. "
                            f"Response body: {response.text}. Waiting {wait_time}s "
                            f"(attempt {attempt + 1}/4)"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    if response.status_code >= 400:
                        logger.error(
                            f"[OpenAI-compatible Embeddings Error] Status: {response.status_code}, "
                            f"Model: {target_model}, Response: {response.text}"
                        )
                    response.raise_for_status()
                    data = response.json()

                    # Sort results by index to preserve input order.
                    embeddings_data = sorted(data["data"], key=lambda x: x.get("index", 0))
                    embeddings = [item["embedding"] for item in embeddings_data]
                    if self.dimensions and any(len(embedding) != self.dimensions for embedding in embeddings):
                        actual_dimensions = len(embeddings[0]) if embeddings else 0
                        raise ValueError(
                            f"Embedding provider returned {actual_dimensions} dimensions, "
                            f"but EMBEDDING_DIMENSIONS is configured as {self.dimensions}. "
                            "Set a supported dimension or migrate the pgvector columns."
                        )
                    return embeddings
                except Exception as e:
                    logger.warning(
                        f"[OpenAI-compatible Embeddings Attempt {attempt + 1}/4 Failed] "
                        f"Model: {target_model}, Error: {str(e)}"
                    )
                    if attempt == 3:
                        logger.error(
                            f"[OpenAI-compatible Embeddings Exhausted Retries] Model {target_model} failed: {e}"
                        )
                        if target_model != settings.ai.EMBEDDING_FALLBACK_MODEL:
                            logger.info(
                                f"Switching to fallback embedding model: "
                                f"{settings.ai.EMBEDDING_FALLBACK_MODEL}"
                            )
                            return await self.embed_batch_api(
                                texts,
                                model=settings.ai.EMBEDDING_FALLBACK_MODEL,
                            )
                        raise
                    await asyncio.sleep(1.5 * (attempt + 1))
        return []

    async def get_or_create_embeddings(
        self,
        session: AsyncSession,
        text_hash_tuples: List[tuple[str, str]],  # (text_hash, embed_text)
    ) -> Dict[str, List[float]]:
        """
        Cached embedding retrieval. Checks embedding_cache first; calls API for missing items.
        Returns a dict mapping text_hash -> embedding vector.
        """
        results: Dict[str, List[float]] = {}
        if not text_hash_tuples:
            return results

        hashes = [h for h, _ in text_hash_tuples]

        # 1. Query existing cache.
        stmt = select(EmbeddingCache).where(
            EmbeddingCache.text_hash.in_(hashes),
            EmbeddingCache.model == self.cache_model,
        )
        cache_res = await session.execute(stmt)
        for row in cache_res.scalars():
            results[row.text_hash] = list(row.embedding)

        # 2. Identify missing items and deduplicate by text_hash.
        unique_missing_dict = {h: t for h, t in text_hash_tuples if h not in results}
        unique_missing = list(unique_missing_dict.items())

        if unique_missing:
                # Keep embeddings requests within conservative item and
                # character limits supported by most OpenAI-compatible APIs.
            batches: List[List[tuple[str, str]]] = []
            current_batch: List[tuple[str, str]] = []
            current_chars = 0

            for h, text in unique_missing:
                truncated_text = text[:6000]
                text_len = len(truncated_text)

                if (
                    len(current_batch) >= settings.ai.EMBEDDING_BATCH_SIZE
                    or current_chars + text_len > 35000
                ) and current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_chars = 0

                current_batch.append((h, truncated_text))
                current_chars += text_len

            if current_batch:
                batches.append(current_batch)

            for batch in batches:
                batch_texts = [t for _, t in batch]
                embeddings = await self.embed_batch_api(batch_texts)

                for (h, _), emb in zip(batch, embeddings):
                    results[h] = emb
                    insert_stmt = (
                        pg_insert(EmbeddingCache)
                        .values(
                            text_hash=h,
                            model=self.cache_model,
                            embedding=emb,
                        )
                        .on_conflict_do_nothing(index_elements=["text_hash"])
                    )
                    await session.execute(insert_stmt)

            await session.flush()

        return results

    async def embed_query(self, query: str) -> List[float]:
        """Embed a single search query with fast in-memory caching."""
        if query in self._query_embed_cache:
            return self._query_embed_cache[query]

        results = await self.embed_batch_api([query])
        emb = results[0]
        if len(self._query_embed_cache) > 2000:
            self._query_embed_cache.clear()
        self._query_embed_cache[query] = emb
        return emb
