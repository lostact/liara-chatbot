from typing import Any, Dict
from app.graph.state import ChatState


async def clarify_node(state: ChatState) -> Dict[str, Any]:
    clarify_action = state.get("clarify_action")
    if clarify_action:
        question = clarify_action.question
    else:
        question = "لطفاً برای راهنمایی دقیق‌تر، سرویس یا فریم‌ورک مورد نظرتان را مشخص کنید."

    return {
        "final_answer": question,
        "confidence": "high",
    }
