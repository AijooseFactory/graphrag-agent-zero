# Troubleshooting Guide

## Neo4j Connectivity Issues
- **Error:** `Neo4j driver not available` or `Neo4j health check failed`.
- **Check:** Ensure the DBMS is running in `dev/` using `docker compose ps`.
- **Check:** Verify `NEO4J_URI` matches the host port (7688).
- **Diagnostics:** Run `curl http://localhost:7475` from the host.

## GraphRAG Not Activating
- **Check:** Ensure `GRAPH_RAG_ENABLED=true` is set in the environment.
- **Check:** Verify logs for "GraphRAG enabled but Neo4j unavailable".
- **Check:** If using Ollama, ensure the model is reachable.

## Performance Issues
- **Problem:** Retrieval is slow (>5s).
- **Solution:** Check `NEO4J_QUERY_TIMEOUT_MS`. The default is 10s.
- **Solution:** Reduce `GRAPH_EXPAND_LIMIT` (default 100).
- **Solution:** Check Neo4j memory settings in `docker-compose.graphrag-dev.yml`.

## Security Blocked Query
- **Error:** `Attempted to execute unauthorized template`.
- **Reason:** A query was attempted that is not in the `safe_cypher.py` allowlist.
- **Action:** Add the template to `safe_cypher.py` if it follows security guidelines.
