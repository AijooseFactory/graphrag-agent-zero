# GraphRAG Extension for Agent Zero (Docker-Verified)

This repository provides a **GraphRAG** extension for **Agent Zero** that injects Neo4j-derived context into the agent’s prompt loop.

## What this does
- Hooks into Agent Zero’s `message_loop_prompts_after` extension point without modifying core files.
- When enabled, queries Neo4j and injects a GraphRAG context block directly into the prompt via `extras_persistent`.
- When Neo4j is unavailable, it cleanly no-ops (no crash) and emits a resilience marker.

## Top 1% Perfect Commitment
This integration is built around a "Top 1% PERFECT" standard, ensuring that no Pull Requests will be refused to the upstream [agent0ai/agent-zero](https://github.com/agent0ai/agent-zero) repository due to integration failures or regressions. 

*Contributors:* **George Freeny Jr.** (who forked Agent Zero to pioneer this integration and aspires to be a core contributor) and the **Ai joose Factory**.

## Verification Guarantees
This repo includes a deterministic, keyless End-to-End (E2E) testing harness:
- Runs Agent Zero + Neo4j + an OpenAI-compatible LLM stub locally in Docker.
- Proves extension execution via strict log markers:
  - `GRAPHRAG_EXTENSION_EXECUTED`
  - `GRAPHRAG_CONTEXT_INJECTED`
  - `GRAPHRAG_NOOP_NEO4J_DOWN`
- Validates memory receipt injection end-to-end to verify that the LLM stub successfully detects the injected graph sentinel.

## Quickstart
```bash
# 1. Provide a dummy configuration to run the keyless E2E stub environment
cp dev/.env.example dev/.env

# 2. Start the isolated dev stack (Agent Zero + Neo4j + LLM Stub)
docker compose -f dev/docker-compose.graphrag-dev.yml up -d --build

# 3. Verify the Agent Zero web interface has come online
curl -I http://localhost:8087
```

## Run E2E Verification (Hard Gate)

```bash
chmod +x scripts/e2e.sh
./scripts/e2e.sh
```

## Extension-First Documentation (For Agent Zero Builders)
This repository is architected explicitly for developers building on top of the Agent Zero extension framework.

* **Hook Point:** `message_loop_prompts_after`
* **Override Location:** `agents/default/extensions/message_loop_prompts_after/_80_graphrag.py`
* **Ordering Rule:** The `_80_` prefix ensures this extension runs *late* in the prompt assembly phase, guaranteeing it injects context right before the LLM call without overriding core system prompts (`_10_` or `_20_`).
* **Source Logic:** Core retrieval processing is maintained cleanly in `src/graphrag_agent_zero/`.

### Verification Markers
The extension proves its execution deterministicly through standard output:
- `GRAPHRAG_BASE_EXTENSION_EXECUTED` (proves baseline precedence loading, intentionally overridden by profiles).
- `GRAPHRAG_AGENT_EXTENSION_EXECUTED` (proves the agent profile override successfully won the load order).
- `GRAPHRAG_CONTEXT_INJECTED` (proves successful Neo4j query and memory injection).
- `GRAPHRAG_CONTEXT_SHA256=<hash>` (verifies cryptographic integrity of the context block).
- `GRAPHRAG_HOOKPOINT=message_loop_prompts_after` (guarantees the extension executed in the declared phase).
- `GRAPHRAG_NOOP_NEO4J_DOWN` (proves side-effect safety when Neo4j is offline).

### How to Add Your Own Extension
1. Clone your extension script into `agents/<your_profile>/extensions/<hook_point>/<filename>.py`.
2. Follow the chronological prefixing (`_10_`, `_50_`, `_99_`) to determine execution override order.

## Security and Architecture
* No API secrets or internal IPs are committed.
* Local `.env` files are exclusively ignored, except `dev/.env.example`.
* Safe Cypher template engine strictly forbids arbitrary Cypher execution.
* Provider connectivity is handled dynamically during container build.