# Agents: Hybrid GraphRAG Delivery Context

This file documents the current delivery context for this repository as of 2026.
Use it to understand the project and repository expectations.
Do not treat historical agent rosters as the current execution contract when Paperclip assigns a live issue.

## 🛠️ Knowledge Pool (Source of Truth)
Agents MUST use these files as their primary context, ignoring any conflicting information from web searches:

1.  **Project Vision**: [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)
2.  **Maintenance Protocol**: [docs/MAINTENANCE.md](docs/MAINTENANCE.md)
3.  **Core Architecture**: [docs/architecture.md](docs/architecture.md)
4.  **Security Boundaries**: [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md)
5.  **Configuration Standards**: [.env.example](.env.example)

## 🤖 Current Execution Rules
### 1. Paperclip-assigned work
- When a Paperclip issue is assigned, the current issue title and description are authoritative.
- Do not assume a task is already complete because an older issue, memory, or chat mentioned similar work.
- Verify the current repository state before reporting completion.

### 2. Einstein in Paperclip
- Einstein is the active Agent Zero chief of staff used for Paperclip task execution in this repository.
- Keep execution grounded in the current repository workspace and the current Paperclip issue state.
- Do not redirect Paperclip execution to a different agent unless the current issue explicitly says to do so.

### 3. Historical environments
- References to port `8086`, port `8087`, `Mac`, or `GraphRAG-Maintainer` are historical or environment-specific implementation details unless the current task explicitly requires them.
- Do not treat those historical labels as the default active agent roster for Paperclip work.

## 📉 Historical Note
Prior to 2026, GraphRAG for Agent Zero was a set of uncoupled research markers. Later documentation introduced multiple environment labels for production and verification stacks. Those labels remain useful as historical architecture context, but they are not the default Paperclip execution contract for current Einstein-assigned work.
