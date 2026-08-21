from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    message_id: int
    rating: int = Field(..., ge=-1, le=1)  # 1 for thumbs up, -1 for thumbs down
    reason: Optional[str] = None
    comment: Optional[str] = None


class FeedbackResponse(FeedbackCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
