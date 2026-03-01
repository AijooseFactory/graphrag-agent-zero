# Installation Guide

## Prerequisites
- Python ≥ 3.10
- Agent Zero (any provider/model)
- Docker (for the dev stack)
- *Optional:* Neo4j 5.x (Docker, Neo4j Desktop, or existing instance)

## Quick Runbook (3 Commands)

```bash
# (a) Start dev stack (Agent Zero on port 8087)
docker compose -f dev/docker-compose.graphrag-dev.yml up -d --build

# (b) Optional: start Neo4j
docker compose -f dev/docker-compose.graphrag-dev.yml --profile neo4j up -d

# (c) Run E2E proof
bash scripts/e2e.sh
```

## Extension Placement

The GraphRAG extension is automatically loaded by Agent Zero from:
```
agent-zero-fork/agents/default/extensions/message_loop_prompts_after/_80_graphrag.py
```

**No core patches.** Agent Zero discovers it via the upstream Extensions Framework.

## Enable GraphRAG

Set environment variables where Agent Zero runs:
```bash
export GRAPH_RAG_ENABLED=true
export NEO4J_URI="bolt://localhost:7688"   # or your Neo4j Desktop URI
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-password"
```

GraphRAG is **OFF by default**. If you don't set `GRAPH_RAG_ENABLED=true`, Agent Zero behaves normally.

## Neo4j Connection Priority

1. If `NEO4J_URI` is set and reachable → use it
2. If Neo4j Desktop is running (bolt://localhost:7687) → use it
3. If nothing reachable → GraphRAG no-ops, Agent Zero continues

## Install the Package (optional, for local development)

```bash
pip install -e .                  # Baseline install (no Neo4j driver)
pip install -e ".[neo4j]"         # With Neo4j driver
```

## Dev Stack Ports

| Service | URL |
|---------|-----|
| Agent Zero Web UI | http://localhost:8087 |
| Neo4j HTTP | http://localhost:7475 (with `--profile neo4j`) |
| Neo4j Bolt | bolt://localhost:7688 (with `--profile neo4j`) |
