import json
import logging
from pathlib import Path
import time
from typing import Any, Dict
from jinja2 import Environment, FileSystemLoader
from app.graph.state import ChatState
from app.llm.openai_compatible import OpenAICompatibleClient
from app.graph.support import clean_suggestions
from shared.settings import get_settings
from shared.schemas.chat import ClarifyAction, ClarifyChoice

logger = logging.getLogger(__name__)
settings = get_settings()

prompts_dir = Path(__file__).resolve().parent.parent.parent / "prompts"
jinja_env = Environment(loader=FileSystemLoader(str(prompts_dir)))
llm_client = OpenAICompatibleClient()


def _extract_search_query(data: Dict[str, Any], user_query: str) -> str:
    """Return the router's canonical query or the original query as fallback."""
    search_query = data.get("search_query")
    if isinstance(search_query, str) and search_query.strip():
        return search_query.strip()
    return user_query.strip()


async def route_node(state: ChatState) -> Dict[str, Any]:
    t0 = time.time()
    if state.get("is_shortcut"):
        return {}

    user_query = state.get("message", "")
    template = jinja_env.get_template("route.jinja")
    rendered_prompt = template.render(
        profile=state.get("profile", {}),
        host_context=state.get("host_context", {}),
        summary=state.get("summary", ""),
        recent_messages=state.get("recent_messages", []),
        user_query=user_query,
    )

    try:
        resp = await llm_client.complete(
            messages=[{"role": "user", "content": rendered_prompt}],
            model=settings.ai.ROUTER_MODEL,
            temperature=0.1,
            max_tokens=400,
            json_mode=True,
        )

        raw_json = resp.content.strip()
        if raw_json.startswith("```"):
            raw_json = raw_json.strip("`").lstrip("json").strip()

        data = json.loads(raw_json)
        action = data.get("action", "search")
        intent = data.get("intent", "general_doc_query")
        search_query = _extract_search_query(data, user_query)
        steps = data.get("steps") or []
        suggestions = clean_suggestions(data.get("suggestions") or [])
        confidence = float(data.get("confidence", 0.9))

        clarify_action = None
        if action == "clarify" and data.get("clarify_question"):
            choices = [
                ClarifyChoice(
                    id=c.get("id", str(i)),
                    label=c.get("label", ""),
                    value=c.get("value", ""),
                )
                for i, c in enumerate(data.get("clarify_choices", []))
            ]
            clarify_action = ClarifyAction(
                question=data["clarify_question"],
                choices=choices,
            )

        timings = dict(state.get("timings") or {})
        timings["route"] = round(time.time() - t0, 3)

        return {
            "action": action,
            "intent": intent,
            "search_queries": [search_query],
            "steps": steps,
            "suggestions": suggestions,
            "clarify_action": clarify_action,
            "route_confidence": confidence,
            "tokens_prompt": state.get("tokens_prompt", 0) + resp.prompt_tokens,
            "tokens_completion": state.get("tokens_completion", 0) + resp.completion_tokens,
            "cost_usd": state.get("cost_usd", 0.0) + resp.cost_usd,
            "timings": timings,
        }

    except Exception as e:
        logger.error(f"Error in route_node: {e}. Defaulting to standard search.")
        timings = dict(state.get("timings") or {})
        timings["route"] = round(time.time() - t0, 3)
        return {
            "action": "search",
            "intent": "fallback_search",
            "search_queries": [user_query],
            "suggestions": [],
            "route_confidence": 0.5,
            "timings": timings,
        }
