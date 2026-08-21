from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Conversation, Message
from app.db.session import db_context
from shared.schemas.chat import CitationItem

logger = logging.getLogger(__name__)


class ConversationStore:
    async def get_or_create_conversation(
        self,
        session: AsyncSession,
        conversation_id: Optional[str],
        site_key: str,
        visitor_hash: Optional[str] = None,
        initial_profile: Optional[Dict[str, Any]] = None,
    ) -> Conversation:
        if conversation_id:
            try:
                conv_uuid = uuid.UUID(conversation_id)
                stmt = select(Conversation).where(Conversation.id == conv_uuid)
                res = await session.execute(stmt)
                conv = res.scalar_one_or_none()
                if conv:
                    conv.last_activity_at = datetime.now(timezone.utc)
                    return conv
            except ValueError:
                pass

        # Create new conversation
        new_conv = Conversation(
            id=uuid.uuid4(),
            site_key=site_key,
            visitor_hash=visitor_hash,
            profile=initial_profile or {},
            created_at=datetime.now(timezone.utc),
            last_activity_at=datetime.now(timezone.utc),
        )
        session.add(new_conv)
        await session.flush()
        return new_conv

    async def get_recent_messages(
        self,
        session: AsyncSession,
        conversation_id: uuid.UUID,
        limit: int = 8,
    ) -> List[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.seq.desc())
            .limit(limit)
        )
        res = await session.execute(stmt)
        messages = list(reversed(res.scalars().all()))
        return messages

    async def append_message(
        self,
        session: AsyncSession,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        citations: Optional[List[Dict[str, Any]]] = None,
        route: Optional[str] = None,
        confidence: Optional[float] = None,
        model: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
        latency_ms: int = 0,
        trace_id: Optional[str] = None,
    ) -> Message:
        # Determine next seq
        seq_stmt = select(func.coalesce(func.max(Message.seq), 0)).where(Message.conversation_id == conversation_id)
        next_seq = (await session.execute(seq_stmt)).scalar() + 1

        msg = Message(
            conversation_id=conversation_id,
            seq=next_seq,
            role=role,
            content=content,
            citations=citations or [],
            route=route,
            confidence=confidence,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            trace_id=trace_id,
            created_at=datetime.now(timezone.utc),
        )
        session.add(msg)

        # Update conversation msg_count & token_spend
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(
                msg_count=Conversation.msg_count + 1,
                token_spend=Conversation.token_spend + (prompt_tokens + completion_tokens),
                last_activity_at=datetime.now(timezone.utc),
            )
        )
        await session.flush()
        return msg

    async def delete_conversation(self, session: AsyncSession, conversation_id: uuid.UUID) -> bool:
        stmt = delete(Conversation).where(Conversation.id == conversation_id)
        res = await session.execute(stmt)
        return res.rowcount > 0
