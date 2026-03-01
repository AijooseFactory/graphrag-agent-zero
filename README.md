# Hybrid GraphRAG for Agent Zero

Add a **Neo4j knowledge graph** to Agent Zero's memory. One safe, auto-applied patch to `memory.py` — everything else is pure extensions.

When enabled, Agent Zero's memories are automatically indexed into a graph and used to enrich every prompt with connected context. When disabled, Agent Zero behaves exactly like stock.

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

Then restart Agent Zero. That's it.

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

## How toVerify Behavior:

Run the one-command verification suite. It spins up an isolated Docker test to explicitly prove:
1. **Hybrid OFF**: Stock memory behavior is completely unchanged.
2. **Hybrid ON**: Memories sync successfully across both vector baseline and graph.
3. **Neo4j Down**: If the graph is unreachable, memory gracefully degrades to stock without throwing exceptions.

```bash
./scripts/verify.sh --ci
```

---

*By [George Freeny Jr.](https://github.com/AijooseFactory) and the Ai joose Factory • MIT License*