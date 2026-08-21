import time
from typing import Any, Dict
from app.graph.state import ChatState
from app.security.guard import check_input_guard
from app.security.pii import scrub_pii
from app.retrieval.cache import RedisCache
from shared.text import detect_language

answer_cache = RedisCache()


async def guard_node(state: ChatState) -> Dict[str, Any]:
    t0 = time.time()
    raw_message = state.get("message", "")
    scrubbed_message = scrub_pii(raw_message)
    lang = state.get("options", {}).get("lang", "auto")
    if lang == "auto":
        lang = detect_language(scrubbed_message)

    guard_res = check_input_guard(scrubbed_message, lang=lang)

    if not guard_res.is_safe:
        return {
            "message": scrubbed_message,
            "lang": lang,
            "guard_safe": False,
            "is_shortcut": True,
            "shortcut_response": guard_res.shortcut_response or guard_res.rejection_reason,
            "final_answer": guard_res.shortcut_response or guard_res.rejection_reason,
            "confidence": "high",
            "action": "refuse",
        }

    if guard_res.shortcut_response:
        return {
            "message": scrubbed_message,
            "lang": lang,
            "guard_safe": True,
            "is_shortcut": True,
            "shortcut_response": guard_res.shortcut_response,
            "shortcut_links": guard_res.shortcut_links,
            "final_answer": guard_res.shortcut_response,
            "confidence": "high",
            "action": guard_res.shortcut_type or "answer_from_context",
        }

    # 4. Check exact answer cache for repeated queries (<3ms response)
    cached_ans = await answer_cache.get_cached_answer(scrubbed_message)
    timings = dict(state.get("timings") or {})
    timings["guard"] = round(time.time() - t0, 3)

    if cached_ans:
        return {
            "message": scrubbed_message,
            "lang": lang,
            "guard_safe": True,
            "is_shortcut": True,
            "shortcut_response": cached_ans.get("answer", ""),
            "citations": cached_ans.get("citations", []),
            "suggestions": cached_ans.get("suggestions", []),
            "action_links": cached_ans.get("action_links", []),
            "final_answer": cached_ans.get("answer", ""),
            "confidence": cached_ans.get("confidence", "high"),
            "action": "cached_answer",
            "timings": timings,
        }

    return {
        "message": scrubbed_message,
        "lang": lang,
        "guard_safe": True,
        "is_shortcut": False,
        "timings": timings,
    }
