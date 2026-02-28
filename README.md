# GraphRAG for Agent Zero

> **A top-1% GitHub add-on enabling graph-augmented retrieval for Agent Zero with Neo4j integration.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Agent Zero](https://img.shields.io/badge/Agent%20Zero-Compatible-blue)](https://github.com/AgentZeroAI/agent-zero)

## Overview

GraphRAG for Agent Zero enhances the agent's retrieval capabilities by combining vector search with knowledge graph traversal. This enables:

- **Multi-hop reasoning**: Connect information across documents
- **Provenance tracking**: Trace answers back to source documents
- **Disambiguation**: Resolve entities and relationships
- **Hallucination reduction**: Grounded responses with citations

## Features

- ✅ **Hybrid Retrieval**: Vector seed → Entity pinning → Bounded graph expansion
- ✅ **Graceful Fallback**: Automatic fallback to baseline retrieval if Neo4j unavailable
- ✅ **Safe Queries**: Allowlisted Cypher templates only (no arbitrary LLM-generated queries)
- ✅ **Zero Regressions**: Feature flag OFF by default, golden tests ensure baseline compatibility
- ✅ **Easy Install**: Docker Compose profile or simple config change

---

## Quick Start

### 1. Prerequisites

- Agent Zero running in Docker
- Neo4j 5.x (optional, for GraphRAG features)
- Python 3.10+

### 2. Start Neo4j (Dedicated Instance)

```bash
# Start dedicated Neo4j for GraphRAG (unique ports 7475/7688)
docker-compose -f docker-compose.neo4j.yml up -d

# Verify Neo4j is running
curl http://localhost:7475
```

### 3. Enable GraphRAG

```bash
# Set environment variable
export GRAPH_RAG_ENABLED=true

# Or edit .env file
GRAPH_RAG_ENABLED=true
```

### 4. Run Tests

```bash
# Golden tests (verify no regressions)
python tests/golden/test_baseline.py

# Benchmark runner
python scripts/run_benchmark.py --mode compare
```

---

## Installation Options

### Option A: Docker Compose Profile

```yaml
# Add to your Agent Zero docker-compose.yml
services:
  agent-zero:
    # ... existing config ...
    environment:
      - GRAPH_RAG_ENABLED=true
      - NEO4J_URI=bolt://graphrag-neo4j:7687
  
  graphrag-neo4j:
    image: neo4j:5.15-community
    ports:
      - "7475:7474"
      - "7688:7687"
    environment:
      - NEO4J_AUTH=neo4j/graphrag123dev
```

### Option B: Manual Configuration

```bash
# Clone the repository
git clone https://github.com/AijooseFactory/graphrag-agent-zero.git

# Install dependencies
pip install neo4j>=5.0.0

# Configure environment
cp .env.graphrag .env
# Edit .env and set GRAPH_RAG_ENABLED=true
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Zero Core                       │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              Extension Hook (extension_hook.py)          │
│                                                          │
│  if GRAPH_RAG_ENABLED and Neo4j available:              │
│      → HybridRetriever (vector + graph)                 │
│  else:                                                   │
│      → Baseline retrieval unchanged                     │
└─────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┴───────────────┐
           ▼                               ▼
┌──────────────────────┐      ┌──────────────────────┐
│   Neo4j Connector    │      │   Graph Builder      │
│  (timeouts/retries)  │      │  (entity extraction) │
└──────────────────────┘      └──────────────────────┘
           │                               │
           └───────────────┬───────────────┘
                           ▼
                  ┌─────────────────┐
                  │    Neo4j DB     │
                  │  (ports 7475/   │
                  │   7688)         │
                  └─────────────────┘
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_RAG_ENABLED` | `false` | Enable/disable GraphRAG |
| `NEO4J_URI` | `bolt://localhost:7688` | Neo4j Bolt URI |
| `NEO4J_HTTP_URI` | `http://localhost:7475` | Neo4j HTTP UI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `graphrag123dev` | Neo4j password |
| `NEO4J_QUERY_TIMEOUT_MS` | `10000` | Query timeout (ms) |
| `GRAPH_EXPAND_MAX_HOPS` | `2` | Max graph traversal depth |
| `GRAPH_EXPAND_LIMIT` | `100` | Max entities to expand |

---

## API Reference

### Extension Hook

```python
from src import enhance_retrieval, is_enabled, health_check

# Check if enabled
if is_enabled():
    # Enhance retrieval with graph
    result = enhance_retrieval(
        query="What caused the outage?",
        vector_results=vector_results,
        top_k=10
    )
    
    print(result["text"])  # Enhanced context
    print(result["sources"])  # ["INC-001", "MEETING-2026-02-15"]
    print(result["entities"])  # ["Service-A", "Component-X"]

# Health check
status = health_check()
# {"enabled": true, "neo4j_available": true, ...}
```

---

## Benchmark Results

### Baseline (GraphRAG OFF)

| Metric | Value |
|--------|-------|
| Accuracy | 51.79% |
| Provenance | 74.07% |
| Hallucination Penalty | 0.00% |
| P95 Latency | 0.04ms |

### Target (GraphRAG ON)

| Metric | Target | Constraint |
|--------|--------|------------|
| Accuracy | >60% | Improvement required |
| Provenance | >85% | Must improve |
| Hallucination Penalty | 0% | No increase |
| P95 Latency | ≤2x baseline | Performance bound |

---

## Safety Guarantees

1. **Feature Flag OFF by Default** - No changes to baseline behavior
2. **No Core Patches** - Uses extension hook pattern only
3. **Graceful Fallback** - Returns baseline if Neo4j unavailable
4. **Safe Cypher** - Allowlisted queries only, no arbitrary LLM-generated Cypher
5. **Bounded Queries** - Max 2 hops, LIMIT enforced, timeouts applied

---

## Development

### Run Tests

```bash
# Golden tests
python tests/golden/test_baseline.py

# Unit tests
pytest tests/

# Benchmark
python scripts/run_benchmark.py --mode compare
```

### Project Structure

```
graphrag-agent-zero/
├── benchmark/
│   ├── BENCHMARK_PLAN.md
│   ├── benchmark_questions.json
│   ├── corpus/           # 12 test documents
│   └── SAFE_CYPHER_TEMPLATES.md
├── config/
│   ├── graphrag_settings.py
│   └── neo4j_config.json
├── docs/
│   └── IMPLEMENTATION_PLAN.md
├── scripts/
│   ├── baseline_benchmark.py
│   └── run_benchmark.py
├── src/
│   ├── __init__.py
│   ├── extension_hook.py    # Main integration point
│   ├── hybrid_retrieve.py   # Vector + graph retrieval
│   ├── neo4j_connector.py   # Neo4j connection management
│   └── graph_builder.py     # Entity extraction
├── tests/
│   ├── golden/             # Baseline compatibility tests
│   └── e2e/                # End-to-end tests
├── docker-compose.neo4j.yml
├── docker-compose.bench.yml
├── .env
└── README.md
```

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `python tests/golden/test_baseline.py`
4. Submit a pull request

---

## Credits

- Built for [Agent Zero](https://github.com/AgentZeroAI/agent-zero)
- Powered by [Neo4j](https://neo4j.com/)
- Part of [Ai joose Factory](https://github.com/AijooseFactory)
