import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx
from shared.settings import get_settings
from app.llm.budget import estimate_cost
from app.obs.metrics import ESTIMATED_COST_USD, TOKEN_USAGE

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMResponse:
    def __init__(
        self,
        content: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
    ):
        self.content = content
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.cost_usd = cost_usd


class OpenAICompatibleClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        proxy: Optional[str] = None,
    ):
        self.api_key = api_key if api_key is not None else settings.ai.llm_api_key
        self.base_url = (base_url or settings.ai.llm_base_url).rstrip("/")
        self.proxy = proxy if proxy is not None else settings.ai.llm_proxy_url
        self.proxy = self.proxy or None

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1500,
        json_mode: bool = False,
    ) -> LLMResponse:
        target_model = model or settings.ai.ROUTER_MODEL
        headers = self._get_headers()
        
        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=45.0, proxy=self.proxy) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code >= 400:
                    logger.error(
                        f"[OpenAI-compatible Chat Error] Status: {resp.status_code}, "
                        f"Model: {target_model}, Response: {resp.text}"
                    )
                resp.raise_for_status()
                data = resp.json()

                choice = data["choices"][0]
                content = choice["message"]["content"]
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                actual_model = data.get("model", target_model)

                cost = estimate_cost(actual_model, prompt_tokens, completion_tokens)
                TOKEN_USAGE.labels(model=actual_model, type="prompt").inc(prompt_tokens)
                TOKEN_USAGE.labels(model=actual_model, type="completion").inc(completion_tokens)
                ESTIMATED_COST_USD.labels(model=actual_model).inc(cost)

                return LLMResponse(
                    content=content,
                    model=actual_model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=cost,
                )
            except Exception as e:
                logger.error(f"OpenAI-compatible call failed for model {target_model}: {e}")
                # Fallback chain for synthesis model
                if (
                    target_model == settings.ai.SYNTHESIS_MODEL
                    and settings.ai.SYNTHESIS_FALLBACK_MODEL
                    and settings.ai.SYNTHESIS_FALLBACK_MODEL != target_model
                ):
                    logger.info(f"Retrying with fallback model: {settings.ai.SYNTHESIS_FALLBACK_MODEL}")
                    return await self.complete(
                        messages=messages,
                        model=settings.ai.SYNTHESIS_FALLBACK_MODEL,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        json_mode=json_mode,
                    )
                raise

    async def stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> AsyncGenerator[str, None]:
        target_model = model or settings.ai.SYNTHESIS_MODEL
        headers = self._get_headers()
        
        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=60.0, proxy=self.proxy) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data_obj = json.loads(data_str)
                            delta = data_obj["choices"][0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                yield token
                        except Exception:
                            continue
