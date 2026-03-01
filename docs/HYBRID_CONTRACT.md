# Hybrid GraphRAG Contract

> Canonical specification for the Hybrid GraphRAG extension in Agent Zero.
> All implementations, tests, and CI gates MUST satisfy the conditions below.

## 1. Definition

**Hybrid GraphRAG = Agent Zero's existing memory retrieval/injection + Graph-based retrieval/injection (Neo4j) combined.**

GraphRAG is an **augmentation layer** on top of Agent Zero's native memory, never a replacement.

| State | Memory Recall | Graph Retrieval | Notes |
|-------|--------------|-----------------|-------|
| `GRAPHRAG_ENABLED=false` | ✅ runs as stock | ❌ zero calls | Baseline behavior unchanged |
| `GRAPHRAG_ENABLED=true` + Neo4j up | ✅ runs as stock | ✅ runs and injects | Additive hybrid |
| `GRAPHRAG_ENABLED=true` + Neo4j down | ✅ runs as stock | ❌ graceful no-op | Resilient fallback |

> **Invariant:** If Hybrid GraphRAG is enabled and memory recall/injection does not occur, the implementation is invalid and must be rejected.

## 2. Toggle Semantics

| Variable | Priority | Default |
|----------|----------|---------|
| `GRAPHRAG_ENABLED` | Primary (contract) | `false` |
| `GRAPH_RAG_ENABLED` | Legacy alias | `false` |

When disabled: **zero** Neo4j calls, **zero** graph prompt blocks injected, **zero** external network traffic from the extension.

## 3. SPEP Retrieval Protocol

The `HybridRetriever` implements **Seed → Pin → Expand → Pack**:

1. **Seed** — Accept vector results from Agent Zero's memory recall.
2. **Pin** — Link seed documents to Neo4j Entity nodes.
3. **Expand** — Follow graph edges (bounded by allowlist + hard caps).
4. **Pack** — Merge graph-derived facts into a context block for the LLM.

### Hard Caps (non-negotiable)

| Parameter | Limit | Env Var |
|-----------|-------|---------|
| Max hops | ≤ 2 | `GRAPH_EXPAND_MAX_HOPS` |
| Max entities | ≤ 100 | `GRAPH_EXPAND_LIMIT` |
| Max results | ≤ 50 | `GRAPH_MAX_RESULTS` |
| Query timeout | configurable | `NEO4J_QUERY_TIMEOUT_MS` |

### Relationship Allowlist

Only these edge types are followed during graph expansion:
`REFERENCES`, `CONTAINS`, `MENTIONS`, `DEPENDS_ON`, `RELATED_TO`, `SUPERSEDES`, `AMENDS`

### Two Retrieval Paths

- **Path A (Doc-seeded):** Vector results → entity pinning → graph expand → pack
- **Path B (Query-only):** Entity term extraction → direct lookup → graph expand → pack

## 4. Wiring

- Extension hook: `message_loop_prompts_after/_80_graphrag.py`
- Injection key: `extras_persistent["graphrag"]`
- Ordering: `memories` → `solutions` → `graphrag` → everything else
- Prompt template: `agent.system.graphrag.md`
- No core patches. Pure extension add-on.

## 5. Required Log Markers

| Marker | When |
|--------|------|
| `GRAPHRAG_EXTENSION_EXECUTED` | Every time the extension hook fires |
| `GRAPHRAG_CONTEXT_INJECTED` | Enabled + Neo4j up + context injected |
| `GRAPHRAG_NOOP_NEO4J_DOWN` | Enabled + Neo4j unreachable |
| `GRAPHRAG_CONTEXT_BLOCK_START` | Sentinel inside injected prompt block |

## 6. Hard-Gated E2E Conditions

All three must pass for the implementation to be considered valid:

### Case A — Hybrid OFF
- `GRAPHRAG_ENABLED=false`
- Assert: `memory_seen=YES`, `graphrag_seen=NO`

### Case B — Hybrid ON + Neo4j UP
- `GRAPHRAG_ENABLED=true`, valid Neo4j URI
- Assert: `memory_seen=YES`, `graphrag_seen=YES`
- Assert: `GRAPHRAG_CONTEXT_INJECTED` in logs

### Case C — Hybrid ON + Neo4j DOWN
- `GRAPHRAG_ENABLED=true`, unreachable Neo4j URI
- Assert: `memory_seen=YES`, `graphrag_seen=NO`
- Assert: `GRAPHRAG_NOOP_NEO4J_DOWN` in logs

No external API keys required. Docker + LLM stub only.

## 7. Security

- All Cypher queries use allowlisted templates (`safe_cypher.py`).
- No arbitrary Cypher execution permitted.
- Parameters are validated and bounded before execution.
- Query timeouts are enforced at the driver level.
- Commented secrets (in `.env.example`, docs, markdown) are treated as secrets and caught by the sanitation gate.

## 8. Verification Coverage

| Gate | CI (`--ci`) | Local (full) |
|------|:-----------:|:------------:|
| Secrets sanitation | ✅ | ✅ |
| Lint (ruff) | ✅ | ✅ |
| Unit tests (43 tests) | ✅ | ✅ |
| E2E hybrid contract (3 cases) | ⏭ skipped | ✅ |
| Playwright | ⏭ skipped | Optional |

> CI validates sanitation, lint, and unit tests on every push/PR.
> Full E2E (Docker + Neo4j + LLM stub) is required locally before release.
> See `docs/RELEASE_CHECKLIST.md` for the pre-release process.
