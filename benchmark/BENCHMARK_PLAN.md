# GraphRAG for Agent Zero - Benchmark Plan

**Version:** 1.2  
**Created:** 2026-02-27  
**Updated:** 2026-02-27  
**Author:** Mac (Agent Zero) for George Freeney Jr.  
**Status:** Draft - Pending Approval Before Implementation  
**Purpose:** Measurably prove Hybrid GraphRAG makes Agent Zero "smarter" (not just feature addition)
**Repository:** https://github.com/AijooseFactory/graphrag-agent-zero

---

## Executive Summary

This benchmark plan defines **what "smarter" means** and how we measure it. GraphRAG for Agent Zero will only be declared successful if it measurably improves:

1. **Accurate recall** – Fewer wrong-but-similar memories pulled from vector similarity alone
2. **Multi-hop reasoning** – "what led to X", "what depends on Y", "who approved Z"
3. **Consistency over time** – Stable entity IDs + relationships reduce drift, duplication
4. **Grounding** – Fewer hallucinated relationships, better provenance

**What does NOT count:**
- Raw model reasoning improvements (not our claim)
- Benefits assumed without benchmarks
- Changes to baseline behavior when GraphRAG is disabled

---

## Definition of "Smarter" (Measurable)

| Metric | Baseline Issue | GraphRAG Target | How Measured |
|--------|----------------|-----------------|--------------|
| **Accurate Recall** | Vector similarity returns semantically similar but contextually wrong results | +20% accuracy on entity-specific queries | Benchmark question scoring |
| **Multi-hop Reasoning** | Cannot trace A→B→C relationships | Correctly answers 80%+ of multi-hop questions | Benchmark multi-hop category |
| **Consistency** | Entity drift, duplicate entities, contradictory context | Stable entity IDs, no duplicates, consistent references | Entity Resolution Audit |
| **Grounding** | Hallucinated relationships without provenance | 0 hallucinated relationships, 100% provenance | Citation check in responses |

---

## Latency Budget Definition

### What We Measure (EXACT Definition)

**Latency budgets EXCLUDE LLM generation time.** We measure only the retrieval pipeline:

| Metric | Definition | Components |
|--------|------------|------------|
| **p95_graph_query_ms** | Neo4j query execution time only | Cypher query + result serialization |
| **p95_retrieval_pipeline_ms** | Full retrieval pipeline | Vector seed + entity pinning + graph expand + context pack |

### Measurement Methodology (Enforceable)

**Baseline Measurement Requirements:**
1. **Same machine:** Baseline and GraphRAG must be measured on identical hardware
2. **Same corpus:** Identical corpus documents for both runs
3. **Same run count:** Each benchmark question executed N times (N=10 minimum)
4. **Warmup rule:** First run discarded (cache cold start), report p95 on runs 2-N

**Sample Size:**
- Minimum N=10 runs per question
- p95 computed across all runs (not per-question average)
- Report both per-question latency and aggregate p95

### Initial Realistic Budgets (Local Dev)

**Note:** These are INITIAL targets for local development. They will be TUNED after first measurements. We do not claim specific values until proven.

| Metric | Initial Target | Rationale |
|--------|----------------|----------|
| **p95_graph_query_ms** | TBD after measurement | Will establish baseline first |
| **p95_retrieval_pipeline_ms** | TBD after measurement | Will establish baseline first |
| **Budget for p95_retrieval_pipeline_ms** | 2x baseline (max) | Must not exceed 2x baseline retrieval latency |

### Escape Hatches for Near-Zero Baseline

**Floor Cap:** Even if baseline is near-zero, p95_retrieval_pipeline_ms must be under an absolute cap:

| Environment | Absolute Cap | Rationale |
|-------------|---------------|----------|
| **Local dev** | 1500ms | Tuned after measurement, initial ceiling |
| **Production** | TBD after profiling | Different constraints |

**Rule:** `p95_retrieval_pipeline_ms ≤ min(2x_baseline, 1500ms)` for local dev

### Latency Recording Per Question

```json
{
  "question_id": "A1",
  "run_number": 5,
  "latency_breakdown": {
    "vector_seed_ms": 45,
    "entity_pinning_ms": 12,
    "graph_query_ms": 78,
    "context_pack_ms": 8,
    "total_pipeline_ms": 143,
    "llm_generation_ms": 2340
  },
  "cache_state": "warm"
}
```

