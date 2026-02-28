# Safe Cypher Templates v1.0

> **Purpose:** Allowlisted, parameterized Cypher queries for GraphRAG retrieval.
> **Constraint:** No arbitrary Cypher from LLM. All queries must use these templates.

---

## Safety Rules

| Rule | Enforcement |
|------|-------------|
| Max hops | 2 (hard limit) |
| Max results | 100 (hard ceiling) |
| Query timeout | 30 seconds |
| Write operations | BLOCKED |
| Arbitrary procedures | BLOCKED |
| Parameterized only | REQUIRED |
| Relationship allowlist | REQUIRED |

---

## Template 1: Entity Lookup

**Purpose:** Find entities by name or ID (supports name variants).

```cypher
MATCH (e:Entity)
WHERE e.id = $entity_id 
   OR e.name = $entity_name 
   OR $entity_name IN e.aliases
RETURN e.id, e.name, e.type, e.aliases
LIMIT $limit
```

| Parameter | Type | Required | Default | Max |
|-----------|------|----------|---------|-----|
| entity_id | string | No | null | - |
| entity_name | string | No | null | - |
| limit | int | No | 10 | 100 |

---

## Template 2: Entity Neighbors (1-hop)

**Purpose:** Get direct relationships of an entity.

```cypher
MATCH (e:Entity {id: $entity_id})-[r]-(neighbor:Entity)
WHERE type(r) IN $relationships
RETURN e.id as entity, 
       type(r) as relationship, 
       neighbor.id as neighbor_id,
       neighbor.name as neighbor_name,
       neighbor.type as neighbor_type
LIMIT $limit
```

| Parameter | Type | Required | Default | Max |
|-----------|------|----------|---------|-----|
| entity_id | string | Yes | - | - |
| relationships | list | No | ['*'] | 20 |
| limit | int | No | 20 | 100 |

---

## Template 3: Entity Neighbors (2-hop)

**Purpose:** Expand entity context with second-degree relationships.

```cypher
MATCH (e:Entity {id: $entity_id})-[r1]-(n1:Entity)-[r2]-(n2:Entity)
WHERE type(r1) IN $relationships 
  AND type(r2) IN $relationships
  AND n2.id <> $entity_id
RETURN DISTINCT 
    e.id as source,
    type(r1) as hop1_rel,
    n1.id as hop1_entity,
    type(r2) as hop2_rel,
    n2.id as hop2_entity,
    n2.name as hop2_name
LIMIT $limit
```

| Parameter | Type | Required | Default | Max |
|-----------|------|----------|---------|-----|
| entity_id | string | Yes | - | - |
| relationships | list | No | ['*'] | 20 |
| limit | int | No | 50 | 100 |

---

## Template 4: Name Variant Resolution

**Purpose:** Resolve name variants to canonical entity.

```cypher
MATCH (e:Entity)
WHERE e.name = $name 
   OR $name IN e.aliases
   OR e.name CONTAINS $name
   OR ANY(alias IN e.aliases WHERE alias CONTAINS $name)
RETURN e.id, e.name, e.aliases, e.type
LIMIT $limit
```

| Parameter | Type | Required | Default | Max |
|-----------|------|----------|---------|-----|
| name | string | Yes | - | - |
| limit | int | No | 5 | 20 |

---

## Template 5: Document References

**Purpose:** Find all entities referenced by a document.

```cypher
MATCH (d:Document {id: $doc_id})-[:REFERENCES|MENTIONS]->(e:Entity)
RETURN d.id as document, 
       e.id as entity_id, 
       e.name as entity_name, 
       e.type as entity_type
LIMIT $limit
```

| Parameter | Type | Required | Default | Max |
|-----------|------|----------|---------|-----|
| doc_id | string | Yes | - | - |
| limit | int | No | 50 | 100 |

---

## Template 6: Dependency Chain

**Purpose:** Trace system dependencies up to 2 hops.

```cypher
MATCH (s:System {id: $system_id})-[:DEPENDS_ON*1..2]->(dep:System)
RETURN DISTINCT 
    s.id as source_system,
    dep.id as dependent_system,
    dep.name as dependent_name,
    dep.status as status
LIMIT $limit
```

| Parameter | Type | Required | Default | Max |
|-----------|------|----------|---------|-----|
| system_id | string | Yes | - | - |
| limit | int | No | 20 | 100 |

---

## Template 7: Incident Impact

**Purpose:** Find systems and changes related to an incident.

```cypher
MATCH (i:Incident {id: $incident_id})
OPTIONAL MATCH (i)-[:AFFECTS]->(s:System)
OPTIONAL MATCH (i)-[:RESOLVED_BY]->(c:Change)
OPTIONAL MATCH (i)-[:CAUSED_BY]->(root:Entity)
RETURN i.id as incident,
       i.title as title,
       collect(DISTINCT s.id) as affected_systems,
       collect(DISTINCT c.id) as resolving_changes,
       collect(DISTINCT root.id) as root_causes
LIMIT $limit
```

| Parameter | Type | Required | Default | Max |
|-----------|------|----------|---------|-----|
| incident_id | string | Yes | - | - |
| limit | int | No | 1 | 10 |

---

