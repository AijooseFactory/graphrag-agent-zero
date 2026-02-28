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

## Quick Start

### Prerequisites

- Agent Zero running in Docker
- Neo4j 5.x (optional, for GraphRAG features)

### Installation

```bash
# Clone the repository
git clone https://github.com/AijooseFactory/graphrag-agent-zero.git
cd graphrag-agent-zero

# Copy to Agent Zero extensions
cp -r lib/* /path/to/agent-zero/python/helpers/
cp -r tools/* /path/to/agent-zero/python/tools/
```

### Configuration

Enable GraphRAG in your Agent Zero configuration:

```json
{
  "graph_rag": {
    "enabled": true,
    "neo4j_uri": "bolt://neo4j:7687",
    "neo4j_user": "neo4j",
    "neo4j_password": "your_password",
    "max_hops": 2,
    "query_timeout_ms": 5000
  }
}
```

### Docker Compose

```yaml
# docker-compose.yml addition
services:
  neo4j:
    image: neo4j:5.15
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      NEO4J_AUTH: neo4j/your_password
    profiles:
      - graphrag
```

```bash
# Start with GraphRAG support
docker-compose --profile graphrag up -d
```

## Benchmark Results

### Baseline (GraphRAG Disabled)

| Metric | Value |
|--------|-------|
| Accuracy Score | 51.79% |
| Provenance Score | 74.07% |
| Hallucination Penalty | 0.00% |
| P95 Latency | 0.04ms |

### GraphRAG Enabled

*Run `scripts/baseline_benchmark.py` after enabling GraphRAG to compare.*

## Project Structure

```
graphrag-agent-zero/
├── benchmark/
│   ├── BENCHMARK_PLAN.md      # Benchmark methodology and scoring
│   ├── benchmark_questions.json # Test questions with answer keys
│   ├── corpus/                # Test documents (12 docs)
│   └── SAFE_CYPHER_TEMPLATES.md # Allowlisted Cypher queries
├── docs/
│   └── IMPLEMENTATION_PLAN.md # Detailed implementation roadmap
├── scripts/
│   └── baseline_benchmark.py  # Benchmark runner
├── src/                       # GraphRAG implementation
├── tests/                     # E2E and golden tests
├── config/                    # Configuration templates
└── README.md
```

## Implementation Phases

### PR #1: MVP
- Neo4j connector with timeouts/retries
- Hybrid retrieval tool
- Extension hook injection
- Feature flag (OFF by default)
- Graceful fallback

### PR #2: Migration
- Knowledge base entity extraction
- Neo4j ingestion pipeline
- Incremental sync

### PR #3: Optimization
- Query result caching
- Batch processing
- Performance tuning

## Development

### Running Benchmarks

```bash
# Baseline benchmark (GraphRAG disabled)
python scripts/baseline_benchmark.py

# Results saved to results/baseline_*.json
```

### Running Tests

```bash
# E2E tests
pytest tests/e2e/

# Golden tests (baseline compatibility)
pytest tests/golden/
```

## Constraints

- **No auto-installation** of Docker/Neo4j
- **No arbitrary Cypher** from LLM
- **No baseline behavior changes** when disabled
- **Persistence only** under `/a0/usr`
- **Graceful degradation** if Neo4j fails

## License

MIT License - see [LICENSE](LICENSE) file.

## Contributing

Contributions welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md).

## Acknowledgments

Built for [Agent Zero](https://github.com/AgentZeroAI/agent-zero) by [Ai joose Factory](https://github.com/AijooseFactory).
