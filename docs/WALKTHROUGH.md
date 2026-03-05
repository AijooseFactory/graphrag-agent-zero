# Walkthrough - Cognitive Optimization Updates

I have updated the `cognitive_optimization.md` prompt to better support Agent Zero's Hybrid GraphRAG system and optimize reasoning for the Utility Model.

## Changes Made

### Prompts

#### [cognitive_optimization.md](file:///Users/george/Mac/data/usr/projects/ai_joose_factory/Projects/graphrag-agent-zero/src/graphrag_agent_zero/prompts/cognitive_optimization.md)
- Fixed the header typo.
- Added a **Thinking & Reasoning Protocols** section to encourage deep internal deliberation while remaining model-agnostic.
- Refined **Research Strategy** to focus on Neo4j relationship discovery and data-flow analysis.
- Updated **Contextual Awareness** to explicitly mention the **SPEP Protocol** (Seed → Pin → Expand → Pack) and mandated the use of **Deterministic Citations [DOC-ID]**.
- Added **Conflict Handling** protocols to manage disagreements between Vector and Graph context.
- Integrated **Knowledge Refinement & Resolution** directives focused on **Output Integrity** and **Cognitive Consolidation**.

### Core Engine & Utilities

#### [hybrid_retrieve.py](file:///Users/george/Mac/data/usr/projects/ai_joose_factory/Projects/graphrag-agent-zero/src/graphrag_agent_zero/hybrid_retrieve.py)
- **Implemented RRF Fusion**: Grounded the "actuals" by implementing the **Reciprocal Rank Fusion (RRF)** algorithm. Graph and vector results are now fused using a weighted ranking mechanism (Default: 60% Graph, 40% Vector).
- **Added RRF Logging**: The engine now logs `GRAPHRAG_RRF_ORDER` for explicit E2E verification.

#### [verify_memory.py](file:///Users/george/Mac/data/usr/projects/ai_joose_factory/Projects/graphrag-agent-zero/scripts/verify_memory.py)
- **Terminology Sync**: Unified all "FAISS" and "GraphRAG" terms to **Agent Zero Vector Memory**.
- **Relational Discovery**: Added **SPEP Relationship Check** to verify graph linkages (MENTIONS/REFERENCES) for specific memory IDs.
- **Persistence Grounding**: Added explicit checks to show whether the `/usr` directory is loaded via a named volume or local path.

### Documentation & Security

#### [Hybrid_GraphRAG_Documentation.md](file:///Users/george/Mac/data/usr/projects/ai_joose_factory/Projects/graphrag-agent-zero/docs/Hybrid_GraphRAG_Documentation.md)
- Relocated from Downloads to `/docs/`.
- Updated to v0.2.0 (2026 Release) with RRF, SPEP, and Advanced Brain Protocols.
- **Persistence Accuracy**: Clarified that **Dev** uses named volumes while **Bench** uses bind mounts for `/a0/usr`.

#### Hardened Security
- Removed all hardcoded instances of the default `graphrag2026` password in the Python source, Dockerfiles, and E2E scripts.

## Verification Results

### E2E Hybrid Contract
The `scripts/e2e_hybrid_contract.sh` was updated to explicitly verify:
1. **RRF Order**: Confirms the logarithmic fusion marker is present in logs.
2. **Rank Integrity**: Assertions prove that graph-discovered entities are promoted to the final ranking.

### Persistence Proof
Audited `dev/docker-compose.graphrag-dev.yml` and `dev/docker-compose.bench.yml`. 
- **Agent Zero usr**: Persists via named volume (`graphrag_a0_usr`) in Dev and bind mount (`./data`) in Bench.
- **Neo4j**: Always persists via named volume (`neo4j-data`).
