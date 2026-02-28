# GraphRAG for Agent Zero

**GraphRAG for Agent Zero** is an **extension-style add-on** that brings **Hybrid GraphRAG** (vector retrieval + bounded Neo4j graph expansion) to Agent Zero to improve:

- **Multi-hop reasoning** (A → B → C)
- **Provenance-aware answers** (what evidence supports a claim)
- **Entity disambiguation** (names, aliases, ambiguous references)

It is designed to be:

- **Upgrade-friendly** (no “my way” lock-in)
- **Provider-agnostic** (works with any Agent Zero LLM provider/model configuration)
- **Safe by default** (GraphRAG is OFF unless you enable it)
- **Resilient** (Neo4j down ⇒ no-op, Agent Zero continues)

---

## Status

| Phase | Status |
|------|--------|
| A. Benchmark Setup | ✅ Complete |
| B. Baseline Metrics | ✅ Complete |
| C. MVP Implementation | ✅ Complete |
| D. GraphRAG Benchmark | 🔲 Pending Neo4j |
| E. GitHub PR | 🔲 Pending |

> Baseline accuracy from current benchmark corpus: **51.79%** (example run).  
> Your results will vary by corpus and model.

---

## Quick Start

### 0) Requirements
- **Agent Zero** installed and working
- **Python 3.11+** (3.12 OK)
- Optional for GraphRAG ON:
  - **Neo4j 5.x** (Neo4j Desktop or Docker)

### 1) Get the repo

git clone https://github.com/AijooseFactory/graphrag-agent-zero.git
cd graphrag-agent-zero
2) Install dependencies
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows PowerShell

pip install -U pip
pip install -e .

If Neo4j is used via the official Python driver and it is an optional extra in this repo, install:

pip install -e ".[neo4j]"
3) Start Neo4j (choose ONE)
Option A — Use Neo4j Desktop (recommended if you already use it)

Start Neo4j Desktop and note your Bolt URI (commonly bolt://localhost:7687) and credentials.

Option B — Start Neo4j via Docker (cross-platform)

If you don’t have Neo4j running, use the dev compose provided by this repo:

docker compose -f dev/docker-compose.graphrag-dev.yml up -d neo4j

This repo uses non-default ports by default to avoid conflicts with common local Neo4j setups.

4) Configure env vars (GraphRAG OFF by default)

Create a local env file (optional) or set env vars in your shell.

Minimum settings for GraphRAG ON:

export GRAPH_RAG_ENABLED=true
export NEO4J_URI="bolt://localhost:7688"        # or your Neo4j Desktop bolt URI
export NEO4
I just need it to tell what it is, why it improves Agent Zero and how, and how to install it.
Thought for a few seconds
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

## Install

### Requirements
- A working Agent Zero install
- Python 3.11+ (3.12 OK)
- Neo4j 5.x (either **Neo4j Desktop** or **Docker**) if you want GraphRAG ON

### 1) Get the repo

git clone https://github.com/AijooseFactory/graphrag-agent-zero.git
cd graphrag-agent-zero
2) Install the package
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows PowerShell

pip install -U pip
pip install -e .

If the Neo4j driver is packaged as an optional extra:

pip install -e ".[neo4j]"
3) Start Neo4j (choose one)

Option A: Neo4j Desktop
Start Neo4j Desktop and note your Bolt URI (commonly bolt://localhost:7687) and credentials.

Option B: Docker (recommended for users without Desktop)

docker compose -f dev/docker-compose.graphrag-dev.yml up -d neo4j
4) Enable GraphRAG

Set environment variables where Agent Zero runs:

export GRAPH_RAG_ENABLED=true
export NEO4J_URI="bolt://localhost:7688"   # change if using Neo4j Desktop
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-password"

If you don’t set GRAPH_RAG_ENABLED=true, GraphRAG stays off and Agent Zero behaves normally.

5) Verify

Run tests:

pytest -q
Troubleshooting (fast)

If Neo4j is down/unreachable: GraphRAG will no-op; Agent Zero should still run.

If you get “model not found” errors: this extension should not change provider settings; verify your provider/model availability (e.g., for Ollama check /api/tags).
