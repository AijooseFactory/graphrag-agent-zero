# Troubleshooting Guide

### `ModuleNotFoundError: No module named 'numpy.distutils'`
**Cause**: The latest `numpy` (2.0+) removed `distutils`, which `faiss-cpu` relies on for instruction set detection on Python 3.12.
**Fix**: 
1. The repository now includes `numpy<2.0.0` in `requirements.txt`.
2. If the error persists in the container, mock the missing module:
   ```bash
   docker exec agent-zero-graphrag-dev mkdir -p /opt/venv-a0/lib/python3.12/site-packages/numpy/distutils
   docker exec agent-zero-graphrag-dev touch /opt/venv-a0/lib/python3.12/site-packages/numpy/distutils/__init__.py
   docker exec agent-zero-graphrag-dev sh -c "echo 'class CPU:\n    info = [{\"Features\": \"\", \"flags\": \"\"}]' > /opt/venv-a0/lib/python3.12/site-packages/numpy/distutils/cpuinfo.py"
   docker exec agent-zero-graphrag-dev sh -c "echo 'cpu = CPU()' >> /opt/venv-a0/lib/python3.12/site-packages/numpy/distutils/cpuinfo.py"
   docker exec agent-zero-graphrag-dev supervisorctl restart run_ui
   ```

### `ERR_CONNECTION_RESET` or `ERR_SOCKET_NOT_CONNECTED`

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
