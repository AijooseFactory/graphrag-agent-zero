# GraphRAG Extension for Agent Zero (Docker-Verified)

This repository provides a **GraphRAG** extension for **Agent Zero** that injects Neo4j-derived context into the agent’s prompt loop.

## What this does
- Hooks into Agent Zero’s `message_loop_prompts_after` extension point without modifying core files.
- When enabled, queries Neo4j and injects a GraphRAG context block directly into the prompt via `extras_persistent`.
- When Neo4j is unavailable, it cleanly no-ops (no crash) and emits a resilience marker.

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

## Security and Architecture
* No API secrets or internal IPs are committed.
* Local `.env` files are exclusively ignored, except `dev/.env.example`.
* Safe Cypher template engine strictly forbids arbitrary Cypher execution.
* Provider connectivity is handled dynamically during container build.
