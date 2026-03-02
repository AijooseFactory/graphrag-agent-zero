# Changelog

All notable changes to this project will be documented in this file.

## [0.1.1] - 2026-03-02
### Fixed
- **Persistent Architecture**: Migrated all GraphRAG extensions to the persistent `usr/extensions/` volume, ensuring configurations and patches survive Docker container recreations.
- **Dynamic Hooking**: Removed dangerous direct file modifications to Agent Zero's `memory.py`. Implemented safe, dynamic Python monkey-patching via the `agent_init` hook.
- **Neo4j Deletion Synchronization**: Deleting memories in Agent Zero now explicitly synchronizes and removes corresponding graph nodes in Neo4j via the `memory_deleted_after` hook.
- **Installation Robustness**: The `install.sh` script now automatically targets Agent Zero's internal virtual environment (`/opt/venv-a0/bin/pip`) to bypass OS-level managed-environment restrictions.
- **Dependency Issues**: Added `nest_asyncio` to `pyproject.toml` to prevent backup script hangs when the extension is installed.

## [0.1.0] - 2026-03-01
### Added
- **Hybrid GraphRAG Contract** — canonical spec at `docs/HYBRID_CONTRACT.md`
- **Evidence-producing E2E** — `summary.json` with git SHA, docker digests, per-case results
- **`scripts/verify.sh`** — single-command release gatekeeper (sanitation + lint + unit + E2E)
- **`docs/RELEASE_CHECKLIST.md`** — pre-release checklist to prevent process drift
- Unit tests for `query_timeout_ms` enforcement and `coalesce(entity_id, id)` query fix
- GitHub Actions CI runs `verify.sh --ci` with artifact upload

### Fixed
- Query timeout now enforced at Neo4j driver level (`session.run(timeout=...)`)
- `get_entities_by_doc` Cypher template supports both `entity_id` and `id` properties
- CI portability: replaced `grep -P` (PCRE) with `grep -E` (POSIX)
- `.env.example` sanitized — removed leaked real password from comment block

### Security
- Secrets gate scans committed files, comments, and markdown code blocks
- `.env` files excluded from version control via `.gitignore`

### Initial Release (2026-02-28)
- Hybrid retrieval combining vector and graph search (SPEP protocol)
- Safe Cypher enforcement with allowlisted templates
- Isolated development stack with Docker Compose
- Provider-agnostic architecture
- Comprehensive documentation and tests
