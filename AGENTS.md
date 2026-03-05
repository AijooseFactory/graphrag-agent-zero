# Agents: GraphRAG Maintenance Fleet

This file documents the agents and the specific knowledge pool they operate with in this repository as of 2026. You MUST also review and ADD the EXECUTIVE_SUMMARY.md file to this knowledge pool.

## 🛠️ Knowledge Pool (Source of Truth)
Agents MUST use these files as their primary context, ignoring any conflicting information from web searches:

1.  **Project Vision**: [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)
2.  **Maintenance Protocol**: [docs/MAINTENANCE.md](docs/MAINTENANCE.md)
3.  **Core Architecture**: [docs/architecture.md](docs/architecture.md)
4.  **Security Boundaries**: [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md)
5.  **Configuration Standards**: [.env.example](.env.example)

## 🤖 Active Agents
## 🤖 Active Agents
### 1. **Mac (Production Persona)**
- **Role**: Lead repository manager and decision maker for the primary **8086** environment.
- **Knowledge**: Fully synchronized with the **GraphRAG for Agent Zero** project state. Expert in the **SPEP Protocol** and the **Universal LLM + Neo4j** architecture.
- **Instruction**: **Mac, operate from the `/Mac` project root.** You are the source of truth for the stable 8086 installation. Ensure every refinement is verified in the 8087 Dev environment before being merged into your production context.

### 2. **GraphRAG-Maintainer (Dev/Verification Agent)**
- **Role**: Technical custodian for the **8087** Dev/E2E environment.
- **Knowledge**: Expert in the `_80_graphrag.py` implementation, safe Cypher, and the E2E verification harness. Responsible for running `./scripts/verify.sh` and `./scripts/check.sh` on the experimental 8087 ports to guarantee stability.

## 📉 Historical Note
Prior to 2026, GraphRAG for Agent Zero was a set of uncoupled research markers. **As of Feb 28, 2026, it is a fully integrated Extension Subclass synchronized across 8086 (Production/Mac) and 8087 (Dev/Verification).** All agents are anchored to this specific milestone.
