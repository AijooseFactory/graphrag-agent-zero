# GraphRAG for Agent Zero

**GraphRAG for Agent Zero** is an extension-style add-on that gives Agent Zero a **Hybrid GraphRAG memory layer**: it combines **vector retrieval** (semantic search) with a **knowledge graph** (Neo4j) to improve how Agent Zero recalls, connects, and explains information across any domain.

---

## Why it improves Agent Zero

Agent Zero’s standard retrieval is strong at finding relevant chunks, but it can struggle with:

- **Multi-hop questions**: “What led to X, who approved it, and what depends on it?”
- **Relationship-heavy context**: dependencies, ownership, cause/effect, timelines
- **Consistency across synonyms/aliases**: different names for the same entity
- **Provenance**: explaining *why* an answer is correct and where it came from

GraphRAG improves this by adding a second step:

1) **Vector seed** finds the most relevant documents/chunks (baseline behavior)  
2) **Graph expansion** follows explicit relationships (A → B → C) to pull in the *right* connected facts

This gives Agent Zero better “structured recall” and more reliable context for planning, debugging, research, and governance work.

---

## Status

| Phase | Status |
|------|--------|
| A. Benchmark Setup | ✅ Complete |
| B. Baseline Metrics | ✅ Complete |
| C. MVP Implementation | ✅ Complete |
| D. Real A0 Extension | ✅ Complete + Verified |
| E. Dev Stack & E2E | ✅ 7 PASS |

> Baseline accuracy from current benchmark corpus: **51.79%** (example run).  
> Your results will vary by corpus and model.

---

## How it works (high level)

When enabled, the extension runs this pipeline:

1. **Vector seed** → get top relevant chunks (baseline)
2. **Entity pinning** → identify entities mentioned in those chunks
3. **Bounded graph expand** → query Neo4j with allowlisted, read-only, parameterized Cypher (max 2 hops)
4. **Context pack** → inject “Graph Facts + Evidence” into Agent Zero’s prompt

Safety & reliability features:
- **OFF by default** (`GRAPH_RAG_ENABLED=false`)
- **Graceful fallback**: if Neo4j is unavailable, it no-ops and Agent Zero continues normally
- **Safe Cypher only**: allowlisted templates, bounded traversal, no arbitrary queries

---

## Quick Start

### 1) Get the repo
```bash
git clone https://github.com/AijooseFactory/graphrag-agent-zero.git
cd graphrag-agent-zero
```

### 2) Install the package
```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install -U pip
pip install -e ".[neo4j]"
```

### 3) Start the Dev Stack (Port 8087)
```bash
# Start Agent Zero (port 8087)
docker compose -f dev/docker-compose.graphrag-dev.yml up -d --build

# Optional: Start Neo4j
docker compose -f dev/docker-compose.graphrag-dev.yml --profile neo4j up -d
```

### 4) Verify
```bash
bash scripts/e2e.sh
```

---

## Documentation
- [Installation Guide](docs/install.md)
- [Configuration](docs/config.md)
- [Architecture](docs/architecture.md)
- [Security Model](docs/SECURITY_MODEL.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Developer Notes](docs/DEV_NOTES.md)

## Connection Details (Dev Stack)

| Parameter | Value |
|-----------|-------|
| Agent Zero UI | http://localhost:8087 |
| Neo4j HTTP | http://localhost:7475 |
| Neo4j Bolt | bolt://localhost:7688 |
| Username | neo4j |
| Password | graphrag2026 |

## DBMS Location
Neo4j runs in the isolated development stack. This ensures zero conflict with production data.