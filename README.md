# 🧠 Hybrid GraphRAG for Agent Zero  

Agent Zero is deliberately designed to keep the core framework as simple and modular as possible, and push “bigger” or more opinionated capabilities into the extensions system. Their docs explicitly describe extensibility as the way to enhance behavior, and note that Plugins can be used to keep the main codebase clean and organized.

Hybrid GraphRAG for Agent Zero is an intelligence-boosting Agent Zero Plugin that adds a structured Neo4j knowledge graph on top of native memory, so the agent doesn’t just retrieve text snippets. It can understand how your information connects, follow relationships across your corpus, and use that structure to deliver clearer, more grounded responses.

Instead of treating your data as isolated chunks, Hybrid GraphRAG helps Agent Zero connect people, projects, systems, and concepts across documents and time. That means it can uncover dependencies that aren’t obvious from simple similarity search alone and provide more complete context when making recommendations or explaining decisions.

Hybrid GraphRAG for Agent Zero also improves reliability by grounding outputs in explicit entities and relationships. This reduces confusion in cases where the same term can mean different things in different contexts, and it makes the agent’s conclusions easier to verify because the supporting links and sources can be traced back to the underlying graph and memory.

For everyday use, Hybrid GraphRAG for Agent Zero helps Agent Zero act more like a well-read assistant that understands how your notes, documents, and decisions connect. It can help you trace “why” something is true by following links between people, projects, topics, and files, catch related context you might have missed, and keep long-running work coherent across weeks or months. It’s especially useful when you’re juggling lots of information, revisiting older material, comparing versions of ideas, or trying to understand dependencies and relationships across a large pile of documents.

The bottom line is, without Hybrid GraphRAG for Agent Zero Plugin, Agent Zero primarily retrieves relevant snippets; with Hybrid GraphRAG, it can reason across your knowledge using entities and relationships, producing better context, clearer explanations, and more trustworthy results.

---

## Install on existing Agent Zero

Ensure you have a working installation of Agent Zero. If not, you can install it by following the instructions in the [Agent Zero documentation](https://github.com/agent-zero/agent-zero).

Then clone this repository:

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
NEO4J_DATABASE=<your db or leave blank for default>
```

Then restart Agent Zero.

### Verify Installation
You can verify that your Agent Zero Vector Memory store and Neo4j graph are correctly aligned by running the verification script from within your Agent Zero directory:

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

## How Hybrid GraphRAG works (Agent Zero + this Extension)

Hybrid GraphRAG is additive: Agent Zero’s native memory continues to work normally, and this extension adds a Neo4j knowledge-graph layer when enabled.

When Agent Zero runs, this extension hooks into the agent lifecycle and does three things:

1) **Memory stays native**
Agent Zero still saves and recalls memories using its existing vector-based memory system. Nothing about the default memory loop is replaced.

2) **Graph sync (when enabled)**
When `GRAPHRAG_ENABLED=true`, newly saved (and deleted) memories can be indexed into Neo4j so documents, entities, and relationships stay in sync over time. If Neo4j is unavailable, syncing no-ops safely.

3) **Hybrid retrieval + prompt injection**
On each user message, the extension:
- uses the normal memory/vector results as a **seed** when available,
- maps those results to graph entities,
- expands through allowlisted relationships (bounded by hard caps),
- packs the result into a GraphRAG context block,
- injects that block into the prompt **in addition to** native memory context.

If GraphRAG is disabled, there are **zero** Neo4j calls and Agent Zero behaves as stock. If enabled but Neo4j is down or retrieval is empty, the extension cleanly no-ops without crashing.

### What to check in logs (expected markers)
- `GRAPHRAG_EXTENSION_EXECUTED`
- `GRAPHRAG_CONTEXT_INJECTED` (enabled + Neo4j reachable + non-empty context)
- `GRAPHRAG_NOOP_NEO4J_DOWN` (enabled + Neo4j unreachable)
- `GRAPHRAG_NOOP_EMPTY_CONTEXT` (enabled + retrieval empty)

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
2. **Hybrid ON**: Memories sync successfully across both Agent Zero Vector Memory and Neo4j graph.
3. **Neo4j Down**: If the graph is unreachable, memory gracefully degrades to stock without throwing exceptions.

```bash
./scripts/verify.sh --ci
```

---

*By [George Freeney Jr.](https://github.com/AijooseFactory) and the Ai joose Factory • MIT License*
