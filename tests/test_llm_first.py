import unittest
from graphrag_agent_zero.llm_extractor import LLMExtractor
from graphrag_agent_zero.graph_builder import GraphBuilder

class TestLLMFirstUpgrade(unittest.TestCase):
    def setUp(self):
        self.extractor = LLMExtractor()
        self.builder = GraphBuilder(extract_llm=False)

    def test_schema_validation(self):
        """Verify schema validation rejects malformed payloads"""
        valid_data = {
            "entities": [{"name": "Test", "type": "Concept", "properties": {}}],
            "relationships": [{"source": "A", "target": "B", "type": "REL"}]
        }
        invalid_data = {"entities": "not a list"}
        
        self.assertTrue(self.extractor._validate_extraction_schema(valid_data))
        self.assertFalse(self.extractor._validate_extraction_schema(invalid_data))

    def test_property_sanitation(self):
        """Verify property sanitation neutralizes nested objects and control chars"""
        unsafe_props = {
            "nested": {"key": "value"},
            "control": "line1\nline2\x00stop",
            "too_long": "A" * 2000,
            "valid": "safe"
        }
        sanitized = self.builder._sanitize_properties(unsafe_props)
        
        self.assertIsInstance(sanitized["nested"], str)
        self.assertNotIn("\n", sanitized["control"])
        self.assertNotIn("\x00", sanitized["control"])
        self.assertEqual(len(sanitized["too_long"]), 1000)
        self.assertEqual(sanitized["valid"], "safe")

    def test_alias_resolution(self):
        """Verify J. Smith and John Smith merge when aliases are provided"""
        entities = [
            {"name": "John Smith", "type": "Person", "aliases": ["J. Smith"]},
            {"name": "J. Smith", "type": "Person", "properties": {"occupation": "Dev"}}
        ]
        resolved = self.builder.deduplicate_entities(entities)
        
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["name"], "John Smith")
        self.assertIn("J. Smith", resolved[0]["properties"]["aliases"])
        self.assertEqual(resolved[0]["properties"]["occupation"], "Dev")

    def test_redaction(self):
        """Verify secrets are redacted from evidence snippets"""
        unsafe_text = "The password is 'admin123' and the token is abc123def456ghi789jkl012mno345pqr"
        redacted = self.extractor._redact_secrets(unsafe_text)
        self.assertIn("[REDACTED]", redacted)
        self.assertNotIn("admin123", redacted)

if __name__ == "__main__":
    unittest.main()
