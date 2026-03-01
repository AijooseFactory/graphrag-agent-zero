# Maintenance Guide: GraphRAG for Agent Zero

This guide ensures that you (or your personal Agent Zero "Mac") can safely maintain and update this repository.

## 🛠️ Local Verification Chain
Always run the one-command check before committing:
```bash
bash scripts/check.sh
```
This script runs:
1. `ruff` (linting)
2. `pytest` (unit tests)
3. `docker-compose up -d` (dev stack)
4. `bash scripts/e2e.sh` (CLI E2E)

## 🔄 Updating from Upstream
This repo is a fork/vending of Agent Zero. To update:
1. Fetch latest from `agent0ai/agent-zero`.
2. Merge `main` into your local `main`.
3. If conflicts occur in `agents/default/extensions/`, prioritize keeping the `_80_graphrag.py` logic.
4. Run `bash scripts/check.sh` to ensure zero regressions.

## 🐳 Docker Connectivity (Mac/Windows)
If you see `Connection refused` for Ollama:
1. Verify Ollama is running on the host.
2. In the Agent Zero Web UI (port 8087), go to **Settings**.
3. Ensure **API Base** for Ollama is set to `http://host.docker.internal:11434`.
4. This is pre-seeded in the dev volume but can be reset if you clear volumes.

## 🏷️ Releasing
To cut a new version:
1. Update version in `pyproject.toml`.
2. Add entry to `CHANGELOG.md`.
3. `git tag -a v1.0.x -m "Release version 1.0.x"`
4. `git push origin --tags`

## 🛡️ Maintainability Constants
- **Extensions First**: Never patch Agent Zero core. Keep all logic in `src/` and the extension hook.
- **Resilience**: GraphRAG must ALWAYS fail gracefully (log `GRAPHRAG_NOOP_NEO4J_DOWN`).
- **Data Integrity**: Never use `docker compose down -v` unless you intend to wipe all memories.
