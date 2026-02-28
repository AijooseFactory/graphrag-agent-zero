# GraphRAG for Agent Zero - Implementation Plan

**Version:** 1.1  
**Created:** 2026-02-27  
**Updated:** 2026-02-27  
**Author:** Mac (Agent Zero) for George Freeney Jr.  
**Status:** Draft - Pending Approval After BENCHMARK_PLAN.md Complete  
**Related:** [BENCHMARK_PLAN.md](./BENCHMARK_PLAN.md)

---

## Upstream PR Safety

**This is the foundational constraint for all implementation work.**

### Non-Negotiable Requirements

| Requirement | Description | Verification Method |
|-------------|-------------|---------------------|
| **GraphRAG OFF by default** | Feature flag `GRAPH_RAG_ENABLED=false` in `.env` | Default config check |
| **No core patches** | No modifications to `/a0/python/` core files | Diff against upstream |
| **No auto-install** | Docker and Neo4j are NOT auto-installed | Code review for `subprocess` calls |
| **Graceful fallback** | System works without Neo4j | Golden test: Neo4j down scenario |
| **Minimal dependencies** | New dependencies are optional | `requirements.txt` conditional imports |
| **Reproducible tests** | Tests pass in CI without special setup | CI pipeline run |

### Graceful Degradation Behavior

```
IF Neo4j not configured OR connection fails:
  LOG WARNING: "GraphRAG unavailable, falling back to vector-only"
  USE vector_memory_only mode
  CONTINUE normal operation
  NO user-facing errors
```

### Dependency Isolation

```python
# All GraphRAG imports must be wrapped:
try:
    from .graphrag_hybrid_retrieve import hybrid_retrieve
    GRAPH_RAG_AVAILABLE = True
except ImportError:
    GRAPH_RAG_AVAILABLE = False
```

---

## Deliverables Split by PR

### PR #1: MVP (Minimum Viable Product)

**Scope:** Basic hybrid retrieval with entity extraction and graph expansion.

| Deliverable | Description | DoD |
|-------------|-------------|-----|
| `neo4j_connector.py` | Connection management with graceful fallback | Connects or returns None without error |
| `graphrag_hybrid_retrieve.py` | Vector seed + entity pinning + graph expand | Returns context with provenance |
| `SAFE_CYPHER_TEMPLATES.md` | Allowlisted query templates only | All queries parameterized |
| Feature flag integration | `GRAPH_RAG_ENABLED` toggle | Works in both states |
| Unit tests | Core functionality tests | 100% pass rate |
| Golden test | Baseline equivalence test | GraphRAG disabled = baseline behavior |

**PR #1 Acceptance Criteria:**
- [ ] All golden tests pass
- [ ] No regression when GraphRAG disabled
- [ ] Entity extraction produces stable IDs
- [ ] Graceful fallback verified
- [ ] Benchmark shows improvement on multi-hop questions

---

### PR #2: Migration & Provenance

**Scope:** Entity backfill, provenance tracking, idempotency.

| Deliverable | Description | DoD |
|-------------|-------------|-----|
| Entity extraction pipeline | LLM-based extraction with deduplication | Entity Resolution Audit passes |
| Provenance tracking | Source document + line tracking | 100% of edges have source |
| Idempotent upsert | Re-run produces identical state | Hash comparison before/after re-run |
| Entity resolution | `same_as` / `possible_same_as` relationships | No unresolved ambiguities |
| Backfill script | Existing knowledge → graph | All existing docs processed |

**PR #2 Acceptance Criteria:**
- [ ] Entity Resolution Audit passes (see BENCHMARK_PLAN.md)
- [ ] Re-run produces identical graph state
- [ ] All entities have stable IDs
- [ ] 100% provenance on relationships

---

### PR #3: Optimization & Benchmarking

**Scope:** Performance tuning, caching, comprehensive benchmarks.

| Deliverable | Description | DoD |
|-------------|-------------|-----|
| Query caching | Neo4j query result cache | Cache hit rate ≥60% |
| Performance budgets | Latency within 2x baseline | p95 measurement in CI |
| Benchmark automation | CI-integrated benchmark runner | Automated score comparison |
| Tuning documentation | Parameter recommendations | Documented for common scenarios |

**PR #3 Acceptance Criteria:**
- [ ] p95_retrieval_pipeline_ms within 2x baseline
- [ ] Cache hit rate ≥60%
- [ ] Benchmark report auto-generated
- [ ] All BENCHMARK_PLAN.md acceptance criteria met

---

## Phase 1: Foundation (PR #1)

### 1.1 Configuration & Environment

**Files:**
- `/a0/usr/projects/mac/graphrag/config/graphrag_config.py`

