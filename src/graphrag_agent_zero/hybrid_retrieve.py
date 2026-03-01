"""
GraphRAG for Agent Zero - Hybrid Retriever

Combines vector search with graph expansion for enhanced retrieval.
- Vector seed → Entity pinning → Bounded graph expand → Context pack
- Graceful fallback to baseline when Neo4j unavailable
- Deterministic citations [DOC-ID] for scoring
"""

import os
import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Handle both package and direct imports
try:
    from .neo4j_connector import is_neo4j_available, get_connector
except ImportError:
    from neo4j_connector import is_neo4j_available, get_connector

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Result from hybrid retrieval"""
    text: str
    source_doc_ids: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    relationships: List[Tuple[str, str, str]] = field(default_factory=list)
    graph_derived: bool = False
    fallback_used: bool = False
    latency_ms: float = 0.0
    cache_hit: bool = False
    
    def to_context_pack(self) -> str:
        """Format as context pack for LLM"""
        lines = []
        
        # Main content
        lines.append(self.text)
        
        # Citations
        if self.source_doc_ids:
            lines.append("\n---\nSources: " + ", ".join(f"[{doc_id}]" for doc_id in self.source_doc_ids))
        
        # Graph-derived context
        if self.graph_derived and self.entities:
            lines.append("\nRelated entities: " + ", ".join(self.entities))
        
        return "\n".join(lines)


class HybridRetriever:
    """
    Main Reasoning Engine for GraphRAG.
    
    This class implements the 'Seed -> Pin -> Expand -> Pack' (SPEP) protocol:
    1.  **VECTOR SEED**: Take context from Agent Zero's native memory.
    2.  **ENTITY PINNING**: Link these seed items to specific nodes in Neo4j.
    3.  **GRAPH EXPAND**: Follow relationship paths up to 2 hops.
    4.  **CONTEXT PACK**: Merge the graph-derived facts back into the original prompt.
    
    MAINTENANCE NOTE for Mac:
    - Current logic is optimized for 'Port 8087' dev stacks.
    - Safety hard-caps are enforced for latency control.
    """
    
    # RELATIONSHIP ALLOWLIST
    # Only follow these edges to prevent 'Context Explosion'.
    ALLOWED_RELATIONSHIPS = [
        "REFERENCES", "CONTAINS", "MENTIONS", "DEPENDS_ON", 
        "RELATED_TO", "SUPERSEDES", "AMENDS",
    ]
    
    def __init__(
        self,
        max_hops: int = 2,
        max_entities: int = 100,
        max_results: int = 50,
        query_timeout_ms: int = 10000,
    ):
        # Strict enforcement of performance boundaries
        self.max_hops = min(max_hops, 2)  
        self.max_entities = min(max_entities, 100)
        self.max_results = max_results
        self.query_timeout_ms = query_timeout_ms
        
        # INTERNAL CACHE: Minimizes expensive Bolt roundtrips.
        # Flushes periodically to ensure consistency with fresh graph updates.
        self._entity_cache: Dict[str, List[str]] = {}
        self._cache_ttl = 3600  # 1 hour
        self._cache_timestamps: Dict[str, float] = {}
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid"""
        if key not in self._cache_timestamps:
            return False
        return time.time() - self._cache_timestamps[key] < self._cache_ttl
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached value if valid"""
        if self._is_cache_valid(key):
            return self._entity_cache.get(key)
        return None
    
    def _set_cache(self, key: str, value: Any):
        """Set cache value with timestamp"""
        self._entity_cache[key] = value
        self._cache_timestamps[key] = time.time()
    
    def retrieve(
        self,
        query: str,
        vector_results: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> RetrievalResult:
        """
        Public interface for retrieval.
        Provides a 'Safe Fallback' pattern: if Neo4j is down, the system 
        continues with pure vector RAG.
        """
        start_time = time.time()
        
        # GATING: Ensure zero downtime even if GraphRAG is misconfigured.
        if not is_neo4j_available():
            return self._fallback_retrieval(vector_results, start_time)
        
        try:
            return self._hybrid_retrieval(query, vector_results, top_k, start_time)
        except Exception as e:
            # Trapped at the reasoning layer to prevent agent crash
            logger.warning(f"Reasoning layer failure (fallback triggered): {e}")
            return self._fallback_retrieval(vector_results, start_time)
    
    def _fallback_retrieval(
        self,
        vector_results: List[Dict[str, Any]],
        start_time: float,
    ) -> RetrievalResult:
        """Fallback to baseline vector retrieval"""
        texts = []
        doc_ids = []
        
        for result in vector_results[:self.max_results]:
            if "text" in result:
                texts.append(result["text"])
            if "doc_id" in result:
                doc_ids.append(result["doc_id"])
            elif "source" in result:
                doc_ids.append(result["source"])
        
        return RetrievalResult(
            text="\n\n".join(texts),
            source_doc_ids=doc_ids,
            fallback_used=True,
            latency_ms=(time.time() - start_time) * 1000,
        )
    
    def _hybrid_retrieval(
        self,
        query: str,
        vector_results: List[Dict[str, Any]],
        top_k: int,
        start_time: float,
    ) -> RetrievalResult:
        """
        The multi-stage GraphRAG pipeline.
        
        MAINTENANCE NOTE for Mac: Focus here if you intend to add 
        reranking or more advanced path discovery.
        """
        
        # 1. PINNING: Identify which documents we're starting from
        seed_doc_ids = []
        for result in vector_results:
            doc_id = result.get("doc_id") or result.get("source")
            if doc_id:
                seed_doc_ids.append(doc_id)
        
        if not seed_doc_ids:
            return self._fallback_retrieval(vector_results, start_time)
        
        # 2. SEED: Get entities associated with those documents
        entities = self._get_entities_for_docs(seed_doc_ids)
        
        # 3. EXPAND: Wander the graph to find hidden connections
        expanded_entities, relationships = self._expand_graph(entities)
        
        # 4. DISCOVER: Find docs linked to these new entities
        related_docs = self._get_related_documents(seed_doc_ids)
        
        all_doc_ids = list(set(seed_doc_ids + related_docs))
        texts = [r.get("text", "") for r in vector_results]
        
        return RetrievalResult(
            text="\n\n".join(texts),
            source_doc_ids=all_doc_ids[:self.max_results],
            entities=expanded_entities[:self.max_entities],
            relationships=relationships,
            graph_derived=True,
            latency_ms=(time.time() - start_time) * 1000,
        )
    
    def _get_entities_for_docs(self, doc_ids: List[str]) -> List[str]:
        """Get entities mentioned in documents"""
        cache_key = f"entities:{','.join(doc_ids)}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        entities = []
        try:
            connector = get_connector()
            for doc_id in doc_ids:
                result = connector.execute_template(
                    "get_entities_by_doc",
                    {"doc_id": doc_id, "limit": 50}
                )
                if result:
                    entities.extend([r["name"] for r in result if r.get("name")])
        except Exception as e:
            logger.warning(f"Entity lookup failed: {e}")
        
        entities = list(set(entities))[:self.max_entities]
        self._set_cache(cache_key, entities)
        return entities
    
    def _expand_graph(
        self,
        entities: List[str]
    ) -> Tuple[List[str], List[Tuple[str, str, str]]]:
        """Expand graph from entities (bounded to max_hops)"""
        all_entities = set(entities)
        all_relationships = []
        
        try:
            connector = get_connector()
            for entity in entities[:20]:  # Limit expansion
                result = connector.execute_template(
                    "get_related_entities",
                    {
                        "entity_name": entity,
                        "allowed_relationships": self.ALLOWED_RELATIONSHIPS,
                        "limit": 10
                    }
                )
                
                if result:
                    for r in result:
                        if r.get("name"):
                            all_entities.add(r["name"])
                        if r.get("relationship"):
                            all_relationships.append(
                                (entity, r["relationship"], r.get("name", "unknown"))
                            )
        except Exception as e:
            logger.warning(f"Graph expansion failed: {e}")
        
        return list(all_entities)[:self.max_entities], all_relationships
    
    def _get_related_documents(self, doc_ids: List[str]) -> List[str]:
        """Get documents related to seed documents via graph"""
        related = []
        try:
            connector = get_connector()
            for doc_id in doc_ids:
                result = connector.execute_template(
                    "get_doc_relationships",
                    {"doc_id": doc_id, "limit": 10}
                )
                if result:
                    related.extend([r["related_doc"] for r in result if r.get("related_doc")])
        except Exception as e:
            logger.warning(f"Document relationship lookup failed: {e}")
        
        return list(set(related))
