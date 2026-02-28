"""
Unit Tests for Neo4j Connector
PR #1 MVP - Tests graceful fallback behavior
"""

import os
import sys
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from neo4j_connector import Neo4jConnector, get_connector, is_neo4j_available


class TestNeo4jConnector:
    """Test Neo4jConnector graceful fallback"""
    
    @patch.dict(os.environ, {"GRAPH_RAG_ENABLED": "false"})
    def test_feature_flag_disabled_returns_false(self):
        """When GRAPH_RAG_ENABLED=false, is_neo4j_available returns False"""
        result = is_neo4j_available()
        assert result == False, "Should return False when feature flag is off"
    
    @patch.dict(os.environ, {"GRAPH_RAG_ENABLED": "true"})
    @patch('neo4j_connector.get_connector')
    def test_neo4j_unavailable_returns_false(self, mock_get_connector):
        """When Neo4j is down, is_neo4j_available returns False gracefully"""
        mock_connector = Mock()
        mock_connector.is_healthy.return_value = False
        mock_get_connector.return_value = mock_connector
        
        result = is_neo4j_available()
        assert result == False, "Should return False when Neo4j is unhealthy"
    
    @patch.dict(os.environ, {"GRAPH_RAG_ENABLED": "true"})
    @patch('neo4j_connector.get_connector')
    def test_neo4j_available_returns_true(self, mock_get_connector):
        """When Neo4j is healthy, is_neo4j_available returns True"""
        mock_connector = Mock()
        mock_connector.is_healthy.return_value = True
        mock_get_connector.return_value = mock_connector
        
        result = is_neo4j_available()
        assert result == True, "Should return True when Neo4j is healthy"
    
    @patch('neo4j.GraphDatabase.driver')
    def test_connector_handles_connection_error(self, mock_driver):
        """Connector handles connection errors gracefully"""
        mock_driver.side_effect = Exception("Connection refused")
        
        # Should not raise - graceful degradation
        connector = Neo4jConnector()
        assert connector._driver is None, "Driver should be None on connection failure"
    
    @patch.dict(os.environ, {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "test"
    })
    def test_connector_initialization(self):
        """Connector initializes with env vars"""
        connector = Neo4jConnector()
        assert connector.uri == "bolt://localhost:7687"
        assert connector.user == "neo4j"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
