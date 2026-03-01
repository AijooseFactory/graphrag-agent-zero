# Contributing to GraphRAG for Agent Zero

Thank you for your interest in contributing!

## Code of Conduct
Please be respectful and professional in all interactions.

## How to Contribute
1.  **Pull Requests**:
    - All code changes MUST be verified by the E2E harness (`bash scripts/check.sh`).
    - New graph queries MUST be added as templates to `src/graphrag_agent_zero/safe_cypher.py`.
    - NEVER execute arbitrary Cypher strings in the application code.
2.  **Standards**:
    - Follow the "Failure as NO-OP" pattern: all external service calls (Neo4j) must fail gracefully.
    - Maintain E2E test markers to ensure observability.

## Security
If you find a security vulnerability, please do NOT open a public issue. Instead, contact the maintainers privately.
