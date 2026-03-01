# Extension Compatibility Matrix

| Component | Version Constraint | Notes |
| :--- | :--- | :--- |
| **Agent Zero** | `>= 0.8.0` | Requires the `message_loop_prompts_after` extension point and `extras_persistent` mapping. |
| **Neo4j** | `^5.0.0` | Requires APOC if advanced graphing expands. Tested on `5.17-community`. |
| **Python** | `>= 3.10` | Uses modern Python typing and asyncio primitives. |
| **graphrag_agent_zero** | `1.0.x` | The core retrieval package provided in `src/`. |

_Note: This extension actively prevents Agent Zero from crashing during incompatibilities by catching exceptions and no-opping gracefully._