**Note:** `llm_generation_ms` is recorded for context but EXCLUDED from latency budgets.

---

## Hallucination Definition & Certainty Discipline

### Hallucination Definition (Precise)

**Hallucination:** Any asserted relationship or claim that is NOT supported by:
1. Corpus evidence (explicit statement in benchmark corpus documents)
2. Graph traversal results (entities and relationships extracted from corpus)

**Examples of hallucinations:**
- Claiming "Alice approved ADR-001" when corpus says "George approved ADR-001"
- Stating "Gateway depends on Weaviate" when no such relationship exists in corpus or graph
- Fabricating entity attributes not present in source material
- Inferring relationships not explicitly stated or logically derivable from corpus

### Certainty Labels Requirement

All responses MUST include certainty labels for factual claims:

| Label | Definition | Required Signals |
|-------|------------|------------------|
| **supported** | Direct evidence in corpus or graph | At least 1 explicit source |
| **likely** | Strong inference from corpus | **At least 2 supporting signals** (2 sources OR 1 source + graph path) |
| **possible** | Weak inference, not contradicted | **At least 1 signal AND no contradictions** |
| **conflicting** | Corpus contains contradictory information | Must list BOTH conflicting sources |
| **unknown** | Insufficient information | No signals found |

### Certainty Label Rules (Enforceable)

**"likely" requires:**
- 2+ sources mentioning the relationship, OR
- 1 source + graph traversal path confirming it

**"possible" requires:**
- At least 1 signal supporting the claim
- No contradicting signals found

**"conflicting" requires:**
- Explicit listing of both conflicting sources
- Example: "Source A says X, Source B says Y"

**Scoring Penalty for Missing Signals:**
- "likely" without 2+ signals cited: -1 penalty
- "possible" without 1 signal cited: -1 penalty
- "conflicting" without listing both sources: -2 penalty

### Certainty in Responses

**Example response format:**

```markdown
The Gateway (supported) [ADR-001] depends on the Auth Service (supported) [DEPENDENCIES.md].
It was approved by Alice Chen (likely) [MEETING-2026-02-20, graph_path:gateway->approval].

Note: The exact approval date is conflicting between [MEETING-2026-02-15] and [MEETING-2026-02-20].
```

### Scoring with Certainty

| Scenario | Points |
|----------|--------|
| Correct claim with correct certainty label | Full points |
| Correct claim with incorrect certainty (overconfident) | -1 penalty |
| Incorrect claim labeled "unknown" | 0 (no penalty for honest uncertainty) |
| Incorrect claim labeled "supported" or "likely" | -2 (hallucination penalty) |
| Correct claim labeled "unknown" | -1 (underconfidence penalty) |
| "likely" without 2+ signals cited | -1 (missing evidence penalty) |
| "possible" without 1 signal cited | -1 (missing evidence penalty) |
| "conflicting" without listing both sources | -2 (incomplete conflict reporting) |

**Rewarding Correct Uncertainty:**
- If corpus has conflicting information and response labels it "conflicting" with both sources, award bonus point
- If response correctly identifies gap and labels "unknown", no penalty

---

## Entity Resolution Audit

### Purpose
Ensure entity stability across the benchmark corpus and GraphRAG system.

### Normalized Key Strategy

**Entity ID Format:** `type:canonical_name[:namespace]`

```yaml
# Examples
person:george_freeney_jr
person:alice_chen
system:gateway
system:auth_service
artifact:ADR-001
decision:ADR-001
incident:INC-001
change:CHG-001

# Namespace for disambiguation
system:gateway:production
decision:ADR-001:2026-02-15
```

### Duplicate Detection Method

1. **Exact match:** Same normalized key → merge
2. **Fuzzy match:** Levenshtein distance < 2 → flag for review
3. **Alias detection:** Explicit `same_as` relationship → merge with confidence score
4. **Contextual match:** Same role + same document context → flag for review

### Idempotent Upsert Verification

For each entity in benchmark corpus:

