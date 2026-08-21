"""Initial schema with pgvector, pg_trgm, unaccent

Revision ID: 001
Revises: 
Create Date: 2025-02-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Enable required PostgreSQL extensions and immutable wrapper
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")

    op.execute("""
    CREATE OR REPLACE FUNCTION immutable_unaccent(text)
      RETURNS text AS
    $func$
      SELECT public.unaccent('public.unaccent', $1);
    $func$ LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT;
    """)

    # 2. Documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('repo_path', sa.Text(), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('nav_path', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('service_tag', sa.Text(), nullable=True),
        sa.Column('lang', sa.Text(), nullable=False, server_default='fa'),
        sa.Column('source', sa.Text(), nullable=False, server_default='repo'),
        sa.Column('alias_of', sa.BigInteger(), nullable=True),
        sa.Column('current_revision_id', sa.BigInteger(), nullable=True),
        sa.Column('simhash', sa.BigInteger(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, server_default='active'),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['alias_of'], ['documents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url')
    )
    op.create_index('ix_documents_service_tag', 'documents', ['service_tag'])

    # 3. Document Revisions table
    op.create_table(
        'document_revisions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.BigInteger(), nullable=False),
        sa.Column('content_hash', sa.Text(), nullable=False),
        sa.Column('markdown', sa.Text(), nullable=False),
        sa.Column('frontmatter', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('git_sha', sa.Text(), nullable=True),
        sa.Column('doc_version', sa.Text(), nullable=True),
        sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', 'content_hash', name='uq_doc_content_hash')
    )

    # 4. Chunks table
    op.execute("""
    CREATE TABLE chunks (
        id BIGSERIAL PRIMARY KEY,
        revision_id BIGINT NOT NULL REFERENCES document_revisions(id) ON DELETE CASCADE,
        document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        ordinal INT NOT NULL,
        anchor TEXT,
        heading_path TEXT[],
        text TEXT NOT NULL,
        embed_text TEXT NOT NULL,
        text_hash TEXT NOT NULL,
        token_count INT NOT NULL,
        has_code BOOLEAN NOT NULL DEFAULT false,
        code_langs TEXT[],
        lang TEXT NOT NULL DEFAULT 'fa',
        service_tag TEXT,
        embedding vector(1024),
        tsv tsvector GENERATED ALWAYS AS (
            to_tsvector('simple', immutable_unaccent(coalesce(text, '')))
        ) STORED,
        CONSTRAINT uq_rev_ordinal UNIQUE (revision_id, ordinal)
    );
    """)

    op.execute("CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);")
    op.execute("CREATE INDEX chunks_tsv_gin ON chunks USING gin (tsv);")
    op.execute("CREATE INDEX chunks_trgm ON chunks USING gin (text gin_trgm_ops);")
    op.execute("CREATE INDEX chunks_doc_rev ON chunks (document_id, revision_id);")
    op.execute("CREATE INDEX ix_chunks_service_tag ON chunks (service_tag);")
    op.execute("CREATE INDEX ix_chunks_text_hash ON chunks (text_hash);")

    # 5. Chunk Occurrences table
    op.create_table(
        'chunk_occurrences',
        sa.Column('chunk_id', sa.BigInteger(), nullable=False),
        sa.Column('document_id', sa.BigInteger(), nullable=False),
        sa.Column('anchor', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['chunk_id'], ['chunks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('chunk_id', 'document_id')
    )

    # 6. Embedding Cache table
    op.execute("""
    CREATE TABLE embedding_cache (
        text_hash TEXT PRIMARY KEY,
        model TEXT NOT NULL,
        embedding vector(1024) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    # 7. Sync Runs table
    op.create_table(
        'sync_runs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('trigger', sa.Text(), nullable=True),
        sa.Column('source', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, server_default='running'),
        sa.Column('from_git_sha', sa.Text(), nullable=True),
        sa.Column('to_git_sha', sa.Text(), nullable=True),
        sa.Column('pages_seen', sa.Integer(), server_default='0'),
        sa.Column('pages_changed', sa.Integer(), server_default='0'),
        sa.Column('chunks_written', sa.Integer(), server_default='0'),
        sa.Column('embed_tokens', sa.Integer(), server_default='0'),
        sa.Column('cost_usd', sa.Numeric(10, 4), server_default='0.0'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 8. URL Mapping Issues table
    op.create_table(
        'url_mapping_issues',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('repo_path', sa.Text(), nullable=True),
        sa.Column('guessed_url', sa.Text(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('resolved', sa.Boolean(), server_default='false'),
        sa.PrimaryKeyConstraint('id')
    )

    # 9. Conversations table
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('site_key', sa.Text(), nullable=False),
        sa.Column('visitor_hash', sa.Text(), nullable=True),
        sa.Column('lang', sa.Text(), nullable=True),
        sa.Column('profile', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('summary_upto_msg', sa.Integer(), server_default='0'),
        sa.Column('msg_count', sa.Integer(), server_default='0'),
        sa.Column('token_spend', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversations_site_key', 'conversations', ['site_key'])

    # 10. Messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), server_default='[]'),
        sa.Column('route', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('model', sa.Text(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), server_default='0'),
        sa.Column('cost_usd', sa.Numeric(10, 5), server_default='0.0'),
        sa.Column('latency_ms', sa.Integer(), server_default='0'),
        sa.Column('trace_id', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conversation_id', 'seq', name='uq_conv_seq')
    )
    op.create_index('ix_messages_conversation_id', 'messages', ['conversation_id'])

    # 11. Feedback table
    op.create_table(
        'feedback',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
        sa.Column('rating', sa.SmallInteger(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 12. Query Log table
    op.create_table(
        'query_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('query_norm', sa.Text(), nullable=True),
        sa.Column('lang', sa.Text(), nullable=True),
        sa.Column('route', sa.Text(), nullable=True),
        sa.Column('top_score', sa.Float(), nullable=True),
        sa.Column('n_results', sa.Integer(), server_default='0'),
        sa.Column('answered', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('query_log')
    op.drop_table('feedback')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('url_mapping_issues')
    op.drop_table('sync_runs')
    op.drop_table('embedding_cache')
    op.drop_table('chunk_occurrences')
    op.drop_table('chunks')
    op.drop_table('document_revisions')
    op.drop_table('documents')
    op.execute("DROP FUNCTION IF EXISTS immutable_unaccent(text);")
