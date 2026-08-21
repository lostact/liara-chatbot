from datetime import datetime
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    FetchedValue,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    url = Column(Text, unique=True, nullable=False, index=True)
    repo_path = Column(Text, nullable=True)
    title = Column(Text, nullable=False)
    nav_path = Column(ARRAY(Text), nullable=True)
    service_tag = Column(Text, nullable=True, index=True)
    lang = Column(Text, nullable=False, default="fa")
    source = Column(Text, nullable=False, default="repo")
    alias_of = Column(BigInteger, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    current_revision_id = Column(BigInteger, nullable=True)
    simhash = Column(BigInteger, nullable=True)
    status = Column(Text, nullable=False, default="active")  # active | removed | excluded
    first_seen_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    revisions = relationship("DocumentRevision", back_populates="document", cascade="all, delete-orphan", foreign_keys="DocumentRevision.document_id")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan", foreign_keys="Chunk.document_id")


class DocumentRevision(Base):
    __tablename__ = "document_revisions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    document_id = Column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    content_hash = Column(Text, nullable=False)
    markdown = Column(Text, nullable=False)
    frontmatter = Column(JSONB, nullable=False, default=dict)
    git_sha = Column(Text, nullable=True)
    doc_version = Column(Text, nullable=True)
    indexed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    document = relationship("Document", back_populates="revisions", foreign_keys=[document_id])
    chunks = relationship("Chunk", back_populates="revision", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("document_id", "content_hash", name="uq_doc_content_hash"),
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    revision_id = Column(BigInteger, ForeignKey("document_revisions.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    ordinal = Column(Integer, nullable=False)
    anchor = Column(Text, nullable=True)
    heading_path = Column(ARRAY(Text), nullable=True)
    text = Column(Text, nullable=False)
    embed_text = Column(Text, nullable=False)
    text_hash = Column(Text, nullable=False, index=True)
    token_count = Column(Integer, nullable=False)
    has_code = Column(Boolean, nullable=False, default=False)
    code_langs = Column(ARRAY(Text), nullable=True)
    lang = Column(Text, nullable=False, default="fa")
    service_tag = Column(Text, nullable=True, index=True)
    embedding = Column(Vector(1024), nullable=True)
    tsv = Column(TSVECTOR, server_default=FetchedValue())

    document = relationship("Document", back_populates="chunks", foreign_keys=[document_id])
    revision = relationship("DocumentRevision", back_populates="chunks", foreign_keys=[revision_id])

    __table_args__ = (
        UniqueConstraint("revision_id", "ordinal", name="uq_rev_ordinal"),
    )


class ChunkOccurrence(Base):
    __tablename__ = "chunk_occurrences"

    chunk_id = Column(BigInteger, ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True)
    document_id = Column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    anchor = Column(Text, nullable=True)


class EmbeddingCache(Base):
    __tablename__ = "embedding_cache"

    text_hash = Column(Text, primary_key=True)
    model = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trigger = Column(Text, nullable=True)  # cron | manual | webhook
    source = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="running")  # running | success | failed
    from_git_sha = Column(Text, nullable=True)
    to_git_sha = Column(Text, nullable=True)
    pages_seen = Column(Integer, default=0)
    pages_changed = Column(Integer, default=0)
    chunks_written = Column(Integer, default=0)
    embed_tokens = Column(Integer, default=0)
    cost_usd = Column(Numeric(10, 4), default=0.0)
    started_at = Column(DateTime(timezone=True), default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(JSONB, nullable=True)


class UrlMappingIssue(Base):
    __tablename__ = "url_mapping_issues"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    repo_path = Column(Text, nullable=True)
    guessed_url = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    resolved = Column(Boolean, default=False)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_key = Column(Text, nullable=False, index=True)
    visitor_hash = Column(Text, nullable=True)
    lang = Column(Text, nullable=True)
    profile = Column(JSONB, nullable=False, default=dict)
    summary = Column(Text, nullable=True)
    summary_upto_msg = Column(Integer, default=0)
    msg_count = Column(Integer, default=0)
    token_spend = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=func.now())
    last_activity_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.seq")


class Message(Base):
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    role = Column(Text, nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)
    citations = Column(JSONB, default=list)
    route = Column(Text, nullable=True)
    confidence = Column(Numeric(3, 2), nullable=True)
    model = Column(Text, nullable=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    cost_usd = Column(Numeric(10, 5), default=0.0)
    latency_ms = Column(Integer, default=0)
    trace_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())

    conversation = relationship("Conversation", back_populates="messages")
    feedback = relationship("Feedback", back_populates="message", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("conversation_id", "seq", name="uq_conv_seq"),
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = Column(SmallInteger, nullable=False)  # 1 or -1
    reason = Column(Text, nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())

    message = relationship("Message", back_populates="feedback")


class QueryLog(Base):
    __tablename__ = "query_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(UUID(as_uuid=True), nullable=True)
    query_norm = Column(Text, nullable=True)
    lang = Column(Text, nullable=True)
    route = Column(Text, nullable=True)
    top_score = Column(Float, nullable=True)
    n_results = Column(Integer, default=0)
    answered = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
