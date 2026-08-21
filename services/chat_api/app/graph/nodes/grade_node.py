import json
import logging
from pathlib import Path
import time
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


async def grade_node(state: ChatState) -> Dict[str, Any]:
    t0 = time.time()
    packed_context = state.get("packed_context", "")
    if not packed_context:
        return {
            "is_sufficient": False,
            "missing_aspects": ["no_docs_found"],
        }

    template = jinja_env.get_template("grade.jinja")
    rendered_prompt = template.render(
        user_query=state.get("message", ""),
        context=packed_context,
    )

    try:
        resp = await llm_client.complete(
            messages=[{"role": "user", "content": rendered_prompt}],
            model=settings.ai.ROUTER_MODEL,
            temperature=0.1,
            max_tokens=250,
            json_mode=True,
        )
        raw_json = resp.content.strip()
        if raw_json.startswith("```"):
            raw_json = raw_json.strip("`").lstrip("json").strip()

        data = json.loads(raw_json)
        is_sufficient = data.get("sufficient", True)
        missing = data.get("missing_aspects", [])
        expansion_queries = data.get("expansion_queries", [])

        # Update search queries if expansion suggested
        search_queries = list(state.get("search_queries", []))
        for eq in expansion_queries:
            if eq not in search_queries:
                search_queries.append(eq)

        timings = dict(state.get("timings") or {})
        timings["grade"] = round(time.time() - t0, 3)

        return {
            "is_sufficient": is_sufficient,
            "missing_aspects": missing,
            "search_queries": search_queries,
            "tokens_prompt": state.get("tokens_prompt", 0) + resp.prompt_tokens,
            "tokens_completion": state.get("tokens_completion", 0) + resp.completion_tokens,
            "cost_usd": state.get("cost_usd", 0.0) + resp.cost_usd,
            "timings": timings,
        }
    except Exception as e:
        logger.error(f"Error in grade_node: {e}")
        timings = dict(state.get("timings") or {})
        timings["grade"] = round(time.time() - t0, 3)
        return {
            "is_sufficient": True,
            "missing_aspects": [],
            "timings": timings,
        }
