"""
GraphRAG for Agent Zero - Extension Hook Integration

This module provides the integration point with Agent Zero.
NO core patches required - uses extension hook pattern.
"""

import os
import logging
from typing import List, Dict, Any, Optional

# Package-ready imports
from .hybrid_retrieve import HybridRetriever
from .neo4j_connector import is_neo4j_available
from .graph_builder import GraphBuilder

logger = logging.getLogger(__name__)

# Global singleton instances for retriever and builder (lazy initialization)
_retriever: Optional[HybridRetriever] = None
_builder: Optional[GraphBuilder] = None


def is_enabled() -> bool:
    """
    Check if the GraphRAG feature is active.
    
    Triggered by the environment variable GRAPH_RAG_ENABLED.
    Defaults to 'false' to ensure non-invasive behavior if not explicitly requested.
    """
    return os.getenv("GRAPH_RAG_ENABLED", "false").lower() == "true"


def get_retriever() -> HybridRetriever:
    """
    Singleton getter for the HybridRetriever.
    
    MAINTENANCE NOTE for Mac:
    - This is where you adjust default hop counts and response limits.
    - Uses environment variables for configuration to avoid hardcoding.
    """
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
    """
    Singleton getter for the GraphBuilder (responsible for data ingestion).
    """
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
    The primary integration point for the Agent Zero 'Extensions' framework.
    
    This function acts as the 'Control Plane' for a retrieval request:
    1. It validates the state (enabled/available).
    2. It executes the hybrid retrieval pipeline (vector + graph).
    3. It packages the results into a dict format expected by the Extension subclass.
    
    Safety Design:
    - Failing Open: If GraphRAG is off or broken, it returns a standard baseline.
    - Exception Isolation: Any crash inside the graph logic is trapped here.
    """
    # GATING: Standard feature flag check
    if not is_enabled():
        return _baseline_response(vector_results)
    
    # GATING: Database availability check
    if not is_neo4j_available():
        logger.debug("GraphRAG enabled but Neo4j unavailable, falling back to baseline")
        return _baseline_response(vector_results)
    
    try:
        # EXECUTE: Run the multi-stage retrieval
        retriever = get_retriever()
        result = retriever.retrieve(query, vector_results, top_k)
        
        # PACKAGE: Map source-agnostic Result object to the extension contract
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
        # LOG & SCALE: Log the failure for maintenance but don't stop the agent.
        logger.warning(f"GraphRAG enhancement failed (trapped in hook): {e}")
        return _baseline_response(vector_results)


def _baseline_response(vector_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Constructs a valid response dictionary when GraphRAG is skipped.
    Ensures that the Extension subclass receives a consistent structure.
    """
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
    Ingestion hook to populate Neo4j from a list of documents.
    
    Args:
        documents: A list of dicts with 'id' and 'content'.
        
    MAINTENANCE NOTE for Mac: Use this when you want to batch-index 
    the workspace memory into the graph.
    """
    if not is_enabled() or not is_neo4j_available():
        return {"documents": 0, "entities": 0, "relationships": 0}
    
    builder = get_builder()
    stats = {"documents": 0, "entities": 0, "relationships": 0}
    
    for doc in documents:
        if builder.build_from_document(doc):
            stats["documents"] += 1
    
    # Note: Stats for entities/rels can be expanded here if needed.
    return stats


def health_check() -> Dict[str, Any]:
    """
    Diagnostic tool for the Maintenance Mode.
    Provides visibility into the current GraphRAG status.
    """
    return {
        "enabled": is_enabled(),
        "neo4j_available": is_neo4j_available() if is_enabled() else False,
        "feature_flag": os.getenv("GRAPH_RAG_ENABLED", "false"),
        "neo4j_uri": os.getenv("NEO4J_URI", "not set"),
    }
