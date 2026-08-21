import asyncio
import logging
from arq import create_pool
from arq.connections import RedisSettings
from shared.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("indexer_cron")
settings = get_settings()


async def run_cron():
    logger.info("Starting indexer cron scheduler...")
    redis_pool = await create_pool(
        RedisSettings(
            host=settings.redis.REDIS_HOST,
            port=settings.redis.REDIS_PORT,
            password=settings.redis.REDIS_PASSWORD,
            database=settings.redis.REDIS_DB,
        )
    )

    tick = 0
    try:
        while True:
            # Every 30 minutes: sync_repo_incremental
            if tick % 30 == 0:
                logger.info("Enqueuing sync_repo_incremental")
                await redis_pool.enqueue_job("sync_repo_incremental", trigger="cron")

            # Daily (every 24h = 1440 min): maintenance_nightly & recall_canary
            if tick % 1440 == 0 and tick > 0:
                logger.info("Enqueuing maintenance_nightly and recall_canary")
                await redis_pool.enqueue_job("maintenance_nightly")
                await redis_pool.enqueue_job("recall_canary")

            # Weekly (every 7 days = 10080 min): docs_gap_report
            if tick % 10080 == 0 and tick > 0:
                logger.info("Enqueuing docs_gap_report")
                await redis_pool.enqueue_job("docs_gap_report")

            await asyncio.sleep(60)
            tick += 1
    except asyncio.CancelledError:
        logger.info("Cron scheduler stopped.")
    finally:
        await redis_pool.close()


if __name__ == "__main__":
    asyncio.run(run_cron())
