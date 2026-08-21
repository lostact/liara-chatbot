import time
from typing import Any, Dict
from app.db.session import db_context
from app.graph.state import ChatState
from app.memory.store import ConversationStore
from app.memory.profile import UserProfileExtractor

conv_store = ConversationStore()
profile_extractor = UserProfileExtractor()


async def hydrate_node(state: ChatState) -> Dict[str, Any]:
    t0 = time.time()
    conv_id_str = state.get("conversation_id")
    site_key = state.get("site_key", "pk_live_docs_liara_ir")
    visitor_hash = state.get("visitor_hash")
    host_context = state.get("host_context") or {}
    message = state.get("message", "")

    async with db_context() as session:
        conversation = await conv_store.get_or_create_conversation(
            session=session,
            conversation_id=conv_id_str,
            site_key=site_key,
            visitor_hash=visitor_hash,
        )

        recent_db_msgs = await conv_store.get_recent_messages(session, conversation.id, limit=8)
        recent_messages = [
            {"role": m.role, "content": m.content, "seq": m.seq}
            for m in recent_db_msgs
        ]

        # Extract/merge profile
        updated_profile = await profile_extractor.extract_and_merge_profile(
            conversation=conversation,
            user_message=message,
            host_context=host_context,
        )

        timings = dict(state.get("timings") or {})
        timings["hydrate"] = round(time.time() - t0, 3)

        return {
            "conversation_id": str(conversation.id),
            "summary": conversation.summary or "",
            "profile": updated_profile,
            "recent_messages": recent_messages,
            "retrieval_loop_count": 0,
            "timings": timings,
        }
