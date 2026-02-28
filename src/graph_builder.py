"""
GraphRAG for Agent Zero - Graph Builder

Builds knowledge graph from documents with:
- Entity extraction
- Relationship detection
- Idempotent upserts
- Safe Cypher templates
"""

import os
import re
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import hashlib

from .neo4j_connector import is_neo4j_available, get_connector

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """Graph entity"""
    name: str
    type: str
    properties: Optional[Dict[str, Any]] = None


@dataclass
class Relationship:
    """Graph relationship"""
    source: str
    target: str
    type: str = "RELATED_TO"
    properties: Optional[Dict[str, Any]] = None


class GraphBuilder:
    """
    Builds knowledge graph from documents.
    
    Safety constraints:
    - Only allowlisted entity types
    - Only allowlisted relationship types
    - Idempotent MERGE operations
    - No arbitrary Cypher from LLM
    """
    
    ALLOWED_ENTITY_TYPES = [
        "Document",
        "Component", 
        "Person",
        "Team",
        "System",
        "Concept",
        "Event",
        "Decision",
        "Incident",
        "Change",
    ]
    
    ALLOWED_RELATIONSHIPS = [
        "REFERENCES",
        "CONTAINS",
        "MENTIONS",
        "DEPENDS_ON",
        "RELATED_TO",
        "SUPERSEDES",
        "AMENDS",
        "AUTHORED_BY",
        "ASSIGNED_TO",
        "AFFECTS",
    ]
    
    # SAFE_CYPHER_TEMPLATES
    MERGE_ENTITY = """
    MERGE (e:Entity {name: $name, type: $type})
    SET e += $properties, e.updated_at = datetime()
    RETURN e
    """
    
    MERGE_RELATIONSHIP = """
    MATCH (a:Entity {name: $source})
    MATCH (b:Entity {name: $target})
    MERGE (a)-[r:%s]->(b)
    SET r += $properties, r.updated_at = datetime()
    RETURN r
    """
    
    def __init__(self):
        self.connector = get_connector()
    
    def _generate_entity_id(self, name: str, entity_type: str) -> str:
        """Generate deterministic entity ID"""
        key = f"{entity_type}:{name}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]
    
    def upsert_entity(self, entity: Entity) -> bool:
        """Idempotent entity upsert using MERGE"""
        if not is_neo4j_available():
            logger.debug("Neo4j not available, skipping entity upsert")
            return False
        
        # Validate entity type
        if entity.type not in self.ALLOWED_ENTITY_TYPES:
            logger.warning(f"Entity type '{entity.type}' not in allowlist, using 'Concept'")
            entity.type = "Concept"
        
        query = self.MERGE_ENTITY
        params = {
            "name": entity.name,
            "type": entity.type,
            "properties": entity.properties or {},
        }
        
        result = self.connector.execute_with_retry(query, params)
        return result is not None
    
    def upsert_relationship(self, relationship: Relationship) -> bool:
        """Idempotent relationship upsert using MERGE"""
        if not is_neo4j_available():
            return False
        
        # Normalize and validate relationship type
        rel_type = relationship.type.upper()
        if rel_type not in self.ALLOWED_RELATIONSHIPS:
            rel_type = "RELATED_TO"
        
        # Safe Cypher with parameterized relationship type
        query = f"""
        MATCH (a:Entity {{name: $source}})
        MATCH (b:Entity {{name: $target}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $properties, r.updated_at = datetime()
        RETURN r
        """
        
        params = {
            "source": relationship.source,
            "target": relationship.target,
            "properties": relationship.properties or {},
        }
        
        result = self.connector.execute_with_retry(query, params)
        return result is not None
    
    def build_from_document(self, doc: Dict[str, Any]) -> bool:
        """Build graph nodes and edges from a document"""
        if not is_neo4j_available():
            return False
        
        doc_id = doc.get("id") or doc.get("doc_id")
        if not doc_id:
            return False
        
        # Create document entity
        content = doc.get("content", "")
        doc_entity = Entity(
            name=doc_id,
            type="Document",
            properties={
                "title": doc.get("title", ""),
                "source": doc.get("source", ""),
                "content_hash": hashlib.sha256(content.encode()).hexdigest()[:16],
            }
        )
        self.upsert_entity(doc_entity)
        
        # Extract references from content
        references = self._extract_references(content)
        
        for ref in references:
            # Create reference entity
            ref_entity = Entity(name=ref, type="Document")
            self.upsert_entity(ref_entity)
            
            # Create relationship
            rel = Relationship(
                source=doc_id,
                target=ref,
                type="REFERENCES"
            )
            self.upsert_relationship(rel)
        
        return True
    
    def _extract_references(self, content: str) -> List[str]:
        """Extract document references from content"""
        patterns = [
            r'\b(ADR-\d+)\b',
            r'\b(INC-\d+)\b', 
            r'\b(CHG-\d+)\b',
            r'\b(MEETING-\d{4}-\d{2}-\d{2})\b',
        ]
        
        references = set()
        for pattern in patterns:
            matches = re.findall(pattern, content)
            references.update(matches)
        
        return list(references)


def build_graph_from_corpus(corpus_dir: str) -> Dict[str, int]:
    """Build graph from a corpus directory"""
    builder = GraphBuilder()
    stats = {"documents": 0, "entities": 0, "relationships": 0}
    
    if not os.path.isdir(corpus_dir):
        logger.error(f"Corpus directory not found: {corpus_dir}")
        return stats
    
    for filename in os.listdir(corpus_dir):
        if filename.endswith(".md"):
            filepath = os.path.join(corpus_dir, filename)
            with open(filepath, "r") as f:
                content = f.read()
            
            doc = {
                "id": filename.replace(".md", ""),
                "content": content,
                "source": filepath,
            }
            
            if builder.build_from_document(doc):
                stats["documents"] += 1
    
    return stats
