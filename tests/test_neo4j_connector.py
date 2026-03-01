"""
Unit Tests for Neo4j Connector
PR #1 MVP - Tests graceful fallback behavior
"""

import os
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from graphrag_agent_zero.neo4j_connector import Neo4jConnector, is_neo4j_available


class TestNeo4jConnector:
    """Test Neo4jConnector graceful fallback"""
    
    @patch.dict(os.environ, {"GRAPH_RAG_ENABLED": "false"})
    def test_feature_flag_disabled_returns_false(self):
        """When GRAPH_RAG_ENABLED=false, is_neo4j_available returns False"""
        result = is_neo4j_available()
        assert not result, "Should return False when feature flag is off"
    
    @patch.dict(os.environ, {"GRAPH_RAG_ENABLED": "true"})
    @patch('graphrag_agent_zero.neo4j_connector.get_connector')
    def test_neo4j_unavailable_returns_false(self, mock_get_connector):
        """When Neo4j is down, is_neo4j_available returns False gracefully"""
        mock_connector = Mock()
        mock_connector.is_healthy.return_value = False
        mock_get_connector.return_value = mock_connector
        
        result = is_neo4j_available()
        assert not result, "Should return False when Neo4j is unhealthy"
    
    @patch.dict(os.environ, {"GRAPH_RAG_ENABLED": "true"})
    @patch('graphrag_agent_zero.neo4j_connector.get_connector')
    def test_neo4j_available_returns_true(self, mock_get_connector):
        """When Neo4j is healthy, is_neo4j_available returns True"""
        mock_connector = Mock()
        mock_connector.is_healthy.return_value = True
        mock_get_connector.return_value = mock_connector
        
        result = is_neo4j_available()
        assert result, "Should return True when Neo4j is healthy"
    
    @patch('graphrag_agent_zero.neo4j_connector.GraphDatabase', create=True)
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
        assert connector.config.uri == "bolt://localhost:7687"
        assert connector.config.user == "neo4j"

    @patch.dict(os.environ, {"GRAPH_RAG_ENABLED": "true"})
    def test_execute_template_passes_timeout(self):
        """execute_template must pass query_timeout_ms as timeout kwarg to session.run"""
        from graphrag_agent_zero.neo4j_connector import Neo4jConfig

        config = Neo4jConfig(query_timeout_ms=7500)
        connector = Neo4jConnector(config=config)

        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_result.__iter__ = Mock(return_value=iter([]))
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)
        mock_driver.session.return_value = mock_session

        connector._driver = mock_driver

        connector.execute_template("check_health", {})

        mock_session.run.assert_called_once()
        call_kwargs = mock_session.run.call_args
        # timeout should be in seconds (7500ms = 7.5s)
        assert call_kwargs.kwargs.get("timeout") == 7.5 or (
            len(call_kwargs.args) >= 3 and call_kwargs.args[2] == 7.5
        ), f"Expected timeout=7.5s, got call: {call_kwargs}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
