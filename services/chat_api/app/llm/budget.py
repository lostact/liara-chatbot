from typing import Dict, Tuple

# Approximate pricing per 1M tokens (USD). Unknown providers/models use the
# conservative fallback rates below.
MODEL_PRICING: Dict[str, Tuple[float, float]] = {
    # model: (prompt_price_per_m, completion_price_per_m)
    "xiaomi/mimo-v2.5": (0.05, 0.20),
    "xiaomi/mimo-v2-flash": (0.05, 0.20),
    "google/gemini-2.5-flash": (0.075, 0.30),
    "deepseek/deepseek-v4-flash-0731": (0.10, 0.30),
    "google/gemini-2.0-flash-001": (0.10, 0.40),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.00),
    "baai/bge-m3": (0.01, 0.0),
    "openai/text-embedding-3-large": (0.13, 0.0),
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Calculate estimated cost in USD for a completion call.
    """
    prompt_rate, completion_rate = MODEL_PRICING.get(model, (0.50, 1.50))
    cost = (prompt_tokens / 1_000_000.0) * prompt_rate + (completion_tokens / 1_000_000.0) * completion_rate
    return round(cost, 6)
