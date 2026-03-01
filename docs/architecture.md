# Architecture

GraphRAG for Agent Zero is an extension that enhances the agent's retrieval capabilities with knowledge graph context.

## Component Overview

- **`extension_hook.py`**: The entrypoint for Agent Zero. It intercepts retrieval requests and orchestrates the hybrid retrieval process.
- **`hybrid_retrieve.py`**: The core logic for combining vector results with graph expansion. It performs "entity pinning" and "bounded traversal".
- **`neo4j_connector.py`**: A safe, bounded connection handler for Neo4j. It enforces timeouts and retries.
- **`safe_cypher.py`**: The security enforcement layer. All queries must match allowlisted templates.
- **`graph_builder.py`**: Utilities for indexing documents into the knowledge graph.

## The SPEP Protocol (Seed -> Pin -> Expand -> Pack)

The core retrieval engine follows the **SPEP** protocol to ensure deterministic, high-signal context:
1.  **Seed**: Retrieve the initial document chunk IDs using standard vector search (FAISS/Chromadb).
2.  **Pin**: Extract key entities from the seed documents and "pin" them to the Knowledge Graph.
3.  **Expand**: Perform a bounded, multi-hop expansion in Neo4j from the pinned entities using allowlisted relationships.
4.  **Pack**: Pack the combined vector text and graph relationships into a single, structured context window for the agent.

## Safety Firewall: Safe Cypher

Security is enforced through a strict "No Arbitrary Cypher" policy. 
- All graph interactions must use pre-defined templates in `safe_cypher.py`.
- Parameters are validated and sanitized before execution.
- LLM-generated text never touches the database directly.

## Safety Bounds
The system is designed with a "Failure as NO-OP" philosophy. If Neo4j is unreachable or a query fails, the system gracefully degrades to baseline vector retrieval, ensuring the agent loop never crashes.
