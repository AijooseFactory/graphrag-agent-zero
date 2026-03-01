"""
Neo4j-Down Fallback Test
PR #1 MVP - Critical test for graceful degradation

This test verifies the system works when Neo4j is unavailable.
"""

import os
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from graphrag_agent_zero.neo4j_connector import is_neo4j_available, Neo4jConnector
from graphrag_agent_zero.hybrid_retrieve import HybridRetriever


class TestNeo4jDownFallback:
    """Test graceful fallback when Neo4j is unavailable"""
    
    @patch.dict(os.environ, {"GRAPH_RAG_ENABLED": "true"})
    @patch('graphrag_agent_zero.neo4j_connector.get_connector')
    def test_is_neo4j_available_returns_false_on_connection_failure(self, mock_get):
        """is_neo4j_available returns False when connection fails"""
        mock_connector = Mock()
        mock_connector.is_healthy.return_value = False
        mock_get.return_value = mock_connector
        
        result = is_neo4j_available()
        assert not result
    
    @patch.dict(os.environ, {"GRAPH_RAG_ENABLED": "true"})
    @patch('graphrag_agent_zero.neo4j_connector.get_connector')
    def test_retriever_falls_back_when_neo4j_unavailable(self, mock_get):
        """HybridRetriever uses fallback when Neo4j unavailable"""
        mock_connector = Mock()
        mock_connector.is_healthy.return_value = False
        mock_get.return_value = mock_connector
        
        retriever = HybridRetriever()
        result = retriever.retrieve("test query about agent memory", [])
        
        # Should use fallback - no crash
        assert result is not None
        assert result.fallback_used
        assert not result.graph_derived
    
    @patch.dict(os.environ, {"GRAPH_RAG_ENABLED": "false"})
    def test_disabled_flag_always_returns_unavailable(self):
        """When disabled, always returns unavailable (no Neo4j check)"""
        result = is_neo4j_available()
        assert not result
    
    def test_connector_query_timeout_returns_empty(self):
        """Query timeout returns empty result, not crash"""
        connector = Neo4jConnector()
        connector._driver = None  # Simulate disconnected
        
        # Should not raise
        result = connector.execute_template("check_health")
        assert result is None or result == [], "Should return empty on failure"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
