from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.db.models import Feedback, Message
from app.security.site_key import verify_site_key
from shared.schemas.feedback import FeedbackCreate, FeedbackResponse

router = APIRouter(prefix="/v1/feedback", tags=["Feedback"])


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    feedback_in: FeedbackCreate,
    session: AsyncSession = Depends(get_db_session),
    site_key: str = Depends(verify_site_key),
):
    # Verify message exists
    msg_stmt = select(Message).where(Message.id == feedback_in.message_id)
    msg_res = await session.execute(msg_stmt)
    msg = msg_res.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    feedback = Feedback(
        message_id=feedback_in.message_id,
        rating=feedback_in.rating,
        reason=feedback_in.reason,
        comment=feedback_in.comment,
        created_at=datetime.now(timezone.utc),
    )
    session.add(feedback)
    await session.commit()
    await session.refresh(feedback)

    return FeedbackResponse.from_orm(feedback)
