import asyncio
from pathlib import Path
import json
import logging
import time
import uuid
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from jinja2 import Environment, FileSystemLoader

from shared.schemas.chat import (
    ActionLink,
    ChatActions,
    ChatContext,
    ChatRequest,
    ChatSyncResponse,
    CitationItem,
    TokenUsage,
)
from shared.settings import get_settings
from app.graph.graph import chat_graph
from app.graph.state import ChatState
from app.graph.nodes.guard_node import guard_node
from app.graph.nodes.hydrate_node import hydrate_node
from app.graph.nodes.route_node import route_node
from app.graph.nodes.clarify_node import clarify_node
from app.graph.nodes.retrieve_node import retrieve_node
from app.graph.nodes.grade_node import grade_node
from app.graph.nodes.finalize_node import finalize_node
from app.graph.support import should_offer_support_ticket
from app.llm.openai_compatible import OpenAICompatibleClient
from app.security.rate_limit import RateLimiter
from app.security.site_key import compute_visitor_hash, verify_site_key
from app.obs.metrics import CHAT_REQUESTS, FIRST_TOKEN_LATENCY, FULL_ANSWER_LATENCY, CONFIDENCE_RATINGS

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/v1", tags=["Chat"])
rate_limiter = RateLimiter()
llm_client = OpenAICompatibleClient()

prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
jinja_env = Environment(loader=FileSystemLoader(str(prompts_dir)))


def sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def generate_chat_sse(
    request_data: ChatRequest,
    site_key: str,
    visitor_hash: str,
    trace_id: str,
) -> AsyncGenerator[str, None]:
    start_time = time.time()
    first_token_emitted = False
    timings: dict = {}

    try:
        # Initial status
        yield sse_event("status", {"stage": "searching", "detail": "جست‌وجو در مستندات لیارا"})

        state: ChatState = {
            "conversation_id": request_data.conversation_id or "",
            "message": request_data.message,
            "host_context": request_data.context.model_dump() if request_data.context else {},
            "options": request_data.options.model_dump() if request_data.options else {},
            "site_key": site_key,
            "visitor_hash": visitor_hash,
            "trace_id": trace_id,
            "timings": {},
        }

        # 1. Guard check
        guard_update = await guard_node(state)
        state.update(guard_update)
        timings.update(state.get("timings", {}))

        # Handle shortcut / cached answer / unsafe refusal immediately
        if state.get("is_shortcut") or not state.get("guard_safe"):
            final_ans = state.get("final_answer") or state.get("shortcut_response") or ""
            yield sse_event("meta", {"conversation_id": state.get("conversation_id", ""), "message_id": 0, "trace_id": trace_id})
            
            # Stream shortcut tokens
            for chunk in [final_ans[i : i + 12] for i in range(0, len(final_ans), 12)]:
                if not first_token_emitted:
                    FIRST_TOKEN_LATENCY.observe(time.time() - start_time)
                    first_token_emitted = True
                yield sse_event("token", {"text": chunk})

            # Cached answers retain their citations in Redis, but this branch
            # bypasses the normal retrieval event. Emit the sources explicitly
            # so the widget can render the citation links for cached answers.
            cached_citations = [
                c.model_dump() if hasattr(c, "model_dump") else c
                for c in state.get("citations", [])
            ]
            if cached_citations:
                yield sse_event("citations", {"items": cached_citations})

            yield sse_event(
                "actions",
                {
                    "suggestions": state.get("suggestions", []),
                    "links": [
                        l.model_dump() if hasattr(l, "model_dump") else l
                        for l in state.get("action_links", [])
                    ],
                },
            )
            yield sse_event("done", {"confidence": "high", "tokens": {"prompt": 0, "completion": 0}, "cost_usd": 0.0})
            return

        # 2. Hydrate conversation state
        hydrate_update = await hydrate_node(state)
        state.update(hydrate_update)
        timings.update(state.get("timings", {}))

        # Emit meta event
        conv_id = state.get("conversation_id", "")
        yield sse_event("meta", {"conversation_id": conv_id, "message_id": 0, "trace_id": trace_id})

        # 3. Route user query
        route_update = await route_node(state)
        state.update(route_update)
        timings.update(state.get("timings", {}))

        action = state.get("action", "search")

        # 4. Handle Clarify
        if action == "clarify":
            clarify_update = await clarify_node(state)
            state.update(clarify_update)
            question_text = state.get("final_answer", "")
            
            for chunk in [question_text[i : i + 8] for i in range(0, len(question_text), 8)]:
                yield sse_event("token", {"text": chunk})

            actions_obj: dict = {}
            if state.get("clarify_action"):
                actions_obj["clarify"] = state["clarify_action"].model_dump()
            yield sse_event("actions", actions_obj)
            yield sse_event("done", {"confidence": "high", "tokens": {"prompt": 0, "completion": 0}, "cost_usd": 0.0})
            return

        # 5. Retrieve documentation context
        retrieve_update = await retrieve_node(state)
        state.update(retrieve_update)
        timings.update(state.get("timings", {}))

        citations_list = [
            c.model_dump() if hasattr(c, "model_dump") else c
            for c in state.get("citations", [])
        ]
        yield sse_event("status", {"stage": "reading", "sources": len(citations_list)})
        if citations_list:
            yield sse_event("citations", {"items": citations_list})

        # 6. Real-time Synthesis Token Streaming
        t_synth_start = time.time()
        packed_context = state.get("packed_context", "").strip()
        final_answer_parts: list = []

        if not packed_context:
            refusal_text = (
                "متأسفانه در مستندات رسمی لیارا اطلاعاتی درباره این مورد یافت نشد."
                + (
                    "\n\nبرای این مورد می‌توانید از طریق لینک زیر با پشتیبانی فنی لیارا در ارتباط باشید:\n"
                    "- [ثبت تیکت پشتیبانی در کنسول لیارا](https://console.liara.ir/tickets/create)"
                    if should_offer_support_ticket(state.get("message", ""))
                    else "\n\nلطفاً سؤال را با نام سرویس یا جزئیات خطا دقیق‌تر مطرح کنید."
                )
            )
            for chunk in [refusal_text[i : i + 15] for i in range(0, len(refusal_text), 15)]:
                if not first_token_emitted:
                    FIRST_TOKEN_LATENCY.observe(time.time() - start_time)
                    first_token_emitted = True
                yield sse_event("token", {"text": chunk})
            state["final_answer"] = refusal_text
            state["confidence"] = "low"
        else:
            synth_template = jinja_env.get_template("synthesize.jinja")
            rendered_synth_prompt = synth_template.render(
                user_query=state.get("message", ""),
                context=packed_context,
            )

            # Stream tokens directly from the configured LLM provider.
            async for token in llm_client.stream(
                messages=[{"role": "user", "content": rendered_synth_prompt}],
                model=settings.ai.SYNTHESIS_MODEL,
                temperature=0.1,
                max_tokens=1500,
            ):
                if not first_token_emitted:
                    FIRST_TOKEN_LATENCY.observe(time.time() - start_time)
                    first_token_emitted = True
                final_answer_parts.append(token)
                yield sse_event("token", {"text": token})

            state["final_answer"] = "".join(final_answer_parts)
            state["confidence"] = "high"

        timings["synthesize"] = round(time.time() - t_synth_start, 3)
        state["timings"] = timings

        # 7. Finalize (persisting in DB and caching in Redis)
        finalize_update = await finalize_node(state)
        state.update(finalize_update)

        # Actions event (suggestions, links)
        actions_obj = {
            "suggestions": state.get("suggestions", []),
            "links": [
                l.model_dump() if hasattr(l, "model_dump") else l
                for l in state.get("action_links", [])
            ],
        }
        yield sse_event("actions", actions_obj)

        # Done event
        confidence = state.get("confidence", "high")
        CONFIDENCE_RATINGS.labels(confidence=confidence).inc()
        prompt_tokens = state.get("tokens_prompt", 0)
        completion_tokens = state.get("tokens_completion", 0)
        cost_usd = state.get("cost_usd", 0.0)
        FULL_ANSWER_LATENCY.observe(time.time() - start_time)

        yield sse_event(
            "done",
            {
                "confidence": confidence,
                "tokens": {"prompt": prompt_tokens, "completion": completion_tokens},
                "cost_usd": cost_usd,
            },
        )
        CHAT_REQUESTS.labels(route=state.get("action", "search"), status="success").inc()

    except Exception as e:
        logger.error(f"Error during chat streaming generation: {e}", exc_info=True)
        CHAT_REQUESTS.labels(route="error", status="error").inc()
        yield sse_event("error", {"code": "internal_error", "message": "خطایی رخ داد. لطفاً دوباره تلاش کنید."})


