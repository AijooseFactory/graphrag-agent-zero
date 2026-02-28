# GraphRAG for Agent Zero

A GraphRAG extension for Agent Zero enabling multi-hop reasoning and knowledge graph integration.

## Status

| Phase | Status |
|-------|--------|
| A. Benchmark Setup | ✅ Complete |
| B. Baseline Metrics | ✅ Complete (51.79% accuracy) |
| C. MVP Implementation | ✅ Complete |
| D. GraphRAG Benchmark | 🔲 Pending Neo4j |
| E. GitHub PR | 🔲 Pending |

## Quick Start

### 1. Start Neo4j (from HOST machine)

```bash
cd /a0/usr/projects/ai_joose_factory/dbms
docker-compose up -d

# Verify Neo4j is running
curl http://localhost:7475
```

### 2. Run Benchmark

```bash
cd /a0/usr/projects/graphrag-agent-zero
python scripts/run_benchmark.py --mode compare
```

## Architecture

- **Feature Flag:** `GRAPH_RAG_ENABLED=false` by default (no baseline changes)
- **Graceful Fallback:** Returns baseline results if Neo4j unavailable
- **Safe Queries:** Only allowlisted Cypher templates
- **Bounded Expansion:** Max 2 hops, 100 nodes limit

## Connection Details

| Parameter | Value |
|-----------|-------|
| HTTP UI | http://localhost:7475 |
| Bolt URI | bolt://localhost:7688 |
| Username | neo4j |
| Password | graphrag123dev |

## Project Structure

```
graphrag-agent-zero/
├── benchmark/           # Benchmark artifacts
│   ├── BENCHMARK_PLAN.md
│   ├── benchmark_questions.json
│   └── corpus/
├── src/                 # Core implementation
│   ├── neo4j_connector.py
│   ├── hybrid_retrieve.py
│   ├── extension_hook.py
│   └── graph_builder.py
├── tests/golden/        # Golden tests
├── scripts/             # Utility scripts
└── docs/                # Documentation
```

## DBMS Location

Neo4j runs in the centralized **Ai joose Factory DBMS**:
- `/a0/usr/projects/ai_joose_factory/dbms/`

This ensures separation from Mac's personal graphrag (macs-graphrag on ports 7474/7687).