```python
@dataclass
class GraphRAGConfig:
    enabled: bool = False  # OFF by default
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    max_hops: int = 2
    max_nodes: int = 50
    cache_ttl_seconds: int = 300
    
    # Latency budgets (measured after baseline)
    p95_graph_query_ms_target: Optional[int] = None
    p95_retrieval_pipeline_multiplier: float = 2.0
```

**Validation:**
- Config loads without error when `GRAPH_RAG_ENABLED=false`
- No required fields when disabled

---

### 1.2 Neo4j Connector

**File:** `/a0/usr/projects/mac/graphrag/lib/neo4j_connector.py`

```python
class Neo4jConnector:
    def __init__(self, config: GraphRAGConfig):
        self.config = config
        self._driver = None
        self._available = False
        
    async def connect(self) -> bool:
        """Attempt connection, return True if successful."""
        if not self.config.enabled:
            return False
        try:
            self._driver = AsyncGraphDatabase.driver(
                self.config.neo4j_uri,
                auth=(self.config.neo4j_user, self.config.neo4j_password)
            )
            await self._driver.verify_connectivity()
            self._available = True
            return True
        except Exception as e:
            logger.warning(f"GraphRAG unavailable: {e}")
            self._available = False
            return False
    
    async def execute_query(
        self, 
        template_name: str, 
        params: dict
    ) -> Tuple[List[dict], int]:
        """
        Execute allowlisted query template.
        Returns (results, latency_ms).
        """
        if not self._available:
            return [], 0
        
        template = SAFE_CYPHER_TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"Unknown template: {template_name}")
        
        start = time.perf_counter()
        result = await self._driver.execute_query(template, params)
        latency_ms = int((time.perf_counter() - start) * 1000)
        
        return [dict(r) for r in result], latency_ms
```

**Error Handling:**
- All exceptions caught and logged
- Returns empty results on failure
- Sets `_available = False` on connection issues

---

### 1.3 Safe Cypher Templates

**File:** `/a0/usr/projects/mac/graphrag/planning/SAFE_CYPHER_TEMPLATES.md`

**Template Requirements:**
1. All queries MUST use parameterized values (`$param`)
2. No string concatenation
3. Bounded depth (max 2 hops)
4. Bounded results (LIMIT always present)
5. Read-only operations only

**Template Format:**

```yaml
# Template definition
get_entity_neighbors:
  description: "Get entities connected to a seed entity"
  query: |
    MATCH (e:Entity {id: $entity_id})
    OPTIONAL MATCH (e)-[r]-(neighbor:Entity)
    WHERE neighbor.type IN $allowed_types
    RETURN DISTINCT neighbor.id, neighbor.type, neighbor.name, type(r)
    LIMIT $max_nodes
  params:
    entity_id: string (required)
    allowed_types: list[string] (required)
    max_nodes: int (default: 50)
  complexity: O(neighbors)

get_dependency_chain:
  description: "Trace dependency chain up to 2 hops"
  query: |
    MATCH path = (start:Entity {id: $entity_id})-[:DEPENDS_ON*1..2]->(dep:Entity)
    RETURN DISTINCT dep.id, dep.type, dep.name, length(path) as depth
    ORDER BY depth
    LIMIT $max_nodes
  params:
    entity_id: string (required)
    max_nodes: int (default: 50)
  complexity: O(depth * neighbors)
```

---

### 1.4 Entity Extraction

**File:** `/a0/usr/projects/mac/graphrag/lib/entity_extractor.py`

**Entity ID Normalization:**

```python
def normalize_entity_id(entity_type: str, name: str, namespace: str = None) -> str:
    """
    Generate stable entity ID.
    Format: type:canonical_name[:namespace]
    """
    canonical_name = re.sub(r'[^a-z0-9]', '_', name.lower().strip())
    canonical_name = re.sub(r'_+', '_', canonical_name).strip('_')
    
    if namespace:
        return f"{entity_type}:{canonical_name}:{namespace}"
    return f"{entity_type}:{canonical_name}"

# Examples:
# normalize_entity_id("person", "George Freeney Jr.") → "person:george_freeney_jr"
# normalize_entity_id("system", "Gateway", "production") → "system:gateway:production"
```

**Extraction Schema:**

```python
@dataclass
class ExtractedEntity:
    id: str  # Normalized ID
    type: str  # person, system, artifact, decision, incident, concept
    name: str  # Original name
    aliases: List[str]  # Variants (e.g., ["EdgeProxy"] for Gateway)
    source_doc: str  # Document ID
    source_line: int  # Line number
    confidence: float  # 0.0-1.0

@dataclass
class ExtractedRelationship:
    source_id: str  # Normalized source entity ID
    target_id: str  # Normalized target entity ID
    type: str  # DEPENDS_ON, APPROVED_BY, MENTIONED_IN, etc.
    source_doc: str  # Document ID
    source_line: int  # Line number
    certainty: str  # supported, likely, possible, conflicting, unknown
```

