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
from .llm_extractor import LLMExtractor

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
        "WORKS_ON",
        "PART_OF",
        "MEMBER_OF",
    ]
    
    def __init__(self, extract_llm: bool = True):
        self.connector = get_connector()
        self.extract_llm = extract_llm
        self.llm_extractor = LLMExtractor() if extract_llm else None
    
    def _generate_entity_id(self, name: str, entity_type: str) -> str:
        """Generate deterministic entity ID"""
        key = f"{entity_type}:{name}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]
    
    def upsert_entity(self, entity: Entity) -> bool:
        """Idempotent entity upsert using MERGE template"""
        if not is_neo4j_available():
            logger.debug("Neo4j not available, skipping entity upsert")
            return False
        
        # Validate entity type
        if entity.type not in self.ALLOWED_ENTITY_TYPES:
            logger.warning(f"Entity type '{entity.type}' not in allowlist, using 'Concept'")
            entity.type = "Concept"
        
        params = {
            "name": entity.name,
            "type": entity.type,
            "properties": entity.properties or {},
        }
        
        result = self.connector.execute_template("merge_entity", params)
        return result is not None
    
    def upsert_relationship(self, relationship: Relationship) -> bool:
        """Idempotent relationship upsert using MERGE template"""
        if not is_neo4j_available():
            return False
        
        # Normalize and validate relationship type
        rel_type = relationship.type.upper().replace(" ", "_")
        if rel_type not in self.ALLOWED_RELATIONSHIPS:
            rel_type = "RELATED_TO"
        
        params = {
            "source": relationship.source,
            "target": relationship.target,
            "rel_type": rel_type, # Used in string interpolation in safe_cypher if allowed, or separate templates
            "properties": relationship.properties or {},
        }
        
        # We need a special template or safe interpolation for relationship types since they can't be parameters
        result = self.connector.execute_template(f"merge_rel_{rel_type.lower()}", params)
        return result is not None
    
    def _write_to_dlq(self, payload: Dict[str, Any], error: str):
        """Append failed extractions to Dead Letter Queue to guarantee ZERO data loss."""
        import json
        from datetime import datetime
        dlq_path = "/a0/usr/memory/default/dlq.json"
        
        # Fallback for Mac host diagnostics
        if not os.path.exists("/a0"):
            dlq_path = os.path.join(os.path.dirname(__file__), "../../../agent-zero-fork/usr/memory/default/dlq.json")
            
        os.makedirs(os.path.dirname(dlq_path), exist_ok=True)
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "error": str(error),
            "payload": payload
        }
        try:
            with open(dlq_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
            logger.error(f"GraphRAG: Failed payload secured in Dead Letter Queue")
        except Exception as e:
            logger.critical(f"GraphRAG DLQ FAILURE: {e}")

    def _sanitize_properties(self, props: Any) -> Dict[str, Any]:
        """Neo4j rejects nested dictionaries as properties. This sanitizes LLM output."""
        if not isinstance(props, dict):
            return {}
            
        import json
        clean = {}
        for k, v in props.items():
            if v is None:
                continue
            if isinstance(v, (dict, list)):
                # Stringify complex nested objects recursively
                clean[str(k)] = json.dumps(v)
            else:
                clean[str(k)] = v
        return clean

    def deduplicate_entities(self, entities_data: List[Dict]) -> List[Dict]:
        """2026 Best Practice: In-memory Entity Resolution via name normalization."""
        seen = {}
        for ent in entities_data:
            name = ent.get("name")
            if not name: continue
            
            # Normalize: lowercase, strip whitespace and punctuation
            norm_name = re.sub(r'[^\w\s]', '', name.lower().strip())
            
            if norm_name not in seen:
                # Ensure type is allowlisted
                ent_type = ent.get("type", "Concept")
                if ent_type not in self.ALLOWED_ENTITY_TYPES:
                    ent["type"] = "Concept"
                    
                # Sanitize initial properties
                ent["properties"] = self._sanitize_properties(ent.get("properties", {}))
                seen[norm_name] = ent
            else:
                # Merge properties if duplicate found
                existing_props = seen[norm_name].get("properties", {})
                new_props = self._sanitize_properties(ent.get("properties", {}))
                
                existing_props.update(new_props)
                seen[norm_name]["properties"] = existing_props
        
        return list(seen.values())

    def build_from_document(self, doc: Dict[str, Any]) -> bool:
        """Build graph nodes and edges from a document via Batch Processing"""
        if not is_neo4j_available():
            return False
        
        doc_id = doc.get("id") or doc.get("doc_id")
        if not doc_id:
            return False
        
        # 1. Create document entity
        content = doc.get("content", "")
        doc_entity = Entity(
            name=doc_id,
            type="Document",
            properties={
                "title": doc.get("title", ""),
                "source": doc.get("source", ""),
                "content": content,
                "content_hash": hashlib.sha256(content.encode()).hexdigest()[:16],
            }
        )
        self.upsert_entity(doc_entity)
        
        # 2. LLM Extraction (High-fidelity)
        if self.extract_llm and self.llm_extractor:
            logger.debug(f"GraphRAG: running LLM extraction for {doc_id}")
            result = self.llm_extractor.extract(content)
            
            try:
                # Deduplicate raw entities before database injection
                raw_entities = result.get("entities", [])
                deduped_entities = self.deduplicate_entities(raw_entities)
                
                # Batch 1: Entities
                if deduped_entities:
                    batch_res = self.connector.execute_template("batch_merge_entities", {"entities": deduped_entities})
                    if batch_res is None:
                        raise Exception("Batch Entity merge returned None (Template failure)")
                
                # Automatically link all deduplicated entities to Document
                doc_mentions = []
                for ent in deduped_entities:
                    doc_mentions.append({
                        "source": doc_id,
                        "target": ent["name"],
                        "properties": {}
                    })
                if doc_mentions:
                    self.connector.execute_template("batch_merge_rel_mentions", {"relationships": doc_mentions})
                
                # Batch 2: Relationships (Grouped by Type for safe interpolation)
                rel_batches = {}
                for rel_data in result.get("relationships", []):
                    src = rel_data.get("source")
                    tgt = rel_data.get("target")
                    if not src or not tgt: continue
                    
                    rel_type = rel_data.get("type", "RELATED_TO").upper().replace(" ", "_")
                    if rel_type not in self.ALLOWED_RELATIONSHIPS:
                        rel_type = "RELATED_TO"
                        
                    if rel_type not in rel_batches:
                        rel_batches[rel_type] = []
                        
                    rel_batches[rel_type].append({
                        "source": src,
                        "target": tgt,
                        "properties": self._sanitize_properties(rel_data.get("properties", {}))
                    })
                    
                for rel_type, rel_list in rel_batches.items():
                    rel_res = self.connector.execute_template(f"batch_merge_rel_{rel_type.lower()}", {"relationships": rel_list})
                    if rel_res is None:
                        raise Exception(f"Batch Relationship merge failed for type {rel_type}")

            except Exception as e:
                logger.error(f"GraphRAG: Batch ingestion failed, routing to DLQ. Error: {e}")
                self._write_to_dlq(result, str(e))

        # 3. Regex Extraction (Fast-path / Fallback)
        references = self._extract_references(content)
        
        # We can also batch these references
        ref_entities = [{"name": ref, "type": "Document", "properties": {}} for ref in references]
        if ref_entities:
            self.connector.execute_template("batch_merge_entities", {"entities": ref_entities})
            
        ref_rels = [{"source": doc_id, "target": ref, "properties": {}} for ref in references]
        if ref_rels:
            self.connector.execute_template("batch_merge_rel_references", {"relationships": ref_rels})
        
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
