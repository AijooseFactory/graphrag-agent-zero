"""
Unit Tests for Safe Cypher Templates

Validates:
- get_entities_by_doc uses coalesce(e.entity_id, e.id) for compatibility
- validate_parameters enforces hard caps on limits
- Unknown template names return None
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from graphrag_agent_zero.safe_cypher import (
    get_safe_query,
    validate_parameters,
    SAFE_CYPHER_TEMPLATES,
)


class TestGetEntitiesByDocCoalesce:
    """Verify the coalesce(entity_id, id) fix is present"""

    def test_template_exists(self):
        """get_entities_by_doc template must exist"""
        query = get_safe_query("get_entities_by_doc")
        assert query is not None, "Template 'get_entities_by_doc' should exist"

    def test_uses_coalesce_for_id(self):
        """Template must use coalesce to support both entity_id and id"""
        query = get_safe_query("get_entities_by_doc")
        assert "coalesce(e.entity_id, e.id)" in query, (
            "get_entities_by_doc must use coalesce(e.entity_id, e.id) "
            "to support nodes indexed with either property"
        )

    def test_returns_name_and_type(self):
        """Template must return name and type columns"""
        query = get_safe_query("get_entities_by_doc")
        assert "e.name as name" in query
        assert "e.type as type" in query


class TestValidateParameters:
    """Verify parameter validation and hard caps"""

    def test_valid_parameters_pass(self):
        """Normal parameters should pass validation"""
        assert validate_parameters({"limit": 50}) is True

    def test_limit_capped_at_1000(self):
        """Limits over 1000 must be clamped to 100"""
        params = {"limit": 5000}
        result = validate_parameters(params)
        assert result is True, "Validation should still pass (clamped, not rejected)"
        assert params["limit"] == 100, "Limit must be clamped to 100"

    def test_limit_at_boundary(self):
        """Limit of exactly 1000 should pass without clamping"""
        params = {"limit": 1000}
        validate_parameters(params)
        assert params["limit"] == 1000

    def test_entity_ids_must_be_list(self):
        """entity_ids must be a list"""
        assert validate_parameters({"entity_ids": "not-a-list"}) is False

    def test_entity_ids_must_contain_strings(self):
        """entity_ids list must contain only strings"""
        assert validate_parameters({"entity_ids": [1, 2, 3]}) is False

    def test_valid_entity_ids(self):
        """Valid entity_ids should pass"""
        assert validate_parameters({"entity_ids": ["e1", "e2"]}) is True

    def test_empty_params(self):
        """Empty parameters should pass"""
        assert validate_parameters({}) is True


class TestGetSafeQuery:
    """Verify template lookup behavior"""

    def test_unknown_template_returns_none(self):
        """Unknown template names must return None"""
        assert get_safe_query("nonexistent_template") is None

    def test_check_health_exists(self):
        """check_health template must exist"""
        assert get_safe_query("check_health") is not None

    def test_all_templates_are_strings(self):
        """Every template value must be a non-empty string"""
        for name, query in SAFE_CYPHER_TEMPLATES.items():
            assert isinstance(query, str), f"Template '{name}' must be a string"
            assert len(query.strip()) > 0, f"Template '{name}' must not be empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
