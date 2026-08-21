import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.db.models import Conversation, Message
from app.memory.store import ConversationStore
from app.security.site_key import verify_site_key
from shared.schemas.conversation import ConversationResponse, MessageItem

router = APIRouter(prefix="/v1/conversations", tags=["Conversations"])
conv_store = ConversationStore()


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation_history(
    conversation_id: str,
    session: AsyncSession = Depends(get_db_session),
    site_key: str = Depends(verify_site_key),
):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    stmt = select(Conversation).where(
        Conversation.id == conv_uuid,
        Conversation.site_key == site_key,
    )
    res = await session.execute(stmt)
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Load messages
    msg_stmt = (
        select(Message)
        .where(Message.conversation_id == conv_uuid)
        .order_by(Message.seq.asc())
    )
    msg_res = await session.execute(msg_stmt)
    messages = [MessageItem.from_orm(m) for m in msg_res.scalars()]

    resp = ConversationResponse.from_orm(conv)
    resp.messages = messages
    return resp


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_db_session),
    site_key: str = Depends(verify_site_key),
):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    deleted = await conv_store.delete_conversation(session, conv_uuid)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"status": "ok", "message": "Conversation deleted successfully"}
