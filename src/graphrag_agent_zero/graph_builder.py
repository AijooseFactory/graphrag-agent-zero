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
    
    def normalize_entity_name(self, name: str) -> str:
        """Standardize entity names for improved resolution."""
        if not name:
            return ""
        # 1. Lowercase and strip whitespace
        name = name.lower().strip()
        # 2. Remove punctuation except internal underscores/hyphens
        name = re.sub(r'(?<!\w)[^\w\s]|[^\w\s](?!\w)', '', name)
        # 3. Collapse multiple spaces
        name = re.sub(r'\s+', ' ', name)
        return name

    def _generate_entity_id(self, name: str, entity_type: str) -> str:
        """Generate deterministic entity ID"""
        # Resolution first
        name = self.normalize_entity_name(name)
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
            logger.error("GraphRAG: Failed payload secured in Dead Letter Queue")
        except Exception as e:
            logger.critical(f"GraphRAG DLQ FAILURE: {e}")

    def _sanitize_properties(self, props: Any) -> Dict[str, Any]:
        """
        Hardened Neo4j Sanitation (Top 1% Engineering):
        - Enforce scalar types (String, Number, Bool, List[Scalar])
        - JSON-stringify or drop nested dicts
        - Remove null bytes and control chars
        - Limit property count
        """
        if not isinstance(props, dict):
            return {}
            
        import json
        clean = {}
        MAX_PROPS = 15
        MAX_VAL_LEN = 1000
        
        # Priority properties to keep if we hit MAX_PROPS
        priority_keys = ["description", "evidence", "aliases", "title", "source"]
        
        # Sort keys to ensure priority keys are processed first
        sorted_keys = sorted(props.keys(), key=lambda k: (0 if k in priority_keys else 1, k))

        for k in sorted_keys:
            if len(clean) >= MAX_PROPS:
                break
                
            v = props[k]
            if v is None:
                continue
                
            # Sanitize key (remove control chars, strip)
            clean_k = "".join(ch for ch in str(k) if ord(ch) >= 32).strip()[:100]
            if not clean_k:
                continue

            # Sanitize value
            if isinstance(v, (dict, list)):
                # Strictly for lists, check if elements are scalars
                if isinstance(v, list):
                    clean_v = []
                    for item in v:
                        if isinstance(item, (str, int, float, bool)):
                            # Sanitize string items
                            if isinstance(item, str):
                                item = "".join(ch for ch in item if ord(ch) >= 32).strip()[:MAX_VAL_LEN]
                            clean_v.append(item)
                    clean[clean_k] = clean_v
                else:
                    # Dicts get stringified
                    clean[clean_k] = json.dumps(v)[:MAX_VAL_LEN]
            elif isinstance(v, (str, int, float, bool)):
                if isinstance(v, str):
                    v = "".join(ch for ch in v if ord(ch) >= 32).strip()[:MAX_VAL_LEN]
                clean[clean_k] = v
            else:
                # Fallback for unknown types
                clean[clean_k] = str(v)[:MAX_VAL_LEN]
                
        return clean

    def deduplicate_entities(self, entities_data: List[Dict]) -> List[Dict]:
        """
        Advanced Entity Resolution (v0.2.0):
        - Uses aliases/synonyms for cross-linking
        - Canonicalizes names for matching
        - Merges properties from duplicates
        """
        seen_by_name = {} # norm_name -> entity
        alias_map = {}    # norm_alias -> norm_canonical_name
        
        # Pass 1: Build alias map and identify unique entities
        for ent in entities_data:
            name = ent.get("name")
            if not name:
                continue
            
            norm_name = self.normalize_entity_name(name)
            aliases = ent.get("aliases", [])
            
            # If this is a new entity, or an alias of an existing one
            target_norm = alias_map.get(norm_name, norm_name)
            
            if target_norm not in seen_by_name:
                # Register new canonical entity
                ent["name"] = name.strip() # Keep original display name
                ent["type"] = ent.get("type", "Concept")
                if ent["type"] not in self.ALLOWED_ENTITY_TYPES:
                    ent["type"] = "Concept"
                ent["properties"] = self._sanitize_properties(ent.get("properties", {}))
                seen_by_name[target_norm] = ent
            else:
                # Merge into existing entity
                existing = seen_by_name[target_norm]
                new_props = self._sanitize_properties(ent.get("properties", {}))
                existing["properties"].update(new_props)
                
            # Register aliases for this entity
            for alias in aliases:
                norm_alias = self.normalize_entity_name(alias)
                if norm_alias and norm_alias not in alias_map:
                    alias_map[norm_alias] = target_norm
                    # Add to property aliases if missing
                    current_aliases = seen_by_name[target_norm]["properties"].get("aliases", [])
                    if isinstance(current_aliases, list) and alias not in current_aliases:
                        current_aliases.append(alias)
                        seen_by_name[target_norm]["properties"]["aliases"] = current_aliases

        return list(seen_by_name.values())

    def build_from_document(self, doc: Dict[str, Any]) -> Dict[str, int]:
        """Build graph nodes and edges from a document via Batch Processing"""
        stats = {"entities": 0, "relationships": 0}
        if not is_neo4j_available():
            return stats

        
        doc_id = doc.get("id") or doc.get("doc_id")
        if not doc_id:
            return stats

        
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
        stats["entities"] += 1

        
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
                    if not src or not tgt:
                        continue
                    
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
                    if rel_res is not None:
                        # count based on merged_count result if available, or list length
                        count = rel_res[0].get("merged_count", len(rel_list)) if rel_res else len(rel_list)
                        stats["relationships"] += count
                    else:
                        raise Exception(f"Batch Relationship merge failed for type {rel_type}")

                stats["entities"] += len(deduped_entities)
                # Linkage to doc adds relationships
                stats["relationships"] += len(doc_mentions)


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
            stats["relationships"] += len(ref_rels)
            stats["entities"] += len(ref_entities)
        
        return stats

    
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
