from contextlib import asynccontextmanager
import logging
import time
from typing import Optional
from fastapi import Depends, FastAPI, HTTPException, Header, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from arq import create_pool
from arq.connections import RedisSettings as ArqRedisSettings
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.settings import get_settings
from shared.schemas.search import SearchRequest, SearchResponse
from shared.schemas.document import DocumentResponse
from shared.schemas.admin import (
    AdminStatusResponse,
    ReindexRequest,
    RollbackRequest,
    SyncRequest,
    SyncRunResponse,
)
from app.db.session import get_db_session
from app.db.models import Document, DocumentRevision, Chunk, SyncRun, UrlMappingIssue
from app.pipeline.index import IndexPipeline
from app.search.hybrid import HybridSearchService
from app.jobs.tasks import sync_repo_incremental

logger = logging.getLogger("indexer")
settings = get_settings()

# Prometheus metrics
SEARCH_REQUESTS = Counter("indexer_search_requests_total", "Total search requests received")
SEARCH_LATENCY = Histogram("indexer_search_latency_seconds", "Search latency in seconds")
INDEX_PAGES_COUNT = Counter("indexer_pages_indexed_total", "Total pages indexed")

hybrid_search = HybridSearchService()
index_pipeline = IndexPipeline()


arq_pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global arq_pool
    logger.info("Starting indexer service...")
    arq_pool = await create_pool(
        ArqRedisSettings(
            host=settings.redis.REDIS_HOST,
            port=settings.redis.REDIS_PORT,
            password=settings.redis.REDIS_PASSWORD,
            database=settings.redis.REDIS_DB,
        )
    )
    yield
    if arq_pool:
        await arq_pool.close()
    logger.info("Shutting down indexer service...")


app = FastAPI(
    title="Liara Docs Indexer & Search API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def verify_internal_token(x_internal_token: Optional[str] = Header(None)):
    if not x_internal_token or x_internal_token != settings.security.INTERNAL_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal token",
        )
    return x_internal_token


async def verify_operator_token(x_operator_token: Optional[str] = Header(None)):
    if not x_operator_token or x_operator_token != settings.security.ADMIN_OPERATOR_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid operator token",
        )
    return x_operator_token


# --- Health & Metrics ---

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(session: AsyncSession = Depends(get_db_session)):
    try:
        await session.execute(select(func.now()))
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readyz check failed: {e}")
        return JSONResponse(status_code=503, content={"status": "degraded", "error": str(e)})


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# --- Search API ---

@app.post(
    "/internal/search",
    response_model=SearchResponse,
    dependencies=[Depends(verify_internal_token)],
)
async def internal_search(
    request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
):
    SEARCH_REQUESTS.inc()
    start_time = time.time()
    try:
        response = await hybrid_search.search(session, request)
        SEARCH_LATENCY.observe(time.time() - start_time)
        return response
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get(
    "/internal/documents/{doc_id}",
    response_model=DocumentResponse,
    dependencies=[Depends(verify_internal_token)],
)
async def get_document(
    doc_id: int,
    include_markdown: bool = Query(default=False, alias="include"),
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(Document).where(Document.id == doc_id)
    res = await session.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    resp = DocumentResponse.from_orm(doc)
    if include_markdown and doc.current_revision_id:
        rev_stmt = select(DocumentRevision.markdown).where(DocumentRevision.id == doc.current_revision_id)
        rev_res = await session.execute(rev_stmt)
        markdown = rev_res.scalar_one_or_none()
        resp.markdown = markdown

    return resp


@app.get(
    "/internal/documents/by-url",
    response_model=DocumentResponse,
    dependencies=[Depends(verify_internal_token)],
)
async def get_document_by_url(
    url: str = Query(..., description="Canonical URL"),
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(Document).where(Document.url == url)
    res = await session.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.from_orm(doc)


# --- Admin API ---

@app.post(
    "/admin/sync",
    dependencies=[Depends(verify_internal_token), Depends(verify_operator_token)],
)
async def trigger_sync(
    request: SyncRequest,
):
    global arq_pool
    try:
        if arq_pool:
            job = await arq_pool.enqueue_job(
                "sync_repo_incremental",
                trigger="manual",
                dry_run=request.dry_run,
                force_full=request.mode == "full",
            )
            return {"status": "enqueued", "job_id": job.job_id if job else None}
        else:
            raise HTTPException(status_code=503, detail="Job queue unavailable")
    except Exception as e:
        logger.error(f"Manual sync enqueue failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/admin/rollback",
    dependencies=[Depends(verify_internal_token), Depends(verify_operator_token)],
)
async def trigger_rollback(
    request: RollbackRequest,
    session: AsyncSession = Depends(get_db_session),
):
    success = await index_pipeline.rollback_document_revision(
        session=session,
        document_id=request.document_id,
        target_revision_id=request.revision_id,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Rollback failed. Invalid document or revision ID.")
    return {"status": "ok", "message": f"Document {request.document_id} rolled back to revision {request.revision_id}"}


@app.get(
    "/admin/status",
    response_model=AdminStatusResponse,
    dependencies=[Depends(verify_internal_token), Depends(verify_operator_token)],
)
async def get_admin_status(session: AsyncSession = Depends(get_db_session)):
    # 1. Corpus stats
    doc_count = (await session.execute(select(func.count(Document.id)))).scalar() or 0
    active_doc_count = (await session.execute(select(func.count(Document.id)).where(Document.status == "active"))).scalar() or 0
    # Count only chunks belonging to each document's active revision. Counting
    # every historical blue/green revision makes this number grow on every
    # re-index even when the document count is unchanged.
    chunk_count = (
        await session.execute(
            select(func.count(Chunk.id))
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.revision_id == Document.current_revision_id)
        )
    ).scalar() or 0

    # 2. Last sync runs
    sync_stmt = select(SyncRun).order_by(SyncRun.started_at.desc()).limit(5)
    sync_res = await session.execute(sync_stmt)
    sync_runs = [SyncRunResponse.from_orm(r) for r in sync_res.scalars()]

    # 3. Mapping issues count
    issues_count = (await session.execute(select(func.count(UrlMappingIssue.id)).where(UrlMappingIssue.resolved == False))).scalar() or 0

    return AdminStatusResponse(
        corpus_stats={
            "total_documents": doc_count,
            "active_documents": active_doc_count,
            "total_chunks": chunk_count,
        },
        index_generation=1,
        last_sync_runs=sync_runs,
        queue_depth=0,
        issues_count=issues_count,
    )
