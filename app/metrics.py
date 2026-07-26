from prometheus_client import Counter, Gauge, Histogram

#How long the moderation takes for every doc
MODERATION_LATENCY = Histogram(
    "moderation_latency_seconds",
    "Latency of the OpenAI moderation gate per document"
)

#how long AI takes to read and return
EXTRACTION_LATENCY = Histogram(
    "extraction_latency_seconds",
    "Latency of the vision-model extraction call per document"
)

#Cost - Cumulative
TOKEN_COST_USD = Counter(
    "token_cost_usd_total",
    "Cumulative USD spend on vision extraction tokens"
)

#throughput and auto-approval rate
DOCS_INGESTED = Counter(
    "docs_ingested_total",
    "Documents ingested, labelled by terminal ingest status",
    ["status"]
)

#auto approvedd
AUTO_APPROVALS = Counter(
    "auto_approvals_total",
    "Documents fully auto-approved with no human review"
)

#reviewed by human
REVIEWS_COMPLETED = Counter(
    "reviews_completed_total",
    "Documents approved by a human reviewer"
)

#Reviews pending
PENDING_REVIEW_GAUGE = Gauge(
    "pending_review_documents",
    "Documents currently sitting in the human review queue"
)


THROUGHPUT_DPM = Gauge(
    "throughput_docs_per_minute",
    "Documents ingested per minute, measured over the last batch",
)