@router.post("/chat")
async def chat_stream(
    request_data: ChatRequest,
    req: Request,
    site_key: str = Depends(verify_site_key),
):
    client_ip = req.client.host if req.client else "127.0.0.1"
    allowed, retry_after = await rate_limiter.check_rate_limit(
        ip=client_ip,
        conversation_id=request_data.conversation_id,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited", "retry_after": retry_after, "message": "تعداد درخواست‌های شما بیش از حد مجاز است."},
            headers={"Retry-After": str(retry_after or 30)},
        )

    user_agent = req.headers.get("user-agent", "")
    visitor_hash = compute_visitor_hash(client_ip, user_agent)
    trace_id = str(uuid.uuid4())

    return StreamingResponse(
        generate_chat_sse(request_data, site_key, visitor_hash, trace_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/sync", response_model=ChatSyncResponse)
async def chat_sync(
    request_data: ChatRequest,
    req: Request,
    site_key: str = Depends(verify_site_key),
):
    start_time = time.time()
    client_ip = req.client.host if req.client else "127.0.0.1"
    allowed, retry_after = await rate_limiter.check_rate_limit(
        ip=client_ip,
        conversation_id=request_data.conversation_id,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited", "retry_after": retry_after, "message": "Rate limit exceeded."},
            headers={"Retry-After": str(retry_after or 30)},
        )

    user_agent = req.headers.get("user-agent", "")
    visitor_hash = compute_visitor_hash(client_ip, user_agent)
    trace_id = str(uuid.uuid4())

    initial_state: ChatState = {
        "conversation_id": request_data.conversation_id or "",
        "message": request_data.message,
        "host_context": request_data.context.model_dump() if request_data.context else {},
        "options": request_data.options.model_dump() if request_data.options else {},
        "site_key": site_key,
        "visitor_hash": visitor_hash,
        "trace_id": trace_id,
        "timings": {},
    }

    final_state = await chat_graph.ainvoke(initial_state)
    latency_ms = int((time.time() - start_time) * 1000)

    citations = [
        CitationItem(**(c.model_dump() if hasattr(c, "model_dump") else c))
        for c in final_state.get("citations", [])
    ]
    actions = ChatActions(
        suggestions=final_state.get("suggestions", []),
        links=final_state.get("action_links", []),
        clarify=final_state.get("clarify_action"),
    )

    return ChatSyncResponse(
        conversation_id=final_state.get("conversation_id", ""),
        message_id=final_state.get("message_id", 0),
        trace_id=trace_id,
        content=final_state.get("final_answer", ""),
        citations=citations,
        actions=actions,
        confidence=final_state.get("confidence", "high"),
        tokens=TokenUsage(
            prompt=final_state.get("tokens_prompt", 0),
            completion=final_state.get("tokens_completion", 0),
        ),
        cost_usd=final_state.get("cost_usd", 0.0),
        latency_ms=latency_ms,
    )
