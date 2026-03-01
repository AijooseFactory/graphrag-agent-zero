"""
GraphRAG for Agent Zero

A top-tier GitHub add-on providing GraphRAG capabilities for Agent Zero.

Features:
- Hybrid retrieval: vector + graph expansion
- Deterministic citations [DOC-ID]
- Graceful fallback when Neo4j unavailable
- Zero baseline changes when disabled
"""

from .extension_hook import (
    enhance_retrieval,
    is_enabled,
    health_check,
    build_knowledge_graph,
)
from .hybrid_retrieve import HybridRetriever, RetrievalResult
from .neo4j_connector import get_connector, is_neo4j_available
from .graph_builder import GraphBuilder

__version__ = "0.1.0"
__all__ = [
    "enhance_retrieval",
    "is_enabled",
    "health_check",
    "build_knowledge_graph",
    "HybridRetriever",
    "RetrievalResult",
    "get_connector",
    "is_neo4j_available",
    "GraphBuilder",
]
