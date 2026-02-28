# Systems Map

## Component Registry

| Current Name | Former Name | Type | Port | Status |
|--------------|-------------|------|------|--------|
| Gateway | EdgeProxy | API Gateway | 8080 | Active |
| Auth Service | - | Authentication | 8081 | Active |
| User Database | - | PostgreSQL | 5432 | Active |
| Neo4j Database | - | Graph DB | 7687 | Active |
| Routing Service | - | Internal Router | 8082 | Active |
| Agent Zero | - | AI Assistant | 80 | Active |

## Renamed Components

### Gateway (formerly EdgeProxy)
- **Renamed:** 2026-01-10 via ADR-001
- **Reason:** Clarify role as API gateway, not edge computing
- **Historical References:** EdgeProxy references in incidents/changes should note "(now Gateway)"

## Component Relationships

```
External Request
       │
       ▼
   Gateway ──────► Auth Service ──────► User Database
       │
       ▼
 Routing Service
       │
       ▼
  Agent Zero ──────► Neo4j Database ──────► Persistent Volume
```
