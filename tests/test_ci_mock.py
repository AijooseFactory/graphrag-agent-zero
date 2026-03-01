"""
Provider-agnostic CI Test
PR #1 MVP - Verifies GraphRAG entrypoint with mocked LLM/Provider
"""

import os
import sys
from unittest.mock import Mock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from graphrag_agent_zero.extension_hook import enhance_retrieval

class TestCIProviderAgnostic:
    """Tests that run without ANY provider keys or Neo4j"""
    
    @patch.dict(os.environ, {"GRAPH_RAG_ENABLED": "true"})
    @patch('graphrag_agent_zero.extension_hook.is_neo4j_available')
    @patch('graphrag_agent_zero.extension_hook.get_retriever')
    def test_enhance_retrieval_with_mocked_results(self, mock_get_retriever, mock_available):
        """enhance_retrieval works with mocked retriever & Neo4j"""
        mock_available.return_value = True
        
        # Mock retriever
        mock_retriever = Mock()
        mock_result = Mock()
        mock_result.to_context_pack.return_value = "Enriched graph context"
        mock_result.source_doc_ids = ["DOC-001"]
        mock_result.entities = ["Entity A"]
        mock_result.relationships = [("Entity A", "RELATED_TO", "Entity B")]
        mock_result.graph_derived = True
        mock_result.fallback_used = False
        mock_result.latency_ms = 10.5
        mock_result.cache_hit = False
        
        mock_retriever.retrieve.return_value = mock_result
        mock_get_retriever.return_value = mock_retriever
        
        # Test call
        query = "What is the status of the project?"
        vector_results = [{"doc_id": "DOC-001", "text": "Baseline text"}]
        
        result = enhance_retrieval(query, vector_results)
        
        assert result["text"] == "Enriched graph context"
        assert result["graph_derived"] == True
        assert "DOC-001" in result["sources"]
        print("✅ Provider-agnostic test passed")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
