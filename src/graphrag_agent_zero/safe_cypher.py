"""
GraphRAG for Agent Zero - Safe Cypher Enforcement

This module defines allowlisted Cypher templates and enforces safe execution.
NO arbitrary Cypher allowed. All queries must be parameterized and bounded.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Allowlisted Cypher Templates
SAFE_CYPHER_TEMPLATES = {
    "get_neighbors": """
        MATCH (e:Entity)
        WHERE e.id IN $entity_ids
        MATCH (e)-[r]-(neighbor:Entity)
        RETURN e.id as source, type(r) as relationship, neighbor.id as target, neighbor.name as name
        LIMIT $limit
    """,
    "get_entity_details": """
        MATCH (e:Entity)
        WHERE e.id IN $entity_ids
        RETURN e.id as id, e.name as name, e.description as description, labels(e) as types
        LIMIT $limit
    """,
    "check_health": "RETURN 1 as health",
    
    # Retrieval templates
    "get_entities_by_doc": """
        MATCH (d:Entity {name: $doc_id, type: 'Document'})-[:REFERENCES|CONTAINS|MENTIONS]->(e:Entity)
        RETURN e.name as name, e.type as type, e.entity_id as id
        LIMIT $limit
    """,
    "get_related_entities": """
        MATCH (e:Entity {name: $entity_name})-[r]-(related:Entity)
        WHERE type(r) IN $allowed_relationships
        RETURN related.name as name, related.type as type, 
               type(r) as relationship, labels(related) as labels
        LIMIT $limit
    """,
    "get_doc_relationships": """
        MATCH (d1:Entity {name: $doc_id, type: 'Document'})-[:REFERENCES]->(d2:Entity)
        WHERE d2.type = 'Document'
        RETURN d2.name as related_doc, d2.title as title
        LIMIT $limit
    """,
    "get_entity_paths": """
        MATCH path = (start:Entity {name: $start_entity})-[*1..2]-(end:Entity)
        WHERE ALL(r IN relationships(path) WHERE type(r) IN $allowed_relationships)
        RETURN [n in nodes(path) | n.name] as entity_path,
               [r in relationships(path) | type(r)] as rel_path,
               length(path) as hops
        ORDER BY hops
        LIMIT $limit
    """,
    
    # Indexing templates
    "merge_entity": """
        MERGE (e:Entity {name: $name, type: $type})
        SET e += $properties, e.updated_at = datetime()
        RETURN e
    """,
}

# Dynamically add relationship templates for each allowed type
ALLOWED_RELATIONSHIPS = [
    "REFERENCES", "CONTAINS", "MENTIONS", "DEPENDS_ON", 
    "RELATED_TO", "SUPERSEDES", "AMENDS", "AUTHORED_BY", 
    "ASSIGNED_TO", "AFFECTS"
]

for rel in ALLOWED_RELATIONSHIPS:
    SAFE_CYPHER_TEMPLATES[f"merge_rel_{rel.lower()}"] = f"""
        MATCH (a:Entity {{name: $source}})
        MATCH (b:Entity {{name: $target}})
        MERGE (a)-[r:{rel}]->(b)
        SET r += $properties, r.updated_at = datetime()
        RETURN r
    """

def get_safe_query(template_name: str) -> Optional[str]:
    """Get an allowlisted Cypher query template."""
    return SAFE_CYPHER_TEMPLATES.get(template_name)

def validate_parameters(parameters: Dict[str, Any]) -> bool:
    """
    Validate query parameters for safety.
    - entity_ids must be a list of strings
    - limit must be an integer <= 1000
    """
    if "entity_ids" in parameters:
        if not isinstance(parameters["entity_ids"], list):
            return False
        if not all(isinstance(eid, str) for eid in parameters["entity_ids"]):
            return False
            
    if "limit" in parameters:
        if not isinstance(parameters["limit"], int) or parameters["limit"] > 1000:
            logger.warning(f"Unsafe limit requested: {parameters['limit']}")
            parameters["limit"] = 100  # Enforce safe default
            
    return True
