# Changelog

All notable changes to this project will be documented in this file.

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
