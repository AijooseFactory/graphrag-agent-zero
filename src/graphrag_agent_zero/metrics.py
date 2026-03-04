from .logger import setup_logger

logger = setup_logger("graphrag_agent_zero.metrics")

# Optional dependency for enterprise observability
try:
    from prometheus_client import Counter, Histogram, Gauge, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    
    class DummyMetric:
        def inc(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    def Counter(*args, **kwargs): return DummyMetric()
    def Histogram(*args, **kwargs): return DummyMetric()
    def Gauge(*args, **kwargs): return DummyMetric()
    def start_http_server(*args, **kwargs): pass


class GraphRAGMetrics:
    """
    Prometheus Telemetry Registry for GraphRAG.
    Gracefully degrades to DummyMetrics if 'prometheus_client' is not installed.
    """
    def __init__(self):
        self.extraction_duration = Histogram('graphrag_extraction_duration_seconds', 'Time spent extracting entities')
        self.query_latency = Histogram('graphrag_query_latency_seconds', 'Neo4j query latency', ['operation'])
        self.entity_count = Counter('graphrag_entity_count_total', 'Total entities extracted')
        self.relationship_count = Counter('graphrag_relationship_count_total', 'Total relationships extracted')
        self.neo4j_errors = Counter('graphrag_neo4j_connection_errors_total', 'Neo4j connection errors')
        self.fallback_total = Counter('graphrag_fallback_total', 'Times vector fallback was used')
        self.retry_total = Counter('graphrag_retry_total', 'Total Neo4j query retries')
        self.circuit_breaker_state = Gauge('graphrag_circuit_breaker_state', '0=Closed, 1=Open')
        self.dlq_size = Gauge('graphrag_dead_letter_queue_size', 'Number of items in DLQ')
        
        self.server_started = False

    def start_server(self, port=8089):
        if PROMETHEUS_AVAILABLE and not self.server_started:
            try:
                start_http_server(port)
                self.server_started = True
                logger.info(f"Prometheus metrics server started on port {port}")
            except Exception as e:
                logger.warning(f"Failed to start Prometheus server: {e}")
        elif not PROMETHEUS_AVAILABLE:
            logger.debug("prometheus_client not installed, metrics disabled.")

# Global metrics registry
metrics = GraphRAGMetrics()
