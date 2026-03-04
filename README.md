# Hybrid GraphRAG for Agent Zero (v0.2.0)

Add a **Neo4j knowledge graph** to Agent Zero's memory. Fully dynamic and persistent — uses safe `agent_init` hooks to integrate cleanly without touching or modifying Agent Zero's core files.

### 🌟 New in v0.2.0: Resilience & Cognitive Optimization
- **Cognitive Optimization**: Injects a mission-critical "Intellectual Research" framework into the agent's core reasoning system.
- **Enterprise Resilience**: Adaptive Neo4j Circuit Breaker and Jittered Exponential Backoff for mission-critical reliability.
- **Hybrid Retrieval (SPEP v2)**: High-performance LRU+TTL caching and tiered extraction (Hybrid NER) to slash token costs and latency.
- **Real-time Sync**: Automatic graph indexing of new memories via the `memory_saved_after` extension hook.

---

## Install into an existing Agent Zero

```bash
git clone https://github.com/AijooseFactory/graphrag-agent-zero.git
cd graphrag-agent-zero
# Run the installer targeting your local Agent Zero path
./scripts/install.sh /path/to/your/agent-zero
```

The installer handles everything: Python package, extensions, config, and the memory hook.

After install, edit your Agent Zero `.env` to configure your Neo4j connection and enable the feature:

```env
# Enable the GraphRAG feature
GRAPH_RAG_ENABLED=true

# Neo4j Connection Details
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<your-password>
```

Then restart Agent Zero.

### Verify Installation
You can verify that your FAISS index and Neo4j graph are correctly aligned by running the verification script from within your Agent Zero directory:

```bash
# General health check
python scripts/verify_memory.py

# Check specifically for expected memory IDs
python scripts/verify_memory.py --present <memory_id_1>,<memory_id_2>
```
If this check fails, you can use your Agent Zero Agent to diagnose and fix the issue.

---

## What happens When ...?

| Mode | Behavior |
|------|----------|
| **Enabled + Neo4j up** | Memories sync to the graph automatically. Prompts include graph context. |
| **Enabled + Neo4j down** | Agent Zero works normally. Graph features silently skip. |
| **Disabled** | Stock Agent Zero. No graph calls, no overhead. |

---

## Docs

- [Hybrid Contract Spec](docs/HYBRID_CONTRACT.md) — what "Hybrid" means and how it's tested
- [Configuration Reference](docs/CONFIGURATION.md) — all environment variables
- [Release Checklist](docs/RELEASE_CHECKLIST.md)
- [Changelog](CHANGELOG.md)

---

## How to Verify Behavior:

Run the one-command verification suite. It spins up an isolated Docker test to explicitly prove:
1. **Hybrid OFF**: Stock memory behavior is completely unchanged.
2. **Hybrid ON**: Memories sync successfully across both vector baseline and graph.
3. **Neo4j Down**: If the graph is unreachable, memory gracefully degrades to stock without throwing exceptions.

```bash
./scripts/verify.sh --ci
```

---

*By [George Freeny Jr.](https://github.com/AijooseFactory) and the Ai joose Factory • MIT License*
