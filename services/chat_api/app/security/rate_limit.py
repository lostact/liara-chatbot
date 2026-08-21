import time
from typing import Optional, Tuple
import redis.asyncio as aioredis
from shared.settings import get_settings

settings = get_settings()


class RateLimiter:
    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self._redis = redis_client

    async def get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.redis.url)
        return self._redis

    async def check_rate_limit(
        self,
        ip: str,
        conversation_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[int]]:
        """
        Check rate limits using sliding window log in Redis.
        Returns (allowed: bool, retry_after_seconds: Optional[int]).
        """
        try:
            r = await self.get_redis()
            now = time.time()
            pipe = r.pipeline()

            # 1. IP burst limit: 6 requests per 60 seconds
            ip_burst_key = f"rl:ip:burst:{ip}"
            pipe.zremrangebyscore(ip_burst_key, 0, now - 60)
            pipe.zadd(ip_burst_key, {str(now): now})
            pipe.zcard(ip_burst_key)
            pipe.expire(ip_burst_key, 70)

            # 2. IP hourly limit: 30 requests per 3600 seconds
            ip_hourly_key = f"rl:ip:hour:{ip}"
            pipe.zremrangebyscore(ip_hourly_key, 0, now - 3600)
            pipe.zadd(ip_hourly_key, {str(now): now})
            pipe.zcard(ip_hourly_key)
            pipe.expire(ip_hourly_key, 3700)

            # 3. Conversation hourly limit: 40 requests per 3600 seconds
            conv_hourly_key = None
            if conversation_id:
                conv_hourly_key = f"rl:conv:hour:{conversation_id}"
                pipe.zremrangebyscore(conv_hourly_key, 0, now - 3600)
                pipe.zadd(conv_hourly_key, {str(now): now})
                pipe.zcard(conv_hourly_key)
                pipe.expire(conv_hourly_key, 3700)

            results = await pipe.execute()

            # Inspect results
            burst_count = results[2]
            if burst_count > settings.security.RATE_LIMIT_IP_BURST:
                return False, 10

            hour_count = results[6]
            if hour_count > settings.security.RATE_LIMIT_IP_HOURLY:
                return False, 120

            if conv_hourly_key:
                conv_count = results[10]
                if conv_count > settings.security.RATE_LIMIT_CONV_HOURLY:
                    return False, 120

            return True, None

        except Exception:
            # Fallback open or minimal logging on Redis unavailability
            return True, None
