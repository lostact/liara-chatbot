from datetime import datetime, timezone, timedelta
import json
import logging
from typing import Any, Dict, Optional
import redis.asyncio as aioredis
from sqlalchemy import func, select, text, delete, update
from shared.settings import get_settings
from app.db.session import db_context
from app.db.models import Document, DocumentRevision, Chunk, SyncRun, UrlMappingIssue, QueryLog, Message
from app.sources.github import GitHubSource
from app.pipeline.index import IndexPipeline

logger = logging.getLogger(__name__)
settings = get_settings()


async def sync_repo_incremental(
    ctx: Dict[str, Any],
    trigger: str = "cron",
    dry_run: bool = False,
    force_full: bool = False,
) -> Dict[str, Any]:
    """
    Sync docs repo incrementally by checking git SHA difference.
    """
    logger.info(
        f"Starting sync_repo_incremental (trigger={trigger}, dry_run={dry_run}, force_full={force_full})"
    )
    gh = GitHubSource()
    indexer = IndexPipeline()

    # 1. Distributed lock via Redis to avoid concurrent sync jobs
    redis_client = aioredis.from_url(settings.redis.url)
    lock_acquired = await redis_client.set("lock:sync_repo", "1", nx=True, ex=7200)
    if not lock_acquired:
        logger.info("Another sync_repo job is currently running. Skipping.")
        await redis_client.aclose()
        return {"status": "already_running"}

    async with db_context() as session:
        # 2. Mark any orphaned 'running' sync runs from killed containers as 'interrupted'
        await session.execute(
            update(SyncRun)
            .where(SyncRun.status == "running")
            .values(
                status="interrupted",
                finished_at=datetime.now(timezone.utc),
                error={"message": "Process interrupted by container restart"},
            )
        )
        await session.commit()

        # 3. Get last successful sync run SHA
        stmt = (
            select(SyncRun)
            .where(SyncRun.status == "success")
            .order_by(SyncRun.finished_at.desc())
            .limit(1)
        )
        last_run = (await session.execute(stmt)).scalar_one_or_none()
        last_sha = last_run.to_git_sha if last_run else None

        # Create new sync_run record
        sync_run = SyncRun(
            trigger=trigger,
            source="github",
            status="running",
            from_git_sha=last_sha,
            started_at=datetime.now(timezone.utc),
        )
        session.add(sync_run)
        await session.commit()

        try:
            if force_full:
                changed_files = [rel_path for rel_path, _ in gh.enumerate_docs()]
            else:
                changed_files, current_sha = gh.get_changed_files_since(last_sha)
            current_sha = gh.get_current_sha()
            sync_run.to_git_sha = current_sha
            sync_run.pages_seen = len(changed_files)

            if dry_run:
                sync_run.status = "dry_run"
                sync_run.finished_at = datetime.now(timezone.utc)
                await session.flush()
                return {"status": "dry_run", "changed_files": len(changed_files)}

            pages_changed = 0
            chunks_written = 0

            for rel_path in changed_files:
                full_path = gh.local_dir / rel_path
                if not full_path.exists():
                    continue

                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    changed, reason = await indexer.index_single_document(
                        session=session,
                        repo_path=rel_path,
                        raw_markdown=content,
                        git_sha=current_sha,
                    )
                    if changed:
                        pages_changed += 1
                        sync_run.pages_changed = pages_changed
                    
                    # Commit immediately so each document is instantly live and searchable
                    await session.commit()
                except Exception as e:
                    await session.rollback()
                    logger.error(f"Failed to process file {rel_path}: {e}")
                    try:
                        issue = UrlMappingIssue(
                            repo_path=rel_path,
                            reason=f"Processing error: {str(e)}",
                        )
                        session.add(issue)
                        await session.commit()
                    except Exception:
                        await session.rollback()

            sync_run.pages_changed = pages_changed
            sync_run.status = "success"
            sync_run.finished_at = datetime.now(timezone.utc)
            await session.commit()

            # Bump index generation so search and answer caches automatically invalidate on updates
            if pages_changed > 0:
                new_gen = await redis_client.incr("index:generation")
                logger.info(f"Index updated ({pages_changed} pages changed). Bumped index generation to v{new_gen}.")
            
            logger.info(f"Sync completed successfully. {pages_changed}/{len(changed_files)} pages changed.")
            return {"status": "success", "pages_changed": pages_changed, "total_seen": len(changed_files)}

        except Exception as e:
            logger.error(f"Sync failed: {e}", exc_info=True)
            sync_run.status = "failed"
            sync_run.error = {"message": str(e)}
            sync_run.finished_at = datetime.now(timezone.utc)
            await session.commit()
            raise
        finally:
            await redis_client.delete("lock:sync_repo")
            await redis_client.aclose()


