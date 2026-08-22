import hashlib
import json
import logging
from typing import Any, Dict, Optional
import redis.asyncio as aioredis
from shared.settings import get_settings
from shared.text import normalize_search_text

logger = logging.getLogger(__name__)
settings = get_settings()

# Keep chat-side caches separate from the indexer's cache and invalidate values
# written under the previous, incomplete cache-key and quality semantics.
SEARCH_CACHE_PREFIX = "chat_search_cache_v2"
ANSWER_CACHE_PREFIX = "chat_answer_cache_v2"


class RedisCache:
    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self._redis = redis_client

    async def get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.redis.url)
        return self._redis

    async def _hash_key(self, prefix: str, raw: str) -> str:
        generation = 1
        try:
            r = await self.get_redis()
            gen_val = await r.get("index:generation")
            if gen_val:
                generation = int(gen_val)
        except Exception:
            pass
        norm = normalize_search_text(raw)
        h = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        return f"{prefix}:v{generation}:{h}"

    async def get_cached_search(self, query: str) -> Optional[Dict[str, Any]]:
        try:
            r = await self.get_redis()
            key = await self._hash_key(SEARCH_CACHE_PREFIX, query)
            val = await r.get(key)
            if val:
                return json.loads(val)
        except Exception as e:
            logger.warning(f"Error reading search cache: {e}")
        return None

    async def set_cached_search(self, query: str, data: Dict[str, Any], ttl_seconds: int = 86400 * 7):
        try:
            r = await self.get_redis()
            key = await self._hash_key(SEARCH_CACHE_PREFIX, query)
            await r.setex(key, ttl_seconds, json.dumps(data))
        except Exception as e:
            logger.warning(f"Error setting search cache: {e}")

    async def get_cached_answer(self, query: str) -> Optional[Dict[str, Any]]:
        try:
            r = await self.get_redis()
            key = await self._hash_key(ANSWER_CACHE_PREFIX, query)
            val = await r.get(key)
            if val:
                return json.loads(val)
        except Exception as e:
            logger.warning(f"Error reading answer cache: {e}")
        return None

    async def set_cached_answer(self, query: str, data: Dict[str, Any], ttl_seconds: int = 86400 * 3):
        try:
            r = await self.get_redis()
            key = await self._hash_key(ANSWER_CACHE_PREFIX, query)
            await r.setex(key, ttl_seconds, json.dumps(data))
        except Exception as e:
            logger.warning(f"Error setting answer cache: {e}")
