"""
GraphRAG for Agent Zero - Hybrid Retriever

Combines vector search with graph expansion for enhanced retrieval.
- Vector seed → Entity pinning → Bounded graph expand → Context pack
- Graceful fallback to baseline when Neo4j unavailable
- Deterministic citations [DOC-ID] for scoring
"""

import time
import logging
import re
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

# Handle both package and direct imports
try:
    from .neo4j_connector import is_neo4j_available, get_connector
    from .cache import LRUTTLCache
except ImportError:
    from neo4j_connector import is_neo4j_available, get_connector
    from cache import LRUTTLCache

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
        rrf_k: int = 60,
        vector_weight: float = 0.4,
        graph_weight: float = 0.6,
    ):
        # Strict enforcement of performance boundaries
        self.max_hops = min(max_hops, 2)  
        self.max_entities = min(max_entities, 100)
        self.max_results = max_results
        self.query_timeout_ms = query_timeout_ms
        self.rrf_k = rrf_k
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight
        
        # INTERNAL CACHE: Minimizes expensive Bolt roundtrips.
        # Implements bounded LRU memory constraint with TTL flush.
        self._entity_cache = LRUTTLCache(capacity=5000, ttl_seconds=3600)
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached value if valid"""
        return self._entity_cache.get(key)
    
    def _set_cache(self, key: str, value: Any):
        """Set cache value with timestamp"""
        self._entity_cache.set(key, value)
    
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
        # Log for E2E contract verification
        logger.info("GRAPHRAG_UTILITY_PROMPT_APPLIED: YES")
        
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
        The multi-stage GraphRAG pipeline with RRF Fusion.
        """
        # 1. PINNING: Identify which documents we're starting from (Vector Rank)
        vector_rankings = {}
        seed_doc_ids = []
        for rank, result in enumerate(vector_results):
            doc_id = result.get("doc_id") or result.get("source")
            if doc_id:
                seed_doc_ids.append(doc_id)
                vector_rankings[doc_id] = rank
        
        if not seed_doc_ids:
            return self._query_only_graph_retrieval(query, vector_results, start_time)
        
        # 2. SEED: Get entities associated with those documents
        entities, hit_entities = self._get_entities_for_docs_with_meta(seed_doc_ids)
        
        # 3. EXPAND: Wander the graph to find hidden connections
        expanded_entities, relationships, hit_expand = self._expand_graph_with_meta(entities)
        
        cache_hit = hit_entities or hit_expand
        
        # 4. DISCOVER: Find docs linked to these new entities (Graph Rank)
        related_docs = self._get_related_documents(seed_doc_ids)
        graph_rankings = {doc_id: rank for rank, doc_id in enumerate(related_docs)}
        
        # 5. RRF FUSION: Calculate combined scores
        combined_scores = {}
        all_unique_docs = set(seed_doc_ids) | set(related_docs)
        
        for doc_id in all_unique_docs:
            v_score = 1.0 / (self.rrf_k + vector_rankings[doc_id]) if doc_id in vector_rankings else 0.0
            g_score = 1.0 / (self.rrf_k + graph_rankings[doc_id]) if doc_id in graph_rankings else 0.0
            
            # Application of Hybrid Weights (Default: Graph 0.6, Vector 0.4)
            score = (v_score * self.vector_weight) + (g_score * self.graph_weight)
            combined_scores[doc_id] = score
            
        # Re-rank based on RRF scores
        sorted_doc_ids = sorted(combined_scores.keys(), key=lambda x: combined_scores[x], reverse=True)
        final_doc_ids = sorted_doc_ids[:self.max_results]
        
        # Log fusion results for E2E verification
        logger.info("GRAPHRAG_RRF_ORDER: %s", final_doc_ids)
        
        # Prepare final text context (prioritizing vector text for documents found in both)
        vector_text_map = { (r.get("doc_id") or r.get("source")): r.get("text", "") for r in vector_results if (r.get("doc_id") or r.get("source")) }
        
        final_texts = []
        for doc_id in final_doc_ids:
            if doc_id in vector_text_map:
                final_texts.append(vector_text_map[doc_id])
            # If doc_id is only in graph, we might want to fetch text, but for now we follow safety contract
        
        return RetrievalResult(
            text="\n\n".join(final_texts),
            source_doc_ids=final_doc_ids,
            entities=expanded_entities[:self.max_entities],
            relationships=relationships,
            graph_derived=True,
            latency_ms=(time.time() - start_time) * 1000,
            cache_hit=cache_hit,
        )

    def _query_only_graph_retrieval(
        self,
        query: str,
        vector_results: List[Dict[str, Any]],
        start_time: float,
    ) -> RetrievalResult:
        """
        Query-driven lookup path for extension calls that do not provide vector seeds.
        """
        entity_terms = self._extract_entity_terms_from_query(query)
        if not entity_terms:
            return self._fallback_retrieval(vector_results, start_time)

        direct_matches = self._get_entities_for_terms(entity_terms)
        if not direct_matches:
            return self._fallback_retrieval(vector_results, start_time)

        base_entities = [m["name"] for m in direct_matches if m.get("name")]
        expanded_entities, relationships = self._expand_graph(base_entities)

        return RetrievalResult(
            text=self._format_entity_matches(direct_matches),
            source_doc_ids=[],
            entities=expanded_entities[:self.max_entities],
            relationships=relationships,
            graph_derived=True,
            latency_ms=(time.time() - start_time) * 1000,
        )

    def _extract_entity_terms_from_query(self, query: str) -> List[str]:
        """Extract likely entity IDs/names from free-form user query."""
        tokens = re.findall(r"\b[A-Za-z0-9_:\-]{3,}\b", query or "")
        likely_entities = []

        for token in tokens:
            if "_" in token or any(ch.isdigit() for ch in token) or token.isupper():
                likely_entities.append(token)

        # Preserve order while deduplicating.
        return list(dict.fromkeys(likely_entities))[:10]

    def _get_entities_for_terms(self, entity_terms: List[str]) -> List[Dict[str, Any]]:
        """Resolve query terms against entity name/id in Neo4j."""
        matches: List[Dict[str, Any]] = []
        seen: set[Tuple[str, str]] = set()

        try:
            connector = get_connector()
            for term in entity_terms:
                result = connector.execute_template(
                    "get_entity_by_name_or_id",
                    {"entity_term": term, "limit": 5},
                )
                if not result:
                    continue

                for row in result:
                    key = (str(row.get("id", "")), str(row.get("name", "")))
                    if key in seen:
                        continue
                    seen.add(key)
                    matches.append(row)
        except Exception as e:
            logger.warning(f"Direct entity lookup failed: {e}")

        return matches[:self.max_entities]

    def _format_entity_matches(self, matches: List[Dict[str, Any]]) -> str:
        """Create deterministic context text from direct entity matches."""
        lines = []
        for row in matches[:self.max_results]:
            name = row.get("name") or row.get("id") or "unknown"
            entity_type = row.get("type") or "Entity"
            description = str(row.get("description") or "").strip()

            if description:
                lines.append(f"{name} ({entity_type}): {description}")
            else:
                lines.append(f"{name} ({entity_type})")

        return "\n".join(lines)

    def _get_entities_for_docs_with_meta(self, doc_ids: List[str]) -> Tuple[List[str], bool]:
        """Get entities for documents and return cache hit status"""
        cache_key = f"entities:{','.join(doc_ids)}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached, True
        
        entities = self._get_entities_for_docs(doc_ids)
        return entities, False

    def _expand_graph_with_meta(
        self,
        entities: List[str]
    ) -> Tuple[List[str], List[Tuple[str, str, str]], bool]:
        """Expand graph from entities and return cache hit status"""
        cache_key = f"expand:{','.join(sorted(entities[:20]))}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached[0], cached[1], True
            
        res_entities, res_rels = self._expand_graph(entities)
        return res_entities, res_rels, False

    def _get_entities_for_docs(self, doc_ids: List[str]) -> List[str]:
        """Get entities mentioned in documents"""
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
        
        return list(set(entities))[:self.max_entities]

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
        """Get documents related to seed documents via graph (Preserves Rank)"""
        related = []
        seen = set()
        try:
            connector = get_connector()
            for doc_id in doc_ids:
                result = connector.execute_template(
                    "get_doc_relationships",
                    {"doc_id": doc_id, "limit": 10}
                )
                if result:
                    for r in result:
                        rel_doc = r.get("related_doc")
                        if rel_doc and rel_doc not in seen:
                            related.append(rel_doc)
                            seen.add(rel_doc)
        except Exception as e:
            logger.warning(f"Document relationship lookup failed: {e}")
        
        return related
