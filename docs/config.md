# Configuration Guide

The extension is configured via environment variables.

## Feature Flags
| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_RAG_ENABLED` | `false` | Enable/Disable GraphRAG enhancement |

## Neo4j Connection
| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7687` | Connection URI |
| `NEO4J_USER` | `neo4j` | Username |
| `NEO4J_PASSWORD` | `graphrag2026` | Password |
| `NEO4J_DATABASE` | `neo4j` | Database name |

## Retrieval Settings
| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_EXPAND_MAX_HOPS` | `2` | Max hops to expand (cap at 2) |
| `GRAPH_EXPAND_LIMIT` | `100` | Max entities per query |
| `GRAPH_MAX_RESULTS` | `50` | Max document IDs returned |
| `NEO4J_QUERY_TIMEOUT_MS` | `10000` | Query timeout in milliseconds |

## Usage
Environment variables should be set in the host environment or defined in a `.env` file at the project root. 

A template is provided at **[.env.example](file:///Users/george/Mac/data/usr/projects/ai_joose_factory/Projects/graphrag-agent-zero/.env.example)**. Copy this to `.env` to get started. The extension will *not* override existing environment variables.