## Template 8: Document Resolution Chain

**Purpose:** 2-hop document traversal for multi-hop reasoning.

```cypher
MATCH (d1:Document {id: $doc_id})-[:REFERENCES]->(d2:Document)
OPTIONAL MATCH (d2)-[:REFERENCES]->(d3:Document)
RETURN DISTINCT
    d1.id as source_doc,
    d2.id as hop1_doc,
    d3.id as hop2_doc
LIMIT $limit
```

| Parameter | Type | Required | Default | Max |
|-----------|------|----------|---------|-----|
| doc_id | string | Yes | - | - |
| limit | int | No | 20 | 100 |

---

## Template 9: Change to Incident

**Purpose:** Find incidents related to a change.

```cypher
MATCH (c:Change {id: $change_id})
OPTIONAL MATCH (c)<-[:RESOLVED_BY]-(i:Incident)
OPTIONAL MATCH (c)-[:MODIFIES]->(s:System)
RETURN c.id as change,
       c.title as title,
       collect(DISTINCT i.id) as related_incidents,
       collect(DISTINCT s.id) as modified_systems
LIMIT $limit
```

| Parameter | Type | Required | Default | Max |
|-----------|------|----------|---------|-----|
| change_id | string | Yes | - | - |
| limit | int | No | 1 | 10 |

---

## Template 10: ADR Approval Chain

**Purpose:** Find who authored and approved an ADR.

```cypher
MATCH (a:ADR {id: $adr_id})
OPTIONAL MATCH (a)<-[:AUTHORED_BY]-(author:Person)
OPTIONAL MATCH (a)<-[:APPROVED_BY]-(approver:Person)
RETURN a.id as adr,
       a.title as title,
       author.id as author_id,
       author.name as author_name,
       approver.id as approver_id,
       approver.name as approver_name
LIMIT $limit
```

| Parameter | Type | Required | Default | Max |
|-----------|------|----------|---------|-----|
| adr_id | string | Yes | - | - |
| limit | int | No | 1 | 10 |

---

## Implementation Requirements

### 1. Query Execution Flow

```python
async def execute_safe_query(
    template_name: str,
    params: dict,
    neo4j_session: AsyncSession
) -> list[dict]:
    # 1. Validate template exists
    if template_name not in TEMPLATE_REGISTRY:
        raise ValueError(f"Unknown template: {template_name}")
    
    # 2. Validate parameters
    template = TEMPLATE_REGISTRY[template_name]
    validate_params(template, params)
    
    # 3. Apply defaults and enforce limits
    params = apply_param_limits(template, params)
    
    # 4. Execute with timeout
    async with asyncio.timeout(QUERY_TIMEOUT_SECONDS):
        result = await neo4j_session.run(template.cypher, params)
        return [record async for record in result]
```

### 2. Parameter Validation

```python
def validate_params(template: Template, params: dict) -> None:
    for param in template.required_params:
        if param.name not in params:
            raise ValueError(f"Missing required parameter: {param.name}")
        
        if param.max and params.get(param.name, param.default) > param.max:
            raise ValueError(f"Parameter {param.name} exceeds max: {param.max}")
```

### 3. Relationship Allowlist Enforcement

```python
ALLOWED_RELATIONSHIPS = {
    'APPROVED_BY', 'AUTHORED_BY', 'CAUSED_BY', 'DEPENDS_ON',
    'RESOLVED_BY', 'REFERENCES', 'MENTIONS', 'RENAMED_TO',
    'AFFECTS', 'RELATED_TO'
}

def validate_relationship_filter(relationships: list[str]) -> list[str]:
    """Only allow known relationship types."""
    filtered = [r for r in relationships if r in ALLOWED_RELATIONSHIPS]
    if not filtered:
        return list(ALLOWED_RELATIONSHIPS)  # Default to all
    return filtered
```

---

## Rejection Criteria

The following query patterns are **rejected** at runtime:

| Pattern | Reason |
|---------|--------|
| `MATCH ...*3..` | Exceeds 2-hop limit |
| `CALL apoc.*` | Arbitrary procedure call |
| `LOAD CSV` | File system access |
| `WITH $cypher` | Dynamic query construction |
| `CREATE`, `DELETE`, `SET`, `MERGE` | Write operations not allowed |
| LIMIT > 100 | Exceeds hard ceiling |
| Unparameterized values | Injection risk |

---

## Template Registry

```python
TEMPLATE_REGISTRY = {
    'entity_lookup': Template_1,
    'entity_neighbors_1hop': Template_2,
    'entity_neighbors_2hop': Template_3,
    'name_variant_resolution': Template_4,
    'document_references': Template_5,
    'dependency_chain': Template_6,
    'incident_impact': Template_7,
    'document_resolution_chain': Template_8,
    'change_to_incident': Template_9,
    'adr_approval_chain': Template_10,
}
```

---

## Testing Requirements

Each template must have:

1. **Unit tests** for parameter validation
2. **Integration tests** with mock Neo4j
3. **Golden tests** for expected outputs
4. **Failure tests** for timeout and connection errors

---

## Change Log

| Version | Date | Changes |
|---------|------|--------|
| 1.0 | 2026-02-27 | Initial template set |
