# GraphRAG for Agent Zero - Project Roadmap

This document outlines the history, current state, and future direction of the Hybrid GraphRAG extension for Agent Zero.

## 📜 Project History

### v0.1.1 - 2026-03-02
- **Persistent Architecture**: Migrated all GraphRAG extensions to the persistent `usr/extensions/` volume, ensuring configurations and patches survive Docker container recreations.
- **Dynamic Hooking**: Safely monkey-patched Agent Zero's memory directly in Python's memory runtime via `agent_init`.
- **Neo4j Deletion Synchronization**: Added explicit hooks so that deleting memories in Agent Zero also automatically deletes the corresponding orphaned nodes in Neo4j.
- **Robust Installation**: Bypassed Kali Linux's `externally-managed-environment` protections using the isolated virtual environment pip.

### v0.1.0 - 2026-03-01
- **Initial Release**: Basic hybridization retrieval combining vector semantics and graph topologies.
- **Safe Cypher Enforcement**: Allowlisted query engine to prevent injection attacks.
- **Zero-Trust**: Hard-capped graph traversal limits (hops, nodes).

---

## 🎯 Improvement Recommendations for Hybrid GraphRAG for Agent Zero (v2.0)

Based on the current architecture, implementation, and v0.1.1 features, here are prioritized improvement suggestions:

---

### 🔥 High Priority (High Impact, Feasible)

| Area | Improvement | Rationale |
|------|-------------|----------|
| **Caching Layer** | Add LRU + TTL cache for frequently-queried entity subgraphs and packed context | Reduces Neo4j query load; repeated SPEP operations become near-instant |
| **Entity Resolution** | Implement deduplication for similar entities (exact/normalized first, optional fuzzy) | Prevents graph noise where `John Smith` and `J. Smith` become separate nodes |
| **Batch Indexing** | Add bulk memory ingestion mode (initial build + reindex) | Indexing thousands of memories one-by-one is slow; batch mode accelerates setup |
| **Metrics & Observability** | Add Prometheus/OpenTelemetry metrics | Track latency, cache hit rate, fallback/no-op rate, entity/edge counts, Neo4j health |
| **Hybrid NER Pipeline** | Two-tier extraction: fast NER first, LLM for relations/complex entities | Reduces LLM token costs for paid usage while preserving quality |
| **Memory Graph Viewer** | Obsidian-style graph view for memories/entities/relationships | Lets users visually explore Agent memories and graph links (search, filter, click-to-view) |
| **Structured Logging** | JSON-structured logs with correlation IDs, request tracing, and log levels | Essential for debugging distributed operations; enables log aggregation (ELK, Loki) |
| **Error Classification** | Categorize errors (transient, permanent, partial) with recovery strategies | Enables intelligent retry vs fail-fast decisions; improves user experience |

---

### 🚀 Medium Priority (Significant Enhancement)

| Area | Improvement | Rationale |
|------|-------------|----------|
| **Temporal Relationships** | Add time-stamped edges (e.g., `WORKED_ON` from `2024-01` to `2024-06`) | Enables “what changed last week” queries; supports audits and change tracking |
| **Graph Analytics API** | Centrality, community detection, shortest-path endpoints | Identifies key connectors and high-impact nodes in a corpus/codebase |
| **Async Batch Operations** | Fully async batch processing with progress callbacks | Handles large corpus ingestion without blocking; improves UX for long runs |
| **Circuit Breaker Pattern** | Implement circuit breaker for Neo4j connections with auto-recovery | Prevents cascade failures; enables graceful degradation when Neo4j is unhealthy |
| **Retry with Backoff** | Exponential backoff retry for transient Neo4j/LLM errors | Handles temporary network blips without manual intervention |
| **Dead Letter Queue** | Queue for failed entity extractions with manual replay | Prevents data loss; enables debugging and reprocessing of failed operations |
| **Audit Logging** | Compliance-ready audit trail for graph mutations and queries | Required for regulated industries; tracks who changed what and when |

---

### 💡 Lower Priority (Nice to Have)

| Area | Improvement | Rationale |
|------|-------------|----------|
| **Multi-GraphDB Support** | Abstract `GraphConnector` interface (Neo4j, Memgraph, FalkorDB) | Reduces vendor lock-in; supports lighter edge deployments |
| **Graph Versioning** | Add snapshot/branching for graph state | Enables rollback and experimental extraction branches |
| **Schema Validation** | Enforce entity/relationship schemas with validation | Prevents malformed entities; improves consistency across extractions |
| **Error Context Preservation** | Capture full context on errors for debugging | Includes memory content, entity ID, query, and stack trace for post-mortem analysis |
| **Graceful Degradation UI** | Dashboard showing fallback/no-op mode status | Operators can see when GraphRAG is degraded vs fully operational |