```python
async def verify_idempotent_upsert(entity_id: str):
    # First upsert
    result1 = await upsert_entity(entity)
    
    # Second upsert (identical data)
    result2 = await upsert_entity(entity)
    
    # Verify
    assert result2.created == False, "Second upsert should not create"
    assert result2.changed == False, "Second upsert should not change"
    
    # Verify state unchanged
    state1 = await get_entity(entity_id)
    state2 = await get_entity(entity_id)
    assert hash(state1) == hash(state2), "State should be identical"
```

### same_as / possible_same_as Rules

```yaml
# Explicit same_as (high confidence)
- Gateway --[SAME_AS]--> EdgeProxy
  confidence: 0.95
  source: CHANGELOG.md "renamed to Gateway"

# Possible same_as (needs review)
- G. Freeney --[POSSIBLE_SAME_AS]--> George Freeney Jr.
  confidence: 0.70
  source: MEETING-2026-02-15 (initials only)
  action: flag for human review

# Unresolved same_as = audit failure
audit_rule: No POSSIBLE_SAME_AS relationships allowed after processing
```

### Audit Checklist

- [ ] All entities have normalized IDs matching `type:canonical_name` format
- [ ] No duplicate entities with same normalized key
- [ ] All `POSSIBLE_SAME_AS` relationships resolved or flagged for review
- [ ] Re-running extraction produces identical entity count and IDs
- [ ] Entity types are consistent (same entity not typed as both `person` and `system`)

---

## Objective Scoring with Reference Answer Keys

### Reference Answer Key Format

Each benchmark question has a machine-checkable reference answer:

```json
{
  "question_id": "A1",
  "question": "What does Gateway depend on for authentication?",
  "required_entities": [
    "system:gateway",
    "system:auth_service",
    "system:redis"
  ],
  "required_sources": [
    "ADR-001",
    "DEPENDENCIES.md"
  ],
  "forbidden_claims": [
    "Gateway depends on PostgreSQL",
    "Gateway has no dependencies"
  ],
  "certainty": "supported",
  "multi_hop": true,
  "category": "A",
  "signals": {
    "supported": ["ADR-001", "DEPENDENCIES.md"],
    "likely_min_signals": 2,
    "possible_min_signals": 1
  }
}
```

### Structured Citation Format (Required)

**Citations MUST use structured format for deterministic scoring:**

```markdown
# Correct format:
The Gateway (supported) [ADR-001] depends on Auth Service (supported) [DEPENDENCIES.md].

# Alternative machine-readable format (also accepted):
The Gateway {entity:system:gateway} [source:ADR-001] depends on Auth Service {entity:system:auth_service} [source:DEPENDENCIES.md].

# WRONG - Free-form citations (NOT accepted):
The Gateway is documented in ADR-001 and depends on Auth Service per the dependencies doc.
```

**Citation Regex Pattern for Scorer:**
```python
CITATION_PATTERN = r'\[([A-Z]+-\d+|[A-Z_]+\.md)\]'  # Matches [ADR-001] or [DEPENDENCIES.md]
ENTITY_PATTERN = r'\{entity:([a-z_:]+)\}'  # Matches {entity:system:gateway}
```

### Deterministic Scoring Method

```python
def score_answer(response: str, reference: ReferenceAnswer) -> Score:
    score = 0
    penalties = []
    
    # 1. Check required entities (0-2 points)
    found_entities = extract_entities(response)
    entity_score = len(set(found_entities) & set(reference.required_entities))
    entity_score = min(entity_score, 2)
    score += entity_score
    
    # 2. Check citations (0-1 point)
    citations = extract_citations(response)  # Uses CITATION_PATTERN
    if set(citations) >= set(reference.required_sources):
        score += 1
    elif set(citations) & set(reference.required_sources):
        score += 0.5  # Partial credit
    
    # 3. Check forbidden claims (-1 each)
    for forbidden in reference.forbidden_claims:
        if forbidden.lower() in response.lower():
            score -= 1
            penalties.append(f"Forbidden claim: {forbidden}")
    
    # 4. Check certainty labels
    certainty = extract_certainty(response)
    if certainty != reference.certainty:
        score -= 1
        penalties.append(f"Wrong certainty: {certainty} vs {reference.certainty}")
    
    # 5. Check signal requirements for likely/possible
    if certainty == "likely":
        signals = count_signals(response)
        if signals < 2:
            score -= 1
            penalties.append("'likely' requires 2+ signals")
    elif certainty == "possible":
        signals = count_signals(response)
        if signals < 1:
            score -= 1
            penalties.append("'possible' requires 1+ signal")
    
    return Score(value=max(score, -2), penalties=penalties)
```

