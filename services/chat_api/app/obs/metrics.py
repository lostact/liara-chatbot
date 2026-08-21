from prometheus_client import Counter, Histogram

CHAT_REQUESTS = Counter(
    "chat_requests_total",
    "Total chat requests received",
    ["route", "status"],
)

FIRST_TOKEN_LATENCY = Histogram(
    "chat_first_token_latency_seconds",
    "Latency to first streaming token in seconds",
    buckets=[0.2, 0.5, 0.8, 1.2, 2.0, 3.0, 5.0, 10.0],
)

FULL_ANSWER_LATENCY = Histogram(
    "chat_full_answer_latency_seconds",
    "Total latency to generate complete answer in seconds",
    buckets=[1.0, 2.0, 4.0, 6.0, 9.0, 12.0, 18.0, 30.0],
)

TOKEN_USAGE = Counter(
    "chat_token_usage_total",
    "Total LLM tokens consumed",
    ["model", "type"],  # type: prompt | completion
)

ESTIMATED_COST_USD = Counter(
    "chat_cost_usd_total",
    "Estimated total LLM cost in USD",
    ["model"],
)

CONFIDENCE_RATINGS = Counter(
    "chat_confidence_total",
    "Total responses by confidence rating",
    ["confidence"],  # high | medium | low
)

CACHE_HITS = Counter(
    "chat_cache_hits_total",
    "Total cache hits",
    ["cache_type"],  # answer | retrieval
)
