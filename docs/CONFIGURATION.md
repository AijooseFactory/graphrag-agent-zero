# Configuration Reference

All Hybrid GraphRAG settings are controlled via environment variables in your Agent Zero `.env` file.

## Feature Flag

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_RAG_ENABLED` | `false` | Master switch. Set to `true` to enable Hybrid GraphRAG. |

## Neo4j Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt endpoint. Use `bolt://host.docker.internal:7687` if Agent Zero runs in Docker and Neo4j runs on the host. |
| `NEO4J_USER` | `neo4j` | Neo4j username. |
| `NEO4J_PASSWORD` | `graphrag2026` | Neo4j password. **Change this.** |
| `NEO4J_DATABASE` | `neo4j` | Neo4j database name. |

## Timeouts

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_CONNECTION_TIMEOUT_MS` | `5000` | Connection timeout in milliseconds. |
| `NEO4J_QUERY_TIMEOUT_MS` | `10000` | Per-query timeout in milliseconds. |

## Graph Expansion Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_EXPAND_MAX_HOPS` | `2` | Max graph traversal depth from seed entities. |
| `GRAPH_EXPAND_LIMIT` | `100` | Max entities returned per expansion query. |
| `GRAPH_MAX_RESULTS` | `50` | Max total results returned to the prompt. |