### Manual Scoring (Fallback Only)

Manual scoring is a **fallback** when deterministic scoring is ambiguous. Default is machine-checkable.

---

## Hard Corpus Cases

### Controlled Ambiguity Cases

| Case Type | Description | Documents |
|-----------|-------------|-----------|
| **Name variants** | "George Freeney Jr." / "George Freeney" / "G. Freeney" | MEETING-2026-02-15, MEETING-2026-02-20 |
| **Renamed component** | "Gateway" formerly "EdgeProxy" | CHANGELOG.md |
| **Conflicting record** | Two meeting notes disagree on approval date | MEETING-2026-02-15 vs MEETING-2026-02-20 |
| **2-hop dependency** | ADR-001 → decision:use_neo4j → system:neo4j | ADR-001, DEPENDENCIES.md |
| **2-doc traversal** | MEETING → ADR → DEPENDENCIES (only discoverable via graph) | MEETING-2026-02-20, ADR-002, DEPENDENCIES.md |

### 2-Doc Traversal Example (Graph Advantage Case)

**Question:** "What database does the system approved in the Feb 20 meeting depend on?"

**Graph Traversal Required:**
```
MEETING-2026-02-20 mentions "approved ADR-002"
ADR-002 decides "use Weaviate for vector search"
DEPENDENCIES.md shows "Weaviate depends on etcd"

Answer: etcd (supported) [MEETING-2026-02-20, ADR-002, DEPENDENCIES.md]
```

**Without graph:** Vector search might return MEETING-2026-02-20 and DEPENDENCIES.md but miss the ADR-002 connection.

### Stable IDs Across Documents

Every document has a stable ID:

| Document Type | ID Pattern | Example |
|---------------|------------|---------|
| Architecture Decision Record | ADR-XXX | ADR-001, ADR-002 |
| Incident Report | INC-XXX | INC-001, INC-002 |
| Standard Operating Procedure | SOP-NAME | SOP-deployment |
| Meeting Notes | MEETING-YYYY-MM-DD | MEETING-2026-02-15 |
| Change Record | CHG-XXX | CHG-001 |
| Reference Document | NAME.md | DEPENDENCIES.md, CHANGELOG.md |

---

## Benchmark Questions (20 Total)

| Category | Count | Purpose |
|----------|-------|---------|
| **A: Multi-hop Dependency** | 6 | Trace A→B→C relationships (requires graph) |
| **B: Decision Provenance** | 5 | Who approved what, where documented |
| **C: Entity Disambiguation** | 4 | Disambiguate terms across contexts |
| **D: Structured Recall** | 3 | Ports, roles, ownerships |
| **E: Failure-Mode** | 2 | Graceful degradation behavior |

---

## Failure-Mode Assertions

### Expected Behavior When Neo4j Down

**Question E1:** "What does Gateway depend on?" (run with Neo4j unavailable)

**Expected Answer Format:**
```markdown
[GRAPH_FALLBACK] GraphRAG is unavailable. Using vector-only retrieval.

The Gateway (supported) [ADR-001] depends on Auth Service (likely) [DEPENDENCIES.md].

Note: Full dependency chain may be incomplete due to graph unavailability.
```

**Scoring:**
- Must include `[GRAPH_FALLBACK]` indicator
- Must NOT claim graph-derived facts
- May still answer correctly from vector results
- Penalty for claiming graph traversal when Neo4j is down

### Expected Behavior When Graph Empty

**Question E2:** "What does Gateway depend on?" (run with empty graph)

**Expected Answer Format:**
```markdown
[GRAPH_EMPTY] Graph has no entities. Using vector-only retrieval.

The Gateway (supported) [ADR-001] depends on Auth Service (supported) [DEPENDENCIES.md].

Note: Graph expansion unavailable. Results may lack multi-hop context.
```

**Scoring:**
- Must include `[GRAPH_EMPTY]` indicator
- Must NOT fabricate graph-derived relationships
- May still answer correctly from vector results
- Penalty for hallucinating graph content

---

## Scoring Rubric