---

## Phase 2: Hybrid Retrieval (PR #1)

### 2.1 Hybrid Retrieve Pipeline

**File:** `/a0/usr/projects/mac/graphrag/lib/graphrag_hybrid_retrieve.py`

```python
@dataclass
class RetrievalResult:
    context: str  # Assembled context
    entities: List[ExtractedEntity]
    relationships: List[ExtractedRelationship]
    provenance: Dict[str, List[str]]  # entity_id -> [doc_ids]
    latency_breakdown: Dict[str, int]  # phase -> ms

class HybridRetriever:
    def __init__(
        self, 
        vector_store, 
        neo4j_connector: Optional[Neo4jConnector],
        config: GraphRAGConfig
    ):
        self.vector_store = vector_store
        self.neo4j = neo4j_connector
        self.config = config
    
    async def retrieve(self, query: str) -> RetrievalResult:
        """
        Execute hybrid retrieval pipeline.
        
        Latency is measured separately from LLM generation.
        """
        latency = {}
        
        # Phase 1: Vector seed (always runs)
        start = time.perf_counter()
        seed_docs = await self.vector_store.similarity_search(query, k=5)
        latency["vector_seed_ms"] = int((time.perf_counter() - start) * 1000)
        
        # Phase 2: Entity pinning
        start = time.perf_counter()
        entities = await self._extract_and_pin_entities(seed_docs)
        latency["entity_pinning_ms"] = int((time.perf_counter() - start) * 1000)
        
        # Phase 3: Graph expansion (if available)
        start = time.perf_counter()
        graph_context = await self._expand_graph(entities)
        latency["graph_query_ms"] = self.neo4j._last_query_ms if self.neo4j else 0
        latency["graph_expansion_ms"] = int((time.perf_counter() - start) * 1000)
        
        # Phase 4: Context pack
        start = time.perf_counter()
        context = self._assemble_context(seed_docs, entities, graph_context)
        latency["context_pack_ms"] = int((time.perf_counter() - start) * 1000)
        
        latency["total_pipeline_ms"] = sum(latency.values())
        
        return RetrievalResult(
            context=context,
            entities=entities,
            relationships=graph_context.relationships,
            provenance=self._build_provenance(entities, graph_context),
            latency_breakdown=latency
        )
```

---

## Phase 3: Entity Resolution Audit (PR #2)

### 3.1 Audit Implementation

**File:** `/a0/usr/projects/mac/graphrag/tools/entity_resolution_audit.py`

```python
class EntityResolutionAuditor:
    def __init__(self, neo4j_connector: Neo4jConnector):
        self.neo4j = neo4j_connector
    
    async def run_audit(self) -> AuditResult:
        """
        Execute full entity resolution audit.
        See BENCHMARK_PLAN.md for detailed procedure.
        """
        results = {
            "total_entities": 0,
            "duplicates": [],
            "unresolved_ambiguities": [],
            "missing_ids": [],
            "inconsistent_types": [],
            "same_as_chains": [],
            "passed": True
        }
        
        # 1. Count entities
        results["total_entities"] = await self._count_entities()
        
        # 2. Check for duplicates (same normalized key)
        results["duplicates"] = await self._find_duplicates()
        
        # 3. Check unresolved POSSIBLE_SAME_AS
        results["unresolved_ambiguities"] = await self._find_unresolved()
        
        # 4. Verify all entities have IDs
        results["missing_ids"] = await self._find_missing_ids()
        
        # 5. Check type consistency
        results["inconsistent_types"] = await self._find_type_inconsistencies()
        
        # 6. Verify same_as chains
        results["same_as_chains"] = await self._verify_same_as_chains()
        
        # Determine pass/fail
        results["passed"] = (
            len(results["duplicates"]) == 0 and
            len(results["unresolved_ambiguities"]) == 0 and
            len(results["missing_ids"]) == 0
        )
        
        return AuditResult(**results)
```

### 3.2 Idempotent Upsert

```python
async def idempotent_upsert_entity(
    connector: Neo4jConnector,
    entity: ExtractedEntity
) -> bool:
    """
    Upsert entity with idempotency check.
    Returns True if entity was created/updated, False if unchanged.
    """
    # Get existing entity
    existing = await connector.execute_query(
        "get_entity_by_id",
        {"entity_id": entity.id}
    )
    
    if existing:
        # Compare hash
        existing_hash = hash_entity(existing[0])
        new_hash = hash_entity(entity)
        
        if existing_hash == new_hash:
            return False  # No change needed
        
        # Update with new data
        await connector.execute_query(
            "update_entity",
            {"entity_id": entity.id, "data": entity.to_dict()}
        )
        return True
    
    # Create new entity
    await connector.execute_query(
        "create_entity",
        {"entity": entity.to_dict()}
    )
    return True
```

