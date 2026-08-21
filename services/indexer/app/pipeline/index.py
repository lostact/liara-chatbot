from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, update, func, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from shared.text import compute_simhash, detect_language
from app.db.models import Document, DocumentRevision, Chunk, ChunkOccurrence
from app.pipeline.clean import is_rejected_page
from app.pipeline.extract import extract_document
from app.pipeline.dedupe import compute_content_hash, find_near_duplicate
from app.pipeline.chunk import MarkdownChunker
from app.pipeline.embed import EmbeddingProvider
from app.sources.github import map_repo_path_to_url, resolve_service_tag

logger = logging.getLogger(__name__)


class IndexPipeline:
    def __init__(self, chunker: Optional[MarkdownChunker] = None, embedder: Optional[EmbeddingProvider] = None):
        self.chunker = chunker or MarkdownChunker()
        self.embedder = embedder or EmbeddingProvider()

    async def index_single_document(
        self,
        session: AsyncSession,
        repo_path: str,
        raw_markdown: str,
        git_sha: Optional[str] = None,
        doc_version: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Processes a single document: extraction, cleaning, dedupe, chunking, embedding, blue/green revision swap.
        Returns (changed: bool, reason: str).
        """
        canonical_url, nav_path = map_repo_path_to_url(repo_path)
        service_tag = resolve_service_tag(repo_path, canonical_url)

        # 1. Extraction
        extracted = extract_document(raw_markdown, default_title=repo_path)

        # 2. Cleaning / Rejection checks
        rejected, reject_reason = is_rejected_page(extracted.cleaned_markdown, extracted.frontmatter)
        if rejected:
            # Mark document as excluded if it exists
            stmt = select(Document).where(Document.url == canonical_url)
            doc_res = await session.execute(stmt)
            existing_doc = doc_res.scalar_one_or_none()
            if existing_doc:
                existing_doc.status = "excluded"
                existing_doc.last_seen_at = datetime.now(timezone.utc)
            return False, f"rejected: {reject_reason}"

        # 3. Content hash check (exact deduplication)
        content_hash = compute_content_hash(extracted.cleaned_markdown)
        simhash_val = compute_simhash(extracted.cleaned_markdown)
        doc_lang = extracted.frontmatter.get("lang") or detect_language(extracted.cleaned_markdown)

        # Find or create Document record
        stmt = select(Document).where(Document.url == canonical_url)
        doc_res = await session.execute(stmt)
        document = doc_res.scalar_one_or_none()

        if not document:
            document = Document(
                url=canonical_url,
                repo_path=repo_path,
                title=extracted.title,
                nav_path=nav_path,
                service_tag=service_tag,
                lang=doc_lang,
                simhash=simhash_val,
                status="active",
            )
            session.add(document)
            await session.flush()
        else:
            document.title = extracted.title
            document.nav_path = nav_path
            document.service_tag = service_tag
            document.lang = doc_lang
            document.simhash = simhash_val
            document.status = "active"
            document.last_seen_at = datetime.now(timezone.utc)

        # Check near duplicate (SimHash)
        alias_canonical_id = await find_near_duplicate(session, simhash_val, current_doc_id=document.id)
        document.alias_of = alias_canonical_id

        # Check if latest revision already matches this content hash
        if document.current_revision_id:
            rev_stmt = select(DocumentRevision).where(DocumentRevision.id == document.current_revision_id)
            rev_res = await session.execute(rev_stmt)
            current_rev = rev_res.scalar_one_or_none()
            if current_rev and current_rev.content_hash == content_hash:
                # Content unchanged, skip re-chunking and re-embedding
                return False, "unchanged"

        # A previous run may have successfully created this revision but failed
        # to update the document pointer (or the pointer may have been rolled
        # back to an older revision). Reuse it instead of inserting the same
        # (document_id, content_hash) pair again.
        existing_rev_stmt = select(DocumentRevision).where(
            DocumentRevision.document_id == document.id,
            DocumentRevision.content_hash == content_hash,
        )
        existing_rev = (await session.execute(existing_rev_stmt)).scalar_one_or_none()
        if existing_rev:
            was_current = document.current_revision_id == existing_rev.id
            document.current_revision_id = existing_rev.id
            return (not was_current), "reused_existing_revision"

        # 4. Create new DocumentRevision (Blue/Green staging)
        # Use an upsert-style insert as a second line of defense if another
        # worker creates the same revision between the lookup above and this
        # insert. The sync job normally uses a Redis lock, but the database
        # constraint must remain safe on restarts and manual job overlap.
        revision_insert = (
            pg_insert(DocumentRevision)
            .values(
                document_id=document.id,
                content_hash=content_hash,
                markdown=extracted.cleaned_markdown,
                frontmatter=extracted.frontmatter,
                git_sha=git_sha,
                doc_version=doc_version,
                indexed_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_nothing(index_elements=["document_id", "content_hash"])
            .returning(DocumentRevision.id)
        )
        revision_result = await session.execute(revision_insert)
        new_revision_id = revision_result.scalar_one_or_none()

        if new_revision_id is None:
            # A concurrent insert won the race. It is now safe to use the
            # committed revision and avoid emitting a per-file IntegrityError.
            existing_rev = (
                await session.execute(existing_rev_stmt)
            ).scalar_one_or_none()
            if not existing_rev:
                raise RuntimeError(
                    "Document revision conflict occurred but the existing revision "
                    "could not be loaded"
                )
            was_current = document.current_revision_id == existing_rev.id
            document.current_revision_id = existing_rev.id
            return (not was_current), "reused_existing_revision"

        new_rev = await session.get(DocumentRevision, new_revision_id)
        if not new_rev:
            raise RuntimeError("Inserted document revision could not be loaded")

        # 5. Chunking
        raw_chunks = self.chunker.chunk_document(
            doc_title=extracted.title,
            markdown=extracted.cleaned_markdown,
            service_tag=service_tag,
            doc_lang=doc_lang,
        )

        if not raw_chunks:
            return False, "no chunks generated"

        # 6. Embedding with cache
        hash_text_tuples = [(c.text_hash, c.embed_text) for c in raw_chunks]
        embeddings_map = await self.embed_embeds(session, hash_text_tuples)

        # 7. Write new Chunks
        for raw_c in raw_chunks:
            emb = embeddings_map.get(raw_c.text_hash)
            chunk = Chunk(
                revision_id=new_rev.id,
                document_id=document.id,
                ordinal=raw_c.ordinal,
                anchor=raw_c.anchor,
                heading_path=raw_c.heading_path,
                text=raw_c.text,
                embed_text=raw_c.embed_text,
                text_hash=raw_c.text_hash,
                token_count=raw_c.token_count,
                has_code=raw_c.has_code,
                code_langs=raw_c.code_langs,
                lang=raw_c.lang,
                service_tag=raw_c.service_tag,
                embedding=emb,
            )
            session.add(chunk)

        await session.flush()

        # 8. Atomic switch of current_revision_id
        document.current_revision_id = new_rev.id
        return True, "indexed"

    async def embed_embeds(
        self,
        session: AsyncSession,
        hash_text_tuples: List[tuple[str, str]],
    ) -> Dict[str, List[float]]:
        return await self.embedder.get_or_create_embeddings(session, hash_text_tuples)

    async def rollback_document_revision(
        self,
        session: AsyncSession,
        document_id: int,
        target_revision_id: int,
    ) -> bool:
        """Roll back a document to a previous revision."""
        stmt = select(DocumentRevision).where(
            DocumentRevision.id == target_revision_id,
            DocumentRevision.document_id == document_id,
        )
        res = await session.execute(stmt)
        target_rev = res.scalar_one_or_none()
        if not target_rev:
            return False

        doc_stmt = select(Document).where(Document.id == document_id)
        doc_res = await session.execute(doc_stmt)
        doc = doc_res.scalar_one_or_none()
        if not doc:
            return False

        doc.current_revision_id = target_revision_id
        await session.commit()
        return True
