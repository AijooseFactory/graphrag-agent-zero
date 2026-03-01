"""
GraphRAG for Agent Zero - Extension Hook Integration

This module provides the integration point with Agent Zero.
NO core patches required - uses extension hook pattern.
"""

import os
import logging
from typing import List, Dict, Any, Optional

# Handle both package and direct imports
try:
    from .hybrid_retrieve import HybridRetriever
    from .neo4j_connector import is_neo4j_available
    from .graph_builder import GraphBuilder
except ImportError:
    from hybrid_retrieve import HybridRetriever
    from neo4j_connector import is_neo4j_available
    from graph_builder import GraphBuilder


# Load project .env and FORCE override parent environment
def _load_project_env():
    """Load project .env and override parent environment variables"""
    from pathlib import Path
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    os.environ[key] = val  # FORCE override

_load_project_env()

logger = logging.getLogger(__name__)

# Global retriever instance (lazy initialization)
_retriever: Optional[HybridRetriever] = None
_builder: Optional[GraphBuilder] = None


def is_enabled() -> bool:
    """Check if GraphRAG is enabled via feature flag"""
    return os.getenv("GRAPH_RAG_ENABLED", "false").lower() == "true"


def get_retriever() -> HybridRetriever:
    """Get or create the hybrid retriever instance"""
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever(
            max_hops=int(os.getenv("GRAPH_EXPAND_MAX_HOPS", "2")),
            max_entities=int(os.getenv("GRAPH_EXPAND_LIMIT", "100")),
            max_results=int(os.getenv("GRAPH_MAX_RESULTS", "50")),
            query_timeout_ms=int(os.getenv("NEO4J_QUERY_TIMEOUT_MS", "10000")),
        )
    return _retriever


def get_builder() -> GraphBuilder:
    """Get or create the graph builder instance"""
    global _builder
    if _builder is None:
        _builder = GraphBuilder()
    return _builder


def enhance_retrieval(
    query: str,
    vector_results: List[Dict[str, Any]],
    top_k: int = 10,
) -> Dict[str, Any]:
    """
    Main extension hook for enhancing retrieval with GraphRAG.
    
    Safety guarantees:
    - If GraphRAG disabled, returns baseline results unchanged
    - If Neo4j unavailable, falls back to baseline
    - All errors are caught and logged, never raises to caller
    """
    # Feature flag check - baseline unchanged when disabled
    if not is_enabled():
        return _baseline_response(vector_results)
    
    # Neo4j availability check
    if not is_neo4j_available():
        logger.debug("GraphRAG enabled but Neo4j unavailable, using baseline")
        return _baseline_response(vector_results)
    
    try:
        retriever = get_retriever()
        result = retriever.retrieve(query, vector_results, top_k)
        
        return {
            "text": result.to_context_pack(),
            "sources": result.source_doc_ids,
            "entities": result.entities,
            "relationships": result.relationships,
            "graph_derived": result.graph_derived,
            "fallback_used": result.fallback_used,
            "latency_ms": result.latency_ms,
            "cache_hit": result.cache_hit,
        }
    except Exception as e:
        logger.warning(f"GraphRAG enhancement failed: {e}")
        return _baseline_response(vector_results)


def _baseline_response(vector_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return baseline response (no graph enhancement)"""
    texts = []
    sources = []
    
    for result in vector_results:
        if "text" in result:
            texts.append(result["text"])
        if "doc_id" in result:
            sources.append(result["doc_id"])
        elif "source" in result:
            sources.append(result["source"])
    
    return {
        "text": "\n\n".join(texts),
        "sources": sources,
        "entities": [],
        "relationships": [],
        "graph_derived": False,
        "fallback_used": True,
        "latency_ms": 0,
        "cache_hit": False,
    }


def build_knowledge_graph(documents: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Build knowledge graph from documents.
    
    Args:
        documents: List of documents with 'id', 'content', 'source' fields
        
    Returns:
        Stats dict with 'documents', 'entities', 'relationships' counts
    """
    if not is_enabled() or not is_neo4j_available():
        return {"documents": 0, "entities": 0, "relationships": 0}
    
    builder = get_builder()
    stats = {"documents": 0, "entities": 0, "relationships": 0}
    
    for doc in documents:
        if builder.build_from_document(doc):
            stats["documents"] += 1
    
    return stats


def health_check() -> Dict[str, Any]:
    """
    Health check for GraphRAG extension.
    
    Returns:
        Dict with status information
    """
    return {
        "enabled": is_enabled(),
        "neo4j_available": is_neo4j_available() if is_enabled() else False,
        "feature_flag": os.getenv("GRAPH_RAG_ENABLED", "false"),
        "neo4j_uri": os.getenv("NEO4J_URI", "not set"),
    }
