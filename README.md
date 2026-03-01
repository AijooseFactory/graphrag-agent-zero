# Hybrid GraphRAG for Agent Zero

**Hybrid GraphRAG for Agent Zero** is a public extension that adds a **Neo4j knowledge graph layer** to Agent Zero's existing memory loop.

- **Enabled:** Agent Zero continues to use its native memory features *and* also injects graph-derived context (Hybrid = **Memory + Graph**).
- **Disabled:** Agent Zero behaves like stock (no graph calls, no graph prompt blocks).

This repo includes a hard-gated contract spec and tests to prove the Hybrid behavior.

---

## What this adds (and what it does not)

### Adds
- **Hybrid retrieval:** vector/memory retrieval + Neo4j graph expansion combined.
- **SPEP pipeline:** Seed → Pin → Expand → Pack with bounded expansion and safe limits.
- **Safe Cypher:** allowlisted, parameterized graph queries (no arbitrary Cypher execution).
- **Graceful fallback:** if Neo4j is down, GraphRAG no-ops and Agent Zero continues normally.
- **Auto-sync on save:** newly saved Agent Zero memories are automatically indexed to Neo4j via the `memory_saved_after` hook when enabled.

### Does not
- Replace Agent Zero memory
- Require you to change how you use Agent Zero day-to-day
- Break Agent Zero if Neo4j is unavailable

---

## Requirements

- **Agent Zero** installed and running normally
- **Neo4j 5.x** reachable from your Agent Zero runtime (local or remote)
- **Python 3.10+**

---

## Install

There are three steps:

1. Install the Python package (retriever + Neo4j connector)
2. Copy the extension files into your Agent Zero installation
3. Configure environment variables

### Step 1 — Install the Python package

```bash
git clone https://github.com/AijooseFactory/graphrag-agent-zero.git
cd graphrag-agent-zero
pip install -e ".[neo4j]"
```

> **Note:** Run this inside the same Python environment that Agent Zero uses.
> If Agent Zero runs in Docker, install the package inside the container or
> bake it into your Dockerfile.

### Step 2 — Copy extension files into Agent Zero

Copy the following files from this repo into your Agent Zero installation:

```bash
# Replace <A0_ROOT> with your Agent Zero installation path (e.g. /a0)

# 2a. Prompt injection extension (injects graph context into the LLM prompt)
cp agent-zero-fork/agents/default/extensions/message_loop_prompts_after/_80_graphrag.py \
   <A0_ROOT>/agents/default/extensions/message_loop_prompts_after/

# 2b. Auto-sync extension (indexes new memories into Neo4j on save)
cp agent-zero-fork/python/extensions/memory_saved_after/_80_graphrag_sync.py \
   <A0_ROOT>/python/extensions/memory_saved_after/

# 2c. Prompt template (used by the prompt injection extension)
cp agent-zero-fork/prompts/agent.system.graphrag.md \
   <A0_ROOT>/prompts/
```

> **Note:** Create any missing directories before copying
> (e.g. `mkdir -p <A0_ROOT>/python/extensions/memory_saved_after`).

### Step 3 — Configure environment variables

Copy the example config and edit it:

```bash
cp .env.example <A0_ROOT>/.env
```

Then set:

```env
# Enable Hybrid GraphRAG
GRAPH_RAG_ENABLED=true

# Neo4j connection
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<your-neo4j-password>
```

If Agent Zero runs in Docker but Neo4j runs on the host:
```env
NEO4J_URI=bolt://host.docker.internal:7687
```

### Step 4 (Optional) — Auto-sync fork patch

The auto-sync feature requires a small addition to Agent Zero's `memory.py` to fire
the `memory_saved_after` extension point. If you are using the forked Agent Zero
included in this repo (`agent-zero-fork/`), this patch is already applied.

If you are using **upstream Agent Zero**, apply this one-line change to
`python/helpers/memory.py` in the `insert_text` method:

```diff
 async def insert_text(self, text, metadata: dict = {}):
     doc = Document(text, metadata=metadata)
     ids = await self.insert_documents([doc])
+
+    # Fire memory_saved_after extensions (e.g. GraphRAG sync)
+    try:
+        from python.helpers.extension import call_extensions
+        await call_extensions(
+            "memory_saved_after", agent=None,
+            text=text, metadata=metadata, doc_id=ids[0],
+            memory_subdir=self.memory_subdir,
+        )
+    except Exception:
+        pass  # Never break memory save
+
     return ids[0]
```

This patch is fully exception-isolated — it cannot break Agent Zero's memory saves.

---

## Verify

```bash
# Run all verification gates (lint, unit tests, secrets scan)
./scripts/verify.sh --ci
```

For full E2E verification with Docker:
```bash
./scripts/verify.sh
```

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_RAG_ENABLED` | `false` | Master switch for Hybrid GraphRAG |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt endpoint |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `graphrag2026` | Neo4j password |
| `NEO4J_DATABASE` | `neo4j` | Neo4j database name |
| `NEO4J_CONNECTION_TIMEOUT_MS` | `5000` | Connection timeout (ms) |
| `NEO4J_QUERY_TIMEOUT_MS` | `10000` | Per-query timeout (ms) |
| `GRAPH_EXPAND_MAX_HOPS` | `2` | Max graph traversal depth |
| `GRAPH_EXPAND_LIMIT` | `100` | Max entities per expansion |
| `GRAPH_MAX_RESULTS` | `50` | Max results returned |

---

## Architecture

```
Agent Zero message loop
  ├── Native memory recall (unchanged)
  └── GraphRAG extension (additive)
        ├── _80_graphrag.py          → injects graph context into prompt
        ├── _80_graphrag_sync.py     → indexes new memories to Neo4j
        └── src/graphrag_agent_zero/ → retriever, connector, safe cypher
```

- **No core patches required** (except the optional `memory_saved_after` hook for auto-sync).
- **Safe Cypher only** — all Neo4j queries use allowlisted, parameterized templates.
- **Contract spec** — see [`docs/HYBRID_CONTRACT.md`](docs/HYBRID_CONTRACT.md) for the full specification.

---

## License

MIT

---

*Contributors:* **George Freeny Jr.** and the **Ai joose Factory**.