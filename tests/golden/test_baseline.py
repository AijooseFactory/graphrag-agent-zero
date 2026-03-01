"""
Golden Test: Baseline Behavior Verification

CRITICAL: When GRAPH_RAG_ENABLED=false, behavior must match baseline exactly.
This test ensures no regressions when the extension is disabled.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from graphrag_agent_zero.neo4j_connector import is_neo4j_available
from graphrag_agent_zero.hybrid_retrieve import HybridRetriever


def test_feature_flag_disabled():
    """Test that GraphRAG is disabled by default"""
    # Ensure feature flag is off
    os.environ["GRAPH_RAG_ENABLED"] = "false"
    
    # Should return False when disabled
    assert not is_neo4j_available(), "GraphRAG should be disabled by default"
    print("✅ Feature flag test passed")


def test_fallback_retrieval():
    """Test that fallback retrieval works when GraphRAG disabled"""
    os.environ["GRAPH_RAG_ENABLED"] = "false"
    
    retriever = HybridRetriever()
    
    # Mock vector results
    vector_results = [
        {"doc_id": "ADR-001", "text": "Test document content", "score": 0.9},
        {"doc_id": "ADR-002", "text": "Another document", "score": 0.8},
    ]
    
    result = retriever.retrieve("test query", vector_results)
    
    # Should use fallback
    assert result.fallback_used, "Should use fallback when disabled"
    assert not result.graph_derived, "Should not have graph-derived content"
    assert len(result.source_doc_ids) == 2, "Should preserve source doc IDs"
    print("✅ Fallback retrieval test passed")


def test_citation_format():
    """Test that citations are in deterministic [DOC-ID] format"""
    os.environ["GRAPH_RAG_ENABLED"] = "false"
    
    retriever = HybridRetriever()
    vector_results = [{"doc_id": "ADR-001", "text": "Content"}]
    
    result = retriever.retrieve("test", vector_results)
    context = result.to_context_pack()
    
    # Should contain structured citation
    assert "[ADR-001]" in context, "Should use [DOC-ID] citation format"
    print("✅ Citation format test passed")


def run_all_golden_tests():
    """Run all golden tests"""
    print("\n=== RUNNING GOLDEN TESTS ===")
    test_feature_flag_disabled()
    test_fallback_retrieval()
    test_citation_format()
    print("\n✅ ALL GOLDEN TESTS PASSED")


if __name__ == "__main__":
    run_all_golden_tests()
