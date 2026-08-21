import logging
from pathlib import Path
import time
from typing import Any, Dict
from jinja2 import Environment, FileSystemLoader
from app.graph.state import ChatState
from app.llm.openai_compatible import OpenAICompatibleClient
from app.graph.support import should_offer_support_ticket
from shared.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

prompts_dir = Path(__file__).resolve().parent.parent.parent / "prompts"
jinja_env = Environment(loader=FileSystemLoader(str(prompts_dir)))
llm_client = OpenAICompatibleClient()


async def synthesize_node(state: ChatState) -> Dict[str, Any]:
    t0 = time.time()
    if state.get("is_shortcut"):
        return {}

    packed_context = state.get("packed_context", "").strip()
    user_query = state.get("message", "")
    lang = state.get("lang", "fa")

    # If no context is found, keep the response self-contained. Offer support
    # only when the query explicitly indicates escalation is appropriate.
    if not packed_context:
        ticket_suffix = (
            "\n\nبرای این مورد می‌توانید از طریق لینک زیر با پشتیبانی فنی لیارا در ارتباط باشید:\n"
            "- [ثبت تیکت پشتیبانی در کنسول لیارا](https://console.liara.ir/tickets/create)"
            if should_offer_support_ticket(user_query)
            else "\n\nلطفاً سؤال را با نام سرویس یا جزئیات خطا دقیق‌تر مطرح کنید."
        )
        refusal_text = (
            "متأسفانه در مستندات رسمی لیارا اطلاعاتی درباره این مورد یافت نشد."
            + ticket_suffix
            if lang == "fa"
            else "Unfortunately, this information was not found in the official Liara documentation."
            + (
                "\n\nYou can contact Liara technical support here:\n"
                "- [Create Support Ticket](https://console.liara.ir/tickets/create)"
                if should_offer_support_ticket(user_query)
                else "\n\nPlease include the service name or exact error details and try again."
            )
        )
        timings = dict(state.get("timings") or {})
        timings["synthesize"] = round(time.time() - t0, 3)

        return {
            "draft_answer": refusal_text,
            "final_answer": refusal_text,
            "confidence": "low",
            "citations": [],
            "timings": timings,
        }

    template = jinja_env.get_template("synthesize.jinja")
    rendered_prompt = template.render(
        user_query=user_query,
        context=packed_context,
    )

    try:
        resp = await llm_client.complete(
            messages=[{"role": "user", "content": rendered_prompt}],
            model=settings.ai.SYNTHESIS_MODEL,
            temperature=0.1,
            max_tokens=1500,
        )

        timings = dict(state.get("timings") or {})
        timings["synthesize"] = round(time.time() - t0, 3)

        return {
            "draft_answer": resp.content,
            "final_answer": resp.content,
            "confidence": "high",
            "tokens_prompt": state.get("tokens_prompt", 0) + resp.prompt_tokens,
            "tokens_completion": state.get("tokens_completion", 0) + resp.completion_tokens,
            "cost_usd": state.get("cost_usd", 0.0) + resp.cost_usd,
            "timings": timings,
        }
    except Exception as e:
        logger.error(f"Synthesis failed: {e}", exc_info=True)
        fallback_msg = (
            "در حال حاضر به دلیل اختلال ارتباطی موقت، پاسخ‌دهی با مشکل مواجه شد. لطفاً سوال خود را مجدداً ارسال کنید."
            if lang == "fa"
            else "An error occurred while generating the answer. Please try again."
        )
        timings = dict(state.get("timings") or {})
        timings["synthesize"] = round(time.time() - t0, 3)

        return {
            "draft_answer": fallback_msg,
            "final_answer": fallback_msg,
            "confidence": "low",
            "timings": timings,
        }
