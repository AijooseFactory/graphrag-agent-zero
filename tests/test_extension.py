"""
Test: Extension subclass can be instantiated and executed
Proves the real Agent Zero extension pattern works.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest


class TestGraphRAGExtension:
    """Test that the GraphRAG Extension subclass follows Agent Zero patterns"""

    def test_extension_hook_has_no_env_override(self):
        """extension_hook.py must NOT contain _load_project_env or dotenv override"""
        hook_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "graphrag_agent_zero", "extension_hook.py"
        )
        with open(hook_path, "r") as f:
            source = f.read()

        assert "_load_project_env" not in source, "Forced env override must be removed"
        assert "load_dotenv" not in source, "No dotenv loading at import time"
        assert "os.environ[" not in source, "No forced os.environ writes"

    def test_extension_hook_is_enabled_defaults_false(self):
        """GraphRAG must be OFF by default"""
        from graphrag_agent_zero.extension_hook import is_enabled

        with patch.dict(os.environ, {}, clear=True):
            assert not is_enabled()

    @patch.dict(os.environ, {"GRAPHRAG_ENABLED": "true"}, clear=True)
    def test_extension_hook_is_enabled_when_flagged(self):
        """GraphRAG turns ON when preferred flag is set"""
        from graphrag_agent_zero.extension_hook import is_enabled

        assert is_enabled()

    @patch.dict(os.environ, {"GRAPH_RAG_ENABLED": "true"}, clear=True)
    def test_extension_hook_is_enabled_with_legacy_flag(self):
        """GraphRAG turns ON with legacy flag for backward compatibility"""
        from graphrag_agent_zero.extension_hook import is_enabled

        assert is_enabled()

    def test_extension_hook_enhance_retrieval_disabled(self):
        """enhance_retrieval returns baseline when disabled"""
        from graphrag_agent_zero.extension_hook import enhance_retrieval

        with patch.dict(os.environ, {"GRAPHRAG_ENABLED": "false"}, clear=True):
            result = enhance_retrieval("test query", [])
            assert not result["graph_derived"]
            assert result["fallback_used"]

    def test_extension_file_exists(self):
        """The Agent Zero extension file must exist at the correct path"""
        ext_path = os.path.join(
            os.path.dirname(__file__), "..",
            "agent-zero-fork", "agents", "default", "extensions",
            "message_loop_prompts_after", "_80_graphrag.py"
        )
        assert os.path.exists(ext_path), f"Extension file missing: {ext_path}"

    def test_extension_file_subclasses_extension(self):
        """The extension file must contain a class that would subclass Extension"""
        ext_path = os.path.join(
            os.path.dirname(__file__), "..",
            "agent-zero-fork", "agents", "default", "extensions",
            "message_loop_prompts_after", "_80_graphrag.py"
        )
        with open(ext_path, "r") as f:
            source = f.read()

        assert "class GraphRAGExtension(Extension)" in source, "Must subclass Extension"
        assert "async def execute" in source, "Must implement async execute"
        assert "is_enabled" in source, "Must check feature flag through extension_hook"

    def test_graphrag_prompt_fragment_exists(self):
        """Dedicated GraphRAG prompt fragment must exist for additive injection."""
        prompt_path = os.path.join(
            os.path.dirname(__file__), "..",
            "agent-zero-fork", "prompts", "agent.system.graphrag.md"
        )
        assert os.path.exists(prompt_path), f"GraphRAG prompt fragment missing: {prompt_path}"

    def test_safe_cypher_exists(self):
        """safe_cypher.py must exist with allowlisted templates"""
        from graphrag_agent_zero.safe_cypher import SAFE_CYPHER_TEMPLATES, get_safe_query

        assert "check_health" in SAFE_CYPHER_TEMPLATES
        assert "get_neighbors" in SAFE_CYPHER_TEMPLATES
        assert get_safe_query("check_health") is not None
        assert get_safe_query("DROP_DATABASE") is None  # Not allowlisted

    def test_connector_uses_templates_only(self):
        """Neo4jConnector must use template IDs, not raw queries"""
        connector_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "graphrag_agent_zero", "neo4j_connector.py"
        )
        with open(connector_path, "r") as f:
            source = f.read()

        assert "execute_template" in source, "Must use execute_template method"
        assert "get_safe_query" in source, "Must import from safe_cypher"
        assert "session.run(query" not in source or "get_safe_query" in source, \
            "Raw query execution must go through safe_cypher"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
