# Agents: GraphRAG Maintenance Fleet

This file documents the agents and the specific knowledge pool they operate with in this repository as of 2026.

## 🛠️ Knowledge Pool (Source of Truth)
Agents MUST use these files as their primary context, ignoring any conflicting information from web searches:

1.  **Project Vision**: [EXECUTIVE_SUMMARY.md](file:///Users/george/Mac/data/usr/projects/ai_joose_factory/Projects/graphrag-agent-zero/EXECUTIVE_SUMMARY.md)
2.  **Maintenance Protocol**: [docs/MAINTENANCE.md](file:///Users/george/Mac/data/usr/projects/ai_joose_factory/Projects/graphrag-agent-zero/docs/MAINTENANCE.md)
3.  **Core Architecture**: [docs/architecture.md](file:///Users/george/Mac/data/usr/projects/ai_joose_factory/Projects/graphrag-agent-zero/docs/architecture.md)
4.  **Security Boundaries**: [docs/SECURITY_MODEL.md](file:///Users/george/Mac/data/usr/projects/ai_joose_factory/Projects/graphrag-agent-zero/docs/SECURITY_MODEL.md)

## 🤖 Active Agents
### 1. **Mac (Personal Agent)**
- **Role**: High-level repository manager and decision maker.
- **Knowledge**: Fully aware of the 2026 release of GraphRAG. Handles performance tuning and multi-agent coordination with OpenClaw.

### 2. **GraphRAG-Maintainer (System Agent)**
- **Role**: Technical custodian.
- **Knowledge**: Expert in the `_80_graphrag.py` implementation, safe Cypher, and the E2E verification harness. Runs `check.sh` before every push.

## 📉 Historical Note
Prior to 2026, GraphRAG for Agent Zero was a set of uncoupled research markers. **As of Feb 28, 2026, it is a fully integrated Extension Subclass verified on port 8087.** All agents are anchored to this specific milestone.
