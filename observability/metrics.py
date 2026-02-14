"""
Prometheus Metrics - Production-grade observability
"""
from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry

# Create registry
metrics_registry = CollectorRegistry()

# ============================================================================
# HTTP Metrics
# ============================================================================

http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=metrics_registry
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=metrics_registry
)

# ============================================================================
# Query Processing Metrics
# ============================================================================

query_requests_total = Counter(
    'query_requests_total',
    'Total query requests',
    ['tenant_id', 'cached'],
    registry=metrics_registry
)

query_duration_seconds = Histogram(
    'query_duration_seconds',
    'Query processing duration',
    ['tenant_id'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=metrics_registry
)

# ============================================================================
# LLM Metrics
# ============================================================================

llm_requests_total = Counter(
    'llm_requests_total',
    'Total LLM API requests',
    ['provider', 'status'],
    registry=metrics_registry
)

llm_tokens_used_total = Counter(
    'llm_tokens_used_total',
    'Total tokens consumed',
    ['provider'],
    registry=metrics_registry
)

llm_request_duration_seconds = Histogram(
    'llm_request_duration_seconds',
    'LLM request duration',
    ['provider'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=metrics_registry
)

# ============================================================================
# Circuit Breaker Metrics
# ============================================================================

circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['service'],
    registry=metrics_registry
)

circuit_breaker_failures_total = Counter(
    'circuit_breaker_failures_total',
    'Total circuit breaker failures',
    ['service'],
    registry=metrics_registry
)

# ============================================================================
# Cache Metrics
# ============================================================================

cache_hits_total = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['type'],  # semantic, exact
    registry=metrics_registry
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['type'],
    registry=metrics_registry
)

cache_hit_similarity = Histogram(
    'cache_hit_similarity',
    'Semantic cache hit similarity scores',
    buckets=[0.90, 0.92, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99, 1.0],
    registry=metrics_registry
)

# ============================================================================
# Retrieval Metrics
# ============================================================================

retrieval_documents_retrieved = Histogram(
    'retrieval_documents_retrieved',
    'Number of documents retrieved',
    ['strategy'],
    buckets=[1, 3, 5, 10, 20, 50],
    registry=metrics_registry
)

retrieval_duration_seconds = Histogram(
    'retrieval_duration_seconds',
    'Retrieval duration in seconds',
    ['strategy'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
    registry=metrics_registry
)

# ============================================================================
# Answer Quality Metrics
# ============================================================================

answer_confidence = Histogram(
    'answer_confidence',
    'Answer confidence scores',
    ['tenant_id'],
    buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0],
    registry=metrics_registry
)

answer_validation_failures = Counter(
    'answer_validation_failures',
    'Total answer validation failures (triggers retry)',
    ['tenant_id'],
    registry=metrics_registry
)

# ============================================================================
# Rate Limiting Metrics
# ============================================================================

rate_limit_exceeded_total = Counter(
    'rate_limit_exceeded_total',
    'Total rate limit exceeded events',
    ['identifier'],
    registry=metrics_registry
)

# ============================================================================
# Document Ingestion Metrics
# ============================================================================

documents_ingested_total = Counter(
    'documents_ingested_total',
    'Total documents ingested',
    ['tenant_id', 'file_type'],
    registry=metrics_registry
)

document_ingestion_duration_seconds = Histogram(
    'document_ingestion_duration_seconds',
    'Document ingestion duration',
    ['file_type'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0],
    registry=metrics_registry
)

chunks_created_total = Counter(
    'chunks_created_total',
    'Total chunks created from documents',
    ['tenant_id'],
    registry=metrics_registry
)

# ============================================================================
# System Info
# ============================================================================

app_info = Info(
    'app_info',
    'Application information',
    registry=metrics_registry
)

# Set app info
from core.config import settings
app_info.info({
    'version': settings.VERSION,
    'environment': settings.ENVIRONMENT,
    'project_name': settings.PROJECT_NAME
})