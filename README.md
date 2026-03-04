# Hybrid GraphRAG for Agent Zero

Add a **Neo4j knowledge graph** to Agent Zero's memory. Fully dynamic and persistent — uses safe `agent_init` hooks to integrate cleanly without touching or modifying Agent Zero's core files.

When enabled, Agent Zero's memories are automatically indexed into a graph using **high-fidelity LLM extraction** and used to enrich every prompt with connected context. Documents are fully persisted with raw content in Neo4j, enabling late enrichment and deep traceability. When disabled, Agent Zero behaves exactly like stock. Survives Docker container restarts and wipes automatically since everything lives in the `usr/` volume.

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