| Criterion | Points | Description |
|-----------|--------|-------------|
| **Correctness** | 0-2 | Fully correct (2), partial (1), incorrect (0) |
| **Citation** | 0-1 | All required sources cited in structured format [DOC-ID] |
| **Completeness** | 0-1 | All required entities mentioned |
| **Hallucination Penalty** | -1 to -2 | Fabricated relationships or claims |
| **Certainty Penalty** | -1 | Wrong certainty label or missing signals |

**Maximum Score per Question:** 4 points
**Total Maximum Score:** 80 points (20 questions × 4)

---

## Cache Measurement Requirements

### Metrics

| Metric | Definition | Requirement |
|--------|------------|-------------|
| **cache_hit_rate_graph** | Neo4j query cache hits / total queries | Report separately |
| **cache_hit_rate_pipeline** | Full pipeline cache hits / total requests | Report separately |
| **cache_hit_threshold** | Minimum acceptable hit rate | ≥60% AFTER warm cache |

### Measurement Protocol

1. **Run 1 (cold cache):** Discard for cache metrics, include for latency baseline
2. **Runs 2-N (warm cache):** Report cache hit rates
3. **Cache requirement:** cache_hit_rate_graph ≥60% on runs 2-N

### Cache Reporting

```json
{
  "question_id": "A1",
  "cache_metrics": {
    "graph_cache_hits": 8,
    "graph_cache_misses": 2,
    "graph_cache_hit_rate": 0.80,
    "pipeline_cache_hits": 5,
    "pipeline_cache_misses": 5,
    "pipeline_cache_hit_rate": 0.50
  }
}
```

---

## Acceptance Criteria (Must Pass)

