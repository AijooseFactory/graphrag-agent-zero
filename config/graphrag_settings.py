"""
GraphRAG for Agent Zero - Settings

Configuration and feature flags for GraphRAG extension.
OFF by default - no baseline changes when disabled.
"""

import os
from dataclasses import dataclass


@dataclass
class GraphRAGSettings:
    """Settings for GraphRAG extension"""
    
    # Feature flag (OFF by default - no baseline changes)
    enabled: bool = False
    
    # Graph expansion limits
    max_hops: int = 2
    max_entities: int = 100
    max_results: int = 50
    
    # Timeouts
    query_timeout_ms: int = 10000
    connection_timeout_ms: int = 5000
    
    # Retry configuration
    max_retries: int = 3
    retry_delay_ms: int = 100
    
    # Cache settings
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    
    @classmethod
    def from_env(cls) -> 'GraphRAGSettings':
        """Load settings from environment variables"""
        return cls(
            enabled=os.getenv("GRAPH_RAG_ENABLED", "false").lower() == "true",
            max_hops=int(os.getenv("GRAPH_EXPAND_MAX_HOPS", "2")),
            max_entities=int(os.getenv("GRAPH_EXPAND_LIMIT", "100")),
            max_results=int(os.getenv("GRAPH_MAX_RESULTS", "50")),
            query_timeout_ms=int(os.getenv("NEO4J_QUERY_TIMEOUT_MS", "10000")),
            connection_timeout_ms=int(os.getenv("NEO4J_CONNECTION_TIMEOUT_MS", "5000")),
            max_retries=int(os.getenv("NEO4J_MAX_RETRIES", "3")),
            retry_delay_ms=int(os.getenv("NEO4J_RETRY_DELAY_MS", "100")),
            cache_enabled=os.getenv("GRAPH_RAG_CACHE_ENABLED", "true").lower() == "true",
            cache_ttl_seconds=int(os.getenv("GRAPH_RAG_CACHE_TTL", "3600")),
        )


# Global settings instance
_settings: GraphRAGSettings = None


def get_settings() -> GraphRAGSettings:
    """Get or create settings instance"""
    global _settings
    if _settings is None:
        _settings = GraphRAGSettings.from_env()
    return _settings


def is_enabled() -> bool:
    """Check if GraphRAG is enabled"""
    return get_settings().enabled