---

### 🛡️ Robust Error Handling Architecture

#### Error Classification System
```python
class GraphRAGError(Exception):
    """Base exception for GraphRAG errors"""
    pass

class TransientError(GraphRAGError):
    """Temporary failures - retry recommended"""
    retry_after: int = None
    max_retries: int = 3

class PermanentError(GraphRAGError):
    """Unrecoverable failures - fail fast"""
    pass

class PartialSuccessError(GraphRAGError):
    """Partial completion - log and continue"""
    succeeded: int
    failed: int
    failed_items: list[str]
```

#### Circuit Breaker for Neo4j
```python
class Neo4jCircuitBreaker:
    STATES = ['closed', 'open', 'half_open']
    
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
    
    async def execute(self, operation):
        if self.state == 'open':
            if self._should_attempt_recovery():
                self.state = 'half_open'
            else:
                raise CircuitOpenError("Neo4j circuit breaker is open")
        # ... retry logic
```

#### Retry with Exponential Backoff
```python
async def with_retry(operation, max_retries=3, base_delay=1.0):
    for attempt in range(max_retries):
        try:
            return await operation()
        except TransientError as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            await asyncio.sleep(delay)
```

---

### 📊 Structured Logging Framework

#### Log Structure (JSON)
```json
{
  "timestamp": "2026-03-02T16:14:39.123Z",
  "level": "INFO",
  "correlation_id": "req-abc123",
  "component": "graphrag_agent_zero",
  "operation": "entity_extraction",
  "memory_id": "mem-xyz789",
  "entity_count": 5,
  "duration_ms": 234,
  "neo4j_query_time_ms": 45,
  "cache_hit": false,
  "fallback_mode": false
}
```

#### Log Levels
| Level | Usage |
|-------|-------|
| DEBUG | Detailed extraction steps, Cypher queries |
| INFO | Successful operations, cache hits/misses, timings |
| WARNING | Fallback mode, retry attempts, partial success |
| ERROR | Failed extractions, Neo4j errors, LLM errors |
| CRITICAL | Complete GraphRAG shutdown, data corruption |

---

### 📈 Enhanced Observability Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│  GraphRAG Metrics (Prometheus format)                               │
├─────────────────────────────────────────────────────────────────────┤
│  • graphrag_extraction_duration_seconds                             │
│  • graphrag_query_latency_seconds                                   │
│  • graphrag_entity_count_total                                      │
│  • graphrag_relationship_count_total                                │
│  • graphrag_neo4j_connection_errors_total                           │
│  • graphrag_cache_hit_ratio                                         │
│  • graphrag_fallback_total                                          │
│  • graphrag_noop_neo4j_down_total                                   │
│  • graphrag_retry_total                    ← NEW                    │
│  • graphrag_circuit_breaker_state           ← NEW                    │
│  • graphrag_dead_letter_queue_size          ← NEW                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 📋 Proposed v0.2.0 Roadmap

```
v0.2.0 - Performance, Cost Control, Reliability & Observability
├── Caching Layer (LRU + TTL)
├── Entity Deduplication (exact/normalized, optional fuzzy)
├── Batch Ingestion Mode
├── Prometheus Metrics Endpoint
├── Hybrid NER Pipeline (tiered extraction)
├── Memory Graph Viewer (Obsidian-style)
├── Structured Logging (JSON + correlation IDs)      ← NEW
├── Error Classification (transient/permanent/partial) ← NEW
├── Circuit Breaker for Neo4j                         ← NEW
├── Retry with Exponential Backoff                    ← NEW
└── Dead Letter Queue for failed extractions          ← NEW
```

---

### 🤔 Why Error Handling & Logging Are Critical

| Benefit | Impact |
|---------|--------|
| **Error Classification** | Enables intelligent recovery—retry transient errors, fail fast on permanent ones |
| **Structured Logging** | Correlation IDs allow tracing a request through the entire pipeline |
| **Circuit Breaker** | Prevents cascade failures when Neo4j is unhealthy |
| **Retry with Backoff** | Handles temporary blips without manual intervention |
| **Dead Letter Queue** | Ensures no data loss—failed extractions can be debugged and reprocessed |
| **Audit Logging** | Essential for compliance in regulated industries (legal, healthcare, finance) |

---

### 📝 Implementation Priority for Error Handling

| Phase | Components | Est. Effort |
|-------|-----------|-------------|
| **Phase 1** | Structured logging, Error classification | 2-3 days |
| **Phase 2** | Circuit breaker, Retry with backoff | 2-3 days |
| **Phase 3** | Dead letter queue, Audit logging | 3-4 days |
| **Phase 4** | Graceful degradation dashboard | 1-2 days |

**Total estimated effort: 8-12 days** for complete error handling and logging implementation.
