# Developer Notes

## Project Structure
- `src/graphrag_agent_zero/`: Primary package.
- `dev/`: Isolated dev stack (Neo4j + Agent Zero).
- `tests/`: Unit, Golden, and CI-mock tests.
- `scripts/`: Benchmarking and utility scripts.

## Core Design Principles
1. **Zero Core Patches:** Integration is via hooks only. Do NOT modify `agent-zero-fork/`.
2. **Provider Agnostic:** All LLM calls must use Agent Zero's utility model abstraction.
3. **Upgrade-Safe:** Persistence is limited to `/a0/usr/` in the dev container.
4. **Resilient:** Never crash the agent loop.

## Safe Cypher Templates
When adding new queries, add them to `SAFE_CYPHER_TEMPLATES` in `src/graphrag_agent_zero/safe_cypher.py`. relationship types must be allowlisted separately if they are to be interpolated.

## Testing
Run tests with:
```bash
python3 -m pytest tests/
```
Ensure `neo4j` and `python-dotenv` are installed for full test coverage.
