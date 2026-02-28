# System Dependencies

## Service Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Zero                              │
│                    (AI Assistant)                            │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Neo4j Database                            │
│              (Entity Relationships)                           │
│              Port: 7687 (bolt)                                │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  Persistent Volume                            │
│                   (Data Storage)                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                       Gateway                                 │
│                   (API Gateway)                               │
│                    Port: 8080                                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Auth Service                               │
│                   (Authentication)                            │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   User Database                               │
│                (Credential Store)                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   Routing Service                             │
│                    (Internal)                                 │
└─────────────────────────────────────────────────────────────┘
```

## Critical Paths

| From | To | Dependency Type | Impact if Down |
|------|-----|-----------------|----------------|
| Agent Zero | Neo4j Database | Required for GraphRAG | Degrades to vector-only |
| Neo4j Database | Persistent Volume | Critical | Graph unavailable |
| Gateway | Auth Service | Critical | No authentication |
| Auth Service | User Database | Critical | No credential verification |
| Gateway | Routing Service | Required | Request routing fails |

## Failure Cascades

1. **User Database Down** → Auth Service fails → Gateway cannot authenticate users → All external requests fail
2. **Persistent Volume Down** → Neo4j cannot persist data → Agent Zero GraphRAG degrades to baseline
3. **Gateway Down** → All external traffic blocked → System isolated
