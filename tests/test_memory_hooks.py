"""
Test: memory_save_before and memory_save_after hooks
Validates the Agent Zero collaborator requirements from PR #1176

Contract:
- memory_save_before receives mutable {object} dict
- object['text'] == None means skip save
- memory_save_after receives object with doc_id
- No try/catch around extension calls
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest


class TestMemorySaveHooks:
    """Test memory_save_before and memory_save_after hooks"""

    def _read_hook_source(self):
        hook_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "graphrag_agent_zero", "extension_hook.py"
        )
        with open(hook_path, "r") as f:
            return f.read()

    def _read_extension_source(self):
        ext_path = os.path.join(
            os.path.dirname(__file__), "..", "installer_files", "_80_graphrag.py"
        )
        with open(ext_path, "r") as f:
            return f.read()

    def test_memory_save_before_hook_exists(self):
        """memory_save_before hook must exist in extension_hook.py"""
        source = self._read_hook_source()
        assert "def memory_save_before(" in source, "memory_save_before hook must exist"
        assert "object: Dict[str, Any]" in source, "memory_save_before must accept object dict"

    def test_memory_save_after_hook_exists(self):
        """memory_save_after hook must exist in extension_hook.py"""
        source = self._read_hook_source()
        assert "def memory_save_after(" in source, "memory_save_after hook must exist"
        assert "object: Dict[str, Any]" in source, "memory_save_after must accept object dict"

    def test_memory_save_before_returns_object(self):
        """memory_save_before must return the object dict for chaining"""
        source = self._read_hook_source()
        assert "return object" in source, "memory_save_before must return the object"

    def test_memory_save_after_returns_object(self):
        """memory_save_after must return the object dict"""
        source = self._read_hook_source()
        assert "def memory_save_after(" in source
        assert "return object" in source, "memory_save_after must return object"

    def test_memory_save_before_handles_disabled(self):
        """memory_save_before must return object unchanged when GraphRAG disabled"""
        source = self._read_hook_source()
        assert "if not is_enabled()" in source or "is_enabled()" in source

    def test_memory_hooks_docstring_text_none_skip(self):
        """Hooks must document that object['text'] == None means skip save"""
        source = self._read_hook_source()
        assert "None" in source, "Must document None text behavior"
        assert "skip" in source.lower() or "skipped" in source.lower(), "Must mention skip behavior"

    def test_no_try_catch_in_memory_save_before(self):
        """memory_save_before must NOT have try/catch — extensions handle their own errors"""
        source = self._read_hook_source()
        # Find the memory_save_before function body
        start = source.index("def memory_save_before(")
        # Find the next function definition
        end = source.index("\ndef ", start + 1)
        func_body = source[start:end]
        assert "try:" not in func_body, "memory_save_before must not contain try/catch"
        assert "except " not in func_body, "memory_save_before must not contain try/catch"

    def test_extension_does_not_import_memory_edit_object(self):
        """Extension must not import MemoryEditObject — uses plain {object} dicts"""
        source = self._read_extension_source()
        assert "MemoryEditObject" not in source, "Must use plain dicts, not MemoryEditObject"

    def test_extension_handles_memory_save_before(self):
        """Extension must handle memory_save_before via {object} dict"""
        source = self._read_extension_source()
        assert "_handle_memory_save_before" in source, "Must have _handle_memory_save_before method"
        assert "obj: dict" in source or "object: dict" in source, "Must use dict parameter"

    def test_extension_handles_memory_save_after(self):
        """Extension must handle memory_save_after with doc_id"""
        source = self._read_extension_source()
        assert "_handle_memory_save_after" in source, "Must have _handle_memory_save_after method"
        assert "doc_id" in source, "Must reference doc_id"

    def test_no_legacy_memory_saved_after(self):
        """Must not have legacy memory_saved_after — renamed to memory_save_after"""
        source = self._read_extension_source()
        assert "memory_saved_after" not in source, "Legacy memory_saved_after must be removed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