async def maintenance_nightly(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nightly maintenance:
    - Prune revisions older than 90 days not pointed to by current_revision_id
    - Vacuum/Analyze
    """
    logger.info("Running maintenance_nightly")
    async with db_context() as session:
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        
        # Prune non-current revisions older than 90 days
        stmt = (
            delete(DocumentRevision)
            .where(
                DocumentRevision.created_at < cutoff,
                DocumentRevision.id.notin_(
                    select(Document.current_revision_id).where(Document.current_revision_id.is_not(None))
                ),
            )
        )
        res = await session.execute(stmt)
        pruned_revs = res.rowcount

        # Vacuum analyze
        try:
            await session.execute(text("ANALYZE chunks;"))
            await session.execute(text("ANALYZE documents;"))
        except Exception as e:
            logger.warning(f"Analyze failed: {e}")

        logger.info(f"Maintenance finished. Pruned {pruned_revs} old revisions.")
        return {"pruned_revisions": pruned_revs}


async def docs_gap_report(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Weekly summary of unanswered or low-confidence queries for docs improvements.
    """
    logger.info("Generating docs_gap_report")
    async with db_context() as session:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        stmt = (
            select(QueryLog.query_norm, func.count(QueryLog.id).label("count"))
            .where(
                QueryLog.created_at >= cutoff,
                (QueryLog.answered.is_(False)) | (QueryLog.top_score < 0.75),
            )
            .group_by(QueryLog.query_norm)
            .order_by(text("count DESC"))
            .limit(50)
        )
        res = await session.execute(stmt)
        top_gaps = [{"query": r.query_norm, "count": r.count} for r in res.all()]
        logger.info(f"Docs gap report generated with {len(top_gaps)} gap queries.")
        return {"gap_queries": top_gaps}


async def recall_canary(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recall canary: tests fixed representative queries and measures recall.
    """
    logger.info("Running recall_canary")
    # Canary query suite
    canary_queries = [
        {"q": "نصب liara cli", "expected_tag": "cli"},
        {"q": "استقرار برنامه django", "expected_tag": "django"},
        {"q": "دیتابیس postgresql در لیارا", "expected_tag": "postgres"},
        {"q": "object storage s3 credentials", "expected_tag": "object-storage"},
        {"q": "تنظیم متغیر محیطی", "expected_tag": "paas"},
    ]
    
    hits = 0
    from app.search.hybrid import HybridSearchService
    from shared.schemas.search import SearchRequest

    search_svc = HybridSearchService()
    async with db_context() as session:
        for item in canary_queries:
            req = SearchRequest(query=item["q"], top_k=5)
            resp = await search_svc.search(session, req)
            if any(r.service_tag == item["expected_tag"] for r in resp.results):
                hits += 1

    recall = hits / len(canary_queries) if canary_queries else 1.0
    logger.info(f"Recall canary result: {hits}/{len(canary_queries)} ({recall * 100:.1f}%)")
    return {"recall_score": recall, "passed": recall >= 0.8}


from arq.connections import RedisSettings as ArqRedisSettings


async def worker_startup(ctx: Dict[str, Any]):
    redis_client = aioredis.from_url(settings.redis.url)
    await redis_client.delete("lock:sync_repo")
    await redis_client.aclose()
    logger.info("Worker started: cleared any leftover locks from previous crashed containers.")


class WorkerSettings:
    functions = [
        sync_repo_incremental,
        maintenance_nightly,
        docs_gap_report,
        recall_canary,
    ]
    on_startup = worker_startup
    redis_settings = ArqRedisSettings(
        host=settings.redis.REDIS_HOST,
        port=settings.redis.REDIS_PORT,
        password=settings.redis.REDIS_PASSWORD,
        database=settings.redis.REDIS_DB,
    )
    max_jobs = settings.indexer.INDEXER_WORKER_CONCURRENCY
    job_timeout = 7200  # 2 hours to allow full initial corpus indexing