| Criterion | Threshold |
|-----------|-----------|
| Multi-hop Improvement | GraphRAG ≥+20% vs baseline (Category A) |
| Decision Provenance | GraphRAG ≥+20% vs baseline (Category B) |
| No Baseline Regression | GraphRAG disabled = baseline behavior (golden test) |
| No Hallucination Increase | Hallucination rate ≤ baseline |
| Latency Budget | p95 ≤ min(2x_baseline, 1500ms) |
| Cache Hit Rate | ≥60% after warm cache (PR #3) |
| Certainty Accuracy | ≥80% of certainty labels correct |
| Entity Resolution | Audit passes with no unresolved ambiguities |

---

## Upstream PR Safety

**This is the foundational constraint for all implementation work.**

### Non-Negotiable Requirements

| Requirement | Description | Verification Method |
|-------------|-------------|---------------------|
| **GraphRAG OFF by default** | Feature flag `GRAPH_RAG_ENABLED=false` in `.env` | Default config check |
| **No core patches** | No modifications to `/a0/python/` core files | Diff against upstream |
| **No baseline retrieval changes** | No changes to baseline retrieval code path when `GRAPH_RAG_ENABLED=false` | Code review + golden test |
| **No new required dependencies for baseline** | All new dependencies optional, not required for baseline container build | Build test without GraphRAG deps |
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
- [ ] No changes to baseline retrieval code path when disabled
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
| Query caching | Neo4j query result cache | Cache hit rate ≥60% after warm cache |
| Performance budgets | Latency within 2x baseline | p95 measurement in CI |
| Benchmark automation | CI-integrated benchmark runner | Automated score comparison |
| Tuning documentation | Parameter recommendations | Documented for common scenarios |

**PR #3 Acceptance Criteria:**
- [ ] p95_retrieval_pipeline_ms within 2x baseline
- [ ] Cache hit rate ≥60% after warm cache
- [ ] Benchmark report auto-generated
- [ ] All BENCHMARK_PLAN.md acceptance criteria met

---

## Benchmark Runner Design

### File Layout

```
/a0/usr/projects/graphrag_bench/
├── corpus/                          # Benchmark corpus (12 docs)
│   ├── ADR-001-architecture-decision.md
│   ├── ADR-002-database-choice.md
│   ├── INC-001-gateway-outage.md
│   ├── INC-002-deployment-failure.md
│   ├── SOP-deployment.md
│   ├── SOP-incident-response.md
│   ├── MEETING-2026-02-15.md
│   ├── MEETING-2026-02-20.md
│   ├── SYSTEMS_MAP.md
│   ├── PEOPLE_ROLES.md
│   ├── CHANGELOG.md
│   └── DEPENDENCIES.md
├── questions/                       # Question definitions
│   └── benchmark_questions.json     # Structured question format with reference answers
├── scorer/                          # Scoring logic
│   ├── __init__.py
│   ├── evaluator.py                 # Core scoring logic
│   ├── hallucination_check.py       # Detect fabricated relationships
│   ├── citation_check.py            # Verify provenance claims (structured format)
│   ├── certainty_check.py           # Verify certainty labels and signals
│   └── entity_audit.py              # Entity resolution verification
├── runner/                          # Benchmark execution
│   ├── __init__.py
│   ├── run_bench.py                 # Main entry point
│   ├── baseline_runner.py           # Run with GraphRAG disabled
│   ├── graphrag_runner.py           # Run with GraphRAG enabled
│   └── golden_test.py               # Verify baseline equivalence
├── results/                         # Benchmark outputs
│   └── run_YYYYMMDD_HHMMSS/         # Timestamped results
│       ├── baseline_scores.json
│       ├── graphrag_scores.json
│       ├── latency_baseline.json
│       ├── latency_graphrag.json
│       ├── latency_breakdown.json
│       ├── cache_metrics.json
│       ├── entity_audit.json
│       ├── detailed_answers.json
│       ├── reference_answers.json
│       └── summary.md
├── config/
│   └── bench_config.json            # Benchmark configuration
├── scripts/
│   ├── setup_corpus.py              # Import corpus into test instance
│   ├── entity_resolution_audit.py   # Run entity audit
│   └── teardown.py                  # Cleanup test instance
└── README.md                        # Benchmark usage documentation
```

### Runner Execution Flow

```
1. Setup Phase
   ├── Run entity resolution audit on corpus
   ├── Verify no unresolved POSSIBLE_SAME_AS relationships
   ├── Load corpus into test Agent Zero instance (port 8087)
   ├── Verify corpus loaded correctly (entity count check)
   └── Initialize Neo4j test container (if GraphRAG enabled)

2. Baseline Run (N=10 per question, discard run 1)
   ├── Disable GraphRAG (feature flag = false)
   ├── For each question:
   │   ├── Run 1 (cold cache): Record latency, discard from cache metrics
   │   ├── Runs 2-10 (warm cache): Record latency + cache metrics
   │   ├── Send query to Agent Zero
   │   ├── Record response text
   │   ├── Measure latency breakdown (vector, pack)
   │   ├── Extract entities, sources, relationships, certainty labels
   │   ├── Verify structured citation format
   │   └── Compare to reference answer
   └── Calculate aggregate scores

3. GraphRAG Run (N=10 per question, discard run 1)
   ├── Enable GraphRAG (feature flag = true)
   ├── Verify Neo4j connection
   ├── For each question:
   │   ├── Run 1 (cold cache): Record latency, discard from cache metrics
   │   ├── Runs 2-10 (warm cache): Record latency + cache metrics
   │   ├── Send query to Agent Zero
   │   ├── Record response text
   │   ├── Measure latency breakdown (vector, entity, graph, pack)
   │   ├── Extract entities, sources, relationships, certainty labels
   │   ├── Verify structured citation format
   │   └── Compare to reference answer
   └── Calculate aggregate scores

4. Golden Test
   ├── Compare baseline disabled vs baseline enabled
   └── Verify identical behavior

5. Failure-Mode Tests
   ├── Run E1 with Neo4j unavailable
   ├── Verify [GRAPH_FALLBACK] indicator present
   ├── Run E2 with empty graph
   └── Verify [GRAPH_EMPTY] indicator present

6. Analysis & Report
   ├── Calculate deltas (score, hallucination, certainty, latency, cache)
   ├── Generate per-category breakdown
   ├── Generate entity resolution audit report
   ├── Generate summary.md
   └── Output recommendation (Pass/Fail)
```

### Configuration Format

```json
{
  "corpus_path": "/a0/usr/projects/graphrag_bench/corpus",
  "questions_path": "/a0/usr/projects/graphrag_bench/questions/benchmark_questions.json",
  "output_path": "/a0/usr/projects/graphrag_bench/results",
  "agent_zero_url": "http://localhost:8087",
  "neo4j_url": "bolt://localhost:7687",
  "runs": {
    "baseline": { "graphrag_enabled": false },
    "graphrag": { "graphrag_enabled": true }
  },
  "measurement": {
    "runs_per_question": 10,
    "warmup_runs": 1,
    "same_machine": true,
    "same_corpus": true
  },
  "performance_budgets": {
    "p95_graph_query_ms": null,
    "p95_retrieval_pipeline_multiplier": 2.0,
    "absolute_cap_ms": 1500,
    "max_context_kb": 5,
    "max_hops": 2,
    "max_nodes": 50,
    "cache_ttl_seconds": 300,
    "cache_hit_rate_threshold": 0.60
  },
  "acceptance_criteria": {
    "multi_hop_improvement_percent": 20,
    "provenance_improvement_percent": 20,
    "max_hallucination_rate": 0.05,
    "golden_test_must_match": true,
    "entity_resolution_required": true,
    "certainty_accuracy_percent": 80,
    "cache_hit_rate_threshold": 0.60
  }
}
```

---

## Docker Setup

### Docker Compose for Benchmark/Dev (Optional)

**Note:** This is OPTIONAL. Benchmark can run against existing Agent Zero instance. Use this only for isolated testing.

**Important:** Internal port must match upstream container. Agent Zero's default internal port is **80**.

```yaml
# docker-compose.bench.yml
version: '3.8'
services:
  agent-zero-dev:
    build: 
      context: ./agent-zero-fork
      dockerfile: Dockerfile
    ports:
      - "8087:80"  # Map host 8087 to internal port 80 (Agent Zero default)
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

### Usage

```bash
# Run benchmark with isolated environment
docker-compose --profile benchmark up -d

# Run benchmark
python /a0/usr/projects/graphrag_bench/runner/run_bench.py

# Cleanup
docker-compose --profile benchmark down
```

---

## Deliverables Checklist

### Planning Phase (Current)
- [x] BENCHMARK_PLAN.md created
- [x] Latency budget defined precisely (excludes LLM, separate measurements, enforceable)
- [x] Hallucination definition and certainty discipline (signal requirements)
- [x] Entity Resolution Audit procedure
- [x] Reference answer key format (structured citations)
- [x] Hard corpus cases (including 2-doc traversal)
- [x] Docker Compose YAML corrected (port 80 internal)
- [x] Upstream PR Safety section (baseline code path protection)
- [x] Failure-mode assertions
- [x] Cache measurement requirements
- [ ] SAFE_CYPHER_TEMPLATES.md created
- [ ] Corpus documents created (12 files)
- [ ] benchmark_questions.json created with reference answers
- [ ] bench_config.json created

### Implementation Phase (After Approval)
- [ ] Fork Agent Zero repository to github.com/AijooseFactory/graphrag-agent-zero
- [ ] Docker dev environment on port 8087 (optional)
- [ ] neo4j_connector.py implemented
- [ ] graphrag_hybrid_retrieve.py implemented
- [ ] SAFE_CYPHER_TEMPLATES.md populated
- [ ] Benchmark runner implemented
- [ ] Entity resolution audit implemented
- [ ] E2E tests passing

---

## Approval Gate

**This plan must be approved before implementation begins.**

### Approval Criteria
- [x] Latency budget is precisely defined (excludes LLM, separate measurements, enforceable)
- [x] Hallucination definition is precise with certainty discipline (signal requirements)
- [x] Entity Resolution Audit procedure is complete
- [x] Scoring is machine-checkable with reference answer keys (structured citations)
- [x] Corpus has hard cases (renames, variants, conflicts, 2-hop chains, 2-doc traversal)
- [x] Docker Compose YAML is syntactically correct (port 80 internal)
- [x] Upstream PR Safety section is complete (baseline code path protection)
- [x] Failure-mode assertions defined
- [x] Cache measurement requirements defined
- [x] Acceptance criteria are achievable
- [x] Performance budgets are measurable

### Sign-off

- **Plan Author:** Mac (Agent Zero)  
- **Plan Date:** 2026-02-27  
- **Approval Status:** PENDING  
- **Approver:** George Freeney Jr.  
- **Repository:** https://github.com/AijooseFactory/graphrag-agent-zero

---

*Last updated: 2026-02-27*
