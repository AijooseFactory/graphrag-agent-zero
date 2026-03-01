# Security Model

GraphRAG for Agent Zero implements a strict multi-layer security model to ensure safe and reliable retrieval.

## 1. Zero Core Patches
The extension interacts with Agent Zero *only* via official extension hooks. No core files are modified, ensuring upstream compatibility and safety.

## 2. Safe Cypher Enforcement
All database interactions happen through `safe_cypher.py`:
- **Allowlisted Templates:** Only predefined query templates are executed.
- **Parameterization:** All user inputs are parameterized; No string interpolation in queries.
- **No LLM Cypher:** The LLM *never* generates Cypher directly.

## 3. Resource Bounds
- **Hops:** Graph traversal is strictly capped at 2 hops.
- **Entities:** Retrieval is limited to 100 entities per query to prevent OOM.
- **Timeouts:** Database queries have a 10s hard timeout.

## 4. Isolation
The development stack uses unique ports and named volumes to prevent data leakage and port conflicts with other services.
