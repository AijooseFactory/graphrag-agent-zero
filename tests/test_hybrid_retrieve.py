"""
Unit Tests for Hybrid Retriever
PR #1 MVP - Tests retrieval pipeline
"""

import os
import sys
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from hybrid_retrieve import HybridRetriever, RetrievalResult


class TestHybridRetriever:
    """Test HybridRetriever pipeline"""
    
    def test_retrieval_result_defaults(self):
        """RetrievalResult has correct defaults"""
        result = RetrievalResult(
            query="test query",
            context="test context",
            source_doc_ids=[]
        )
        assert result.query == "test query"
        assert result.fallback_used == True, "Default is fallback"
        assert result.graph_derived == False, "Default no graph"
    
    @patch('hybrid_retrieve.is_neo4j_available')
    def test_retrieve_when_disabled_uses_fallback(self, mock_available):
        """When GraphRAG disabled, uses fallback retrieval"""
        mock_available.return_value = False
        
        retriever = HybridRetriever()
        result = retriever.retrieve("test query")
        
        assert result.fallback_used == True
        assert result.graph_derived == False
    
    @patch('hybrid_retrieve.is_neo4j_available')
    @patch('hybrid_retrieve.VectorStore')
    def test_retrieve_enabled_uses_hybrid(self, mock_vector, mock_available):
        """When GraphRAG enabled, uses hybrid retrieval"""
        mock_available.return_value = True
        
        # Mock vector store
        mock_vs = Mock()
        mock_vs.similarity_search.return_value = [
            {"page_content": "doc1", "metadata": {"id": "DOC-001"}}
        ]
        mock_vector.return_value = mock_vs
        
        retriever = HybridRetriever()
        result = retriever.retrieve("test query")
        
        assert result.fallback_used == False
    
    def test_context_pack_format(self):
        """Context pack uses correct [DOC-ID] format"""
        result = RetrievalResult(
            query="test",
            context="Content from [DOC-001] and [DOC-002].",
            source_doc_ids=["DOC-001", "DOC-002"]
        )
        context = result.to_context_pack()
        assert "[DOC-001]" in context
        assert "[DOC-002]" in context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
