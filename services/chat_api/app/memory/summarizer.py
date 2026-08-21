import logging
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Conversation, Message
from app.llm.openai_compatible import OpenAICompatibleClient
from shared.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ConversationSummarizer:
    def __init__(self, llm_client: Optional[OpenAICompatibleClient] = None):
        self.llm = llm_client or OpenAICompatibleClient()

    async def maybe_update_summary(
        self,
        session: AsyncSession,
        conversation: Conversation,
    ):
        """
        Refresh rolling summary every 6 messages using the cheap router model.
        """
        # Check if 6 new messages accumulated since last summary
        if conversation.msg_count - conversation.summary_upto_msg < 6:
            return

        stmt = (
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.seq > conversation.summary_upto_msg,
            )
            .order_by(Message.seq.asc())
        )
        res = await session.execute(stmt)
        messages_to_summarize = res.scalars().all()

        if not messages_to_summarize:
            return

        chat_transcript = "\n".join([f"{m.role}: {m.content}" for m in messages_to_summarize])
        current_summary = conversation.summary or "None"

        prompt = (
            "You are a concise conversation summarizer. Maintain a rolling summary of technical context and user questions.\n"
            f"Existing summary: {current_summary}\n\n"
            f"New messages to incorporate:\n{chat_transcript}\n\n"
            "Provide a concise summary (under 120 words in Persian/English) of the user's goals, technologies mentioned, and resolved/unresolved issues."
        )

        try:
            resp = await self.llm.complete(
                messages=[{"role": "user", "content": prompt}],
                model=settings.ai.ROUTER_MODEL,
                temperature=0.1,
                max_tokens=250,
            )
            new_summary = resp.content.strip()
            max_seq = max(m.seq for m in messages_to_summarize)

            conversation.summary = new_summary
            conversation.summary_upto_msg = max_seq
            await session.flush()
            logger.info(f"Updated summary for conversation {conversation.id} up to seq {max_seq}")
        except Exception as e:
            logger.warning(f"Failed to update conversation summary: {e}")
