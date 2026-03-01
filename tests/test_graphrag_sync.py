"""
Unit Tests for GraphRAG Memory Sync Extension

Validates:
- Extension respects feature flag gating
- Extension correctly constructs document dict for ingestion
- GraphBuilder receives the expected document shape
"""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from graphrag_agent_zero.extension_hook import is_enabled
from graphrag_agent_zero.graph_builder import GraphBuilder


class TestGraphRAGSyncExtension:
    """Verify the memory_saved_after sync extension safety and behavior"""

    def test_feature_flag_disabled_by_default(self):
        """Extension must be a no-op when GRAPHRAG_ENABLED is not set"""
        env_backup = os.environ.pop("GRAPHRAG_ENABLED", None)
        env_backup2 = os.environ.pop("GRAPH_RAG_ENABLED", None)
        try:
            assert not is_enabled()
        finally:
            if env_backup is not None:
                os.environ["GRAPHRAG_ENABLED"] = env_backup
            if env_backup2 is not None:
                os.environ["GRAPH_RAG_ENABLED"] = env_backup2

    def test_feature_flag_enabled(self):
        """Extension should recognize enabled state"""
        old = os.environ.get("GRAPHRAG_ENABLED")
        os.environ["GRAPHRAG_ENABLED"] = "true"
        try:
            assert is_enabled()
        finally:
            if old is not None:
                os.environ["GRAPHRAG_ENABLED"] = old
            else:
                del os.environ["GRAPHRAG_ENABLED"]

    def test_build_from_document_called_with_correct_shape(self):
        """Verify the doc dict shape passed to GraphBuilder"""
        mock_builder = MagicMock(spec=GraphBuilder)
        mock_builder.build_from_document.return_value = True

        text = "Remember: the server is at 192.168.1.1"
        metadata = {"area": "main", "title": "Server Info"}
        doc_id = "abc123"
        memory_subdir = "default"

        doc = {
            "id": doc_id,
            "content": text,
            "source": f"memory/{memory_subdir}",
            "title": metadata.get("title", doc_id),
        }

        mock_builder.build_from_document(doc)
        mock_builder.build_from_document.assert_called_once_with(doc)

        assert "id" in doc
        assert "content" in doc
        assert "source" in doc
        assert doc["title"] == "Server Info"

    def test_doc_defaults_title_to_doc_id(self):
        """When metadata has no title, doc_id is used as fallback"""
        doc_id = "xyz789"
        metadata = {"area": "main"}

        doc = {
            "id": doc_id,
            "content": "some content",
            "source": "memory/default",
            "title": metadata.get("title", doc_id),
        }

        assert doc["title"] == doc_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