---

## Phase 4: Benchmark Integration (PR #3)

### 4.1 Benchmark Runner

**File:** `/a0/usr/projects/graphrag_bench/runner/run_bench.py`

**See BENCHMARK_PLAN.md for full runner design and file layout.**

### 4.2 Latency Measurement

**Latency is measured EXCLUDING LLM generation time.**

```python
# Per-question latency recording
latency_record = {
    "question_id": "A1",
    "latency_breakdown": {
        "vector_seed_ms": 45,
        "entity_pinning_ms": 12,
        "graph_query_ms": 78,
        "context_pack_ms": 8,
        "total_pipeline_ms": 143,
        "llm_generation_ms": 2340  # Recorded but EXCLUDED from budget
    }
}
```

---

## Docker Setup

### Docker Compose for Benchmark/Dev (Optional)

**Note:** This is OPTIONAL. Benchmark can run against existing Agent Zero instance.

```yaml
# docker-compose.bench.yml
version: '3.8'
services:
  agent-zero-dev:
    build: 
      context: ./agent-zero-fork
      dockerfile: Dockerfile
    ports:
      - "8087:8000"  # Map host 8087 to internal port 8000
    environment:
      - GRAPH_RAG_ENABLED=false
      - NEO4J_URI=bolt://neo4j-bench:7687
    depends_on:
      - neo4j-bench
    profiles:
      - benchmark

  neo4j-bench:
    image: neo4j:5-community
    ports:
      - "7688:7687"
      - "7474:7474"
    environment:
      - NEO4J_AUTH=neo4j/benchmark123
    profiles:
      - benchmark
```

**Usage:**

```bash
# Run benchmark with isolated environment
docker-compose --profile benchmark up -d

# Run benchmark
python /a0/usr/projects/graphrag_bench/runner/run_bench.py

# Cleanup
docker-compose --profile benchmark down
```

---

## Risk Register

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Neo4j connection failures | Retrieval falls back to vector-only | High | Graceful fallback, warning logs |
| Entity extraction errors | Incomplete graph | Medium | Confidence thresholds, manual review queue |
| Latency exceeds budget | User experience degradation | Medium | Async caching, query optimization |
| Hallucinated relationships | Incorrect context | Low | Provenance tracking, certainty labels |
| Baseline regression | Breaking existing behavior | Low | Golden tests, feature flag off by default |
| Entity ID collisions | Data corruption | Low | Normalized keys, uniqueness constraint |

---

## Acceptance Criteria Summary

### PR #1 (MVP)
- [ ] All golden tests pass (GraphRAG disabled = baseline behavior)
- [ ] Graceful fallback verified (Neo4j down scenario)
- [ ] Entity extraction produces stable IDs
- [ ] All Cypher queries use allowlisted templates
- [ ] Feature flag defaults to `false`

### PR #2 (Migration)
- [ ] Entity Resolution Audit passes
- [ ] Re-run produces identical graph state
- [ ] 100% provenance on relationships
- [ ] All existing knowledge backfilled

### PR #3 (Optimization)
- [ ] p95_retrieval_pipeline_ms within 2x baseline
- [ ] Cache hit rate ≥60%
- [ ] Benchmark shows +20% on multi-hop questions
- [ ] No hallucination increase vs baseline

---

## PR Review Checklist

- [ ] Feature flag defaults to `false`
- [ ] No modifications to `/a0/` core files
- [ ] All tests pass with GraphRAG disabled
- [ ] All tests pass with GraphRAG enabled
- [ ] Graceful degradation verified (Neo4j down scenario)
- [ ] No new required dependencies (all optional)
- [ ] Benchmark report generated and shows improvement
- [ ] Entity resolution audit passes
- [ ] Latency budgets not exceeded
- [ ] Certainty labels present in responses

---

## Timeline

This plan uses milestone-gated progression. No timeline estimates are provided.

**Milestone Order:**
1. Planning → BENCHMARK_PLAN.md approved
2. PR #1 MVP → Core functionality, golden tests pass
3. PR #2 Migration → Entity resolution, provenance
4. PR #3 Optimization → Performance, benchmarks

Each milestone requires explicit approval before proceeding to the next.

---

## Approval Gate

**Status:** PENDING - Awaiting BENCHMARK_PLAN.md approval first

**Approver:** George Freeney Jr.

---

*Last updated: 2026-02-27*
