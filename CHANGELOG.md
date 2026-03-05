# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - Planned
### Next-Gen Features
- **Live Interactive Visualization**: Real-time D3/Sigma.js graphical view of the knowledge orbit.
- **Autonomous Entity Resolution**: Background "Consolidation Loop" to merge synonyms and deduplicate the graph.
- **Dynamic Schema Evolution**: LLM-driven discovery of new node/edge types for specialized domains.
- **Graph-Aware Task Routing**: Intelligent executive switching between Vector and Graph retrieval.
- **Multi-Dialect Persistence**: Native support for Memgraph and FalkorDB as alternative backends.
- **Temporal "Self-Healing"**: Knowledge versioning and obsolescence tracking (the `WAS_FORMERLY` state).

## [0.2.0] - 2026-03-05
### Added
- **Universal LLM Architecture**: Complete decoupling of the LLM provider; supports OpenAI, Anthropic, and Ollama via LiteLLM.
- **Enterprise Resilience Layer**: Neo4j Circuit Breaker and Jittered Exponential Backoff.
- **High-Performance Caching**: `LRUTTLCache` for subgraph and context data.
- **Hybrid NER Pipeline**: Two-tier extraction (Fast Heuristic + Deep LLM Reasoning).
- **Cognitive Optimization**: Injected intellectual research framework into core reasoning loop.
- **Real-time Graph Sync**: Automatic `memory_saved_after` hook for instant indexing.
- **Batch Indexing Utility**: New `scripts/batch_index.py` for bulk workspace ingestion.
- **Dead Letter Queue**: Reliable failed-extraction capture at `usr/logs/failed_extractions.jsonl`.
- **Installer v0.2.0**: Added `--verify` diagnostics and support for universal LLM configuration.

### Fixed
- **E2E Isolation**: Patched `scripts/e2e_hybrid_contract.sh` to physically destroy test volumes on cleanup, preventing UI state leakage.
- **State Corruption**: Hardened environment variable management to prevent E2E test stubs from bleeding into production.
- **Branding Scrub**: Removed all instances of internal factory branding and absolute developer paths.

## [0.1.2] - 2026-03-03
### Added
- **High-Fidelity LLM Extraction**: New `LLMExtractor` with "Think and Reason" prompt support and a robust multi-stage JSON parser for better relationship identification.
- **Mandatory Content Persistence**: Documents now always store raw `content` in Neo4j nodes to enable late enrichment and traceability.
- **Improved Relationship Allowlist**: Added `WORKS_ON`, `PART_OF`, and `MEMBER_OF` to the standardized relationship types.
- **Utilities**: Added `enrich_graph.py` for backfilling relationships and `extract_content.py` for diagnostic exports.

### Fixed
- **Extraction Ruggedness**: Multi-stage parser handles models that interleave reasoning text with JSON blocks.
- **Dependency Missing**: Added `litellm`, `neo4j`, and `langchain-community` with explicit version floors to `pyproject.toml`.

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
