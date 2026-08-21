import json
import logging
from pathlib import Path
from typing import Any, Dict
from jinja2 import Environment, FileSystemLoader
from app.graph.state import ChatState
from app.llm.openai_compatible import OpenAICompatibleClient
from shared.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

prompts_dir = Path(__file__).resolve().parent.parent.parent / "prompts"
jinja_env = Environment(loader=FileSystemLoader(str(prompts_dir)))
llm_client = OpenAICompatibleClient()


async def verify_node(state: ChatState) -> Dict[str, Any]:
    if state.get("is_shortcut") or not state.get("packed_context"):
        return {}

    draft_answer = state.get("draft_answer", "")
    packed_context = state.get("packed_context", "")

    template = jinja_env.get_template("verify.jinja")
    rendered_prompt = template.render(
        context=packed_context,
        answer=draft_answer,
    )

    try:
        resp = await llm_client.complete(
            messages=[{"role": "user", "content": rendered_prompt}],
            model=settings.ai.ROUTER_MODEL,
            temperature=0.0,
            max_tokens=800,
            json_mode=True,
        )
        raw_json = resp.content.strip()
        if raw_json.startswith("```"):
            raw_json = raw_json.strip("`").lstrip("json").strip()

        data = json.loads(raw_json)
        is_grounded = data.get("is_grounded", True)
        repaired_answer = data.get("repaired_answer") or draft_answer

        return {
            "final_answer": repaired_answer,
            "is_grounded": is_grounded,
            "confidence": "high" if is_grounded else "medium",
            "tokens_prompt": state.get("tokens_prompt", 0) + resp.prompt_tokens,
            "tokens_completion": state.get("tokens_completion", 0) + resp.completion_tokens,
            "cost_usd": state.get("cost_usd", 0.0) + resp.cost_usd,
        }
    except Exception as e:
        logger.warning(f"Verification check skipped due to error: {e}")
        return {
            "final_answer": draft_answer,
            "is_grounded": True,
            "confidence": state.get("confidence", "high"),
        }
