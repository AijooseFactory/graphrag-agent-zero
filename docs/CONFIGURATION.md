# Hybrid GraphRAG for Agent Zero - Configuration
# ----------------------------------------------

This document describes the environment variables used to configure the extension.
All variables should be set in your `.env` file in the Agent Zero root directory.

## Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_RAG_ENABLED` | `false` | Primary feature flag. Set to `true` to enable. |
| `GRAPHRAG_ENABLED` | `false` | Alias for `GRAPH_RAG_ENABLED`. |

## Neo4j Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7687` | Connection string for Neo4j. |
| `NEO4J_USER` | `neo4j` | Database username. |
| `NEO4J_PASSWORD` | `<your-password>` | Database password. |
| `NEO4J_DATABASE` | `neo4j` | Database name. |
| `NEO4J_CONNECTION_TIMEOUT_MS` | `5000` | Connection attempt timeout. |
| `NEO4J_QUERY_TIMEOUT_MS` | `10000` | Individual query timeout. |

## Graph Retrieval Strategy

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_EXPAND_MAX_HOPS` | `2` | Max graph traversal depth from seed entities. |
| `GRAPH_EXPAND_LIMIT` | `100` | Max entities returned per expansion query. |
| `GRAPH_MAX_RESULTS` | `50` | Max total results returned to the prompt. |

## Technical Architecture

The system uses a flexible LLM provider layer while requiring Neo4j for high-performance graph traversal.

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT ZERO                                │
│                (Primary Controller)                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              HYBRID GraphRAG SYSTEM                          │
│        (Advanced Retrieval & Context Layer)                 │
├─────────────────────────┬───────────────────────────────────┤
│        Neo4j            │        LLM Provider               │
│   (Required Engine)     │    (Universal Compatibility)      │
│   - Graph Storage       │    - Entity Extraction            │
│   - Topology Queries    │    - LiteLLM Integration          │
└─────────────────────────┴───────────────────────────────────┘
```

## LLM Provider Configuration

The Hybrid GraphRAG extension utilizes the **Utility Model** configured in your Agent Zero `settings.json`. It supports any provider compatible with LiteLLM.

### Example: OpenAI
In your `settings.json`:
```json
{
  "util_model_name": "gpt-4-turbo",
  "util_model_provider": "openai"
}
```

### Example: Anthropic
In your `settings.json`:
```json
{
  "util_model_name": "claude-3-opus-20240229",
  "util_model_provider": "anthropic"
}
```

### Example: Ollama (Local)
In your `settings.json`:
```json
{
  "util_model_name": "llama3.2",
  "util_model_provider": "ollama"
}
```
