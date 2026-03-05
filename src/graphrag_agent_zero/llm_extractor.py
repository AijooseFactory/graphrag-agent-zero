"""
GraphRAG for Agent Zero - LLM Extractor

Uses LiteLLM to call the configured Utility Model for high-quality
entity and relationship extraction with reasoning.
"""

import os
import json
import logging
from typing import Dict, Any
import litellm

logger = logging.getLogger(__name__)

class LLMExtractor:
    """
    Extracts entities and relationships from text using the Utility Model.
    """
    
    def __init__(self, settings_path: str = "/a0/usr/settings.json"):
        self.settings_path = settings_path
        self.config = {} 
        self._load_settings()

    @property
    def provider(self) -> str:
        """Get provider (e.g., 'openai', 'anthropic', 'ollama')"""
        p = self.config.get("util_model_provider", "openai")
        return p.split("/")[0] if "/" in p else p

    @property
    def model_name(self) -> str:
        """Get model name (e.g., 'gpt-4o-mini', 'llama3')"""
        model = self.config.get("util_model_name", "gpt-4o-mini")
        # Safety: if model includes a provider prefix that matches our provider, strip it
        # This prevents litellm from doubling up prefixes (e.g., openai/openai/gpt)
        prov = self.provider
        if model.startswith(f"{prov}/"):
            return model[len(prov)+1:]
        return model
        
    def _load_settings(self):
        """Load model settings from Agent Zero configuration"""
        try:
            path = self.settings_path
            if not os.path.exists(path):
                # Universal fallback logic for different Agent Zero mount layouts
                possible_paths = [
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../settings.json")),
                    "/a0/usr/settings.json",
                    "/Mac/data/usr/settings.json"
                ]
                for p in possible_paths:
                    if os.path.exists(p):
                        path = p
                        break
                
            if os.path.exists(path):
                with open(path, "r") as f:
                    self.config = json.load(f)
                    
                    # litellm config
                    if "litellm_global_kwargs" in self.config:
                        api_base = self.config["litellm_global_kwargs"].get("base_url")
                        if api_base:
                            # Fix for running on host: replace host.docker.internal with localhost
                            if "host.docker.internal" in api_base and not os.path.exists("/.dockerenv"):
                                api_base = api_base.replace("host.docker.internal", "localhost")
                            litellm.api_base = api_base
            
            # Load the Cognitive Optimization prompt
            prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "cognitive_optimization.md")
            self.system_optimization = ""
            if os.path.exists(prompt_path):
                with open(prompt_path, "r") as f:
                    self.system_optimization = f.read()
                    logger.info("GraphRAG: Utility Model optimized with Cognitive Optimization prompt")
            
            if self.model_name:
                logger.info(f"GraphRAG: Using Utility Model {self.model_name} via {self.provider or 'default'}")
            else:
                logger.warning("GraphRAG: No Utility Model configured in settings.json. Extraction may fail.")
        except Exception as e:
            logger.warning(f"GraphRAG: Failed to load settings for LLMExtractor: {e}")

    def _fast_ner_extraction(self, text: str) -> list:
        """Zero-token heuristic extraction for baseline entities (Classes, Paths, Concepts)"""
        import re
        entities = []
        seen = set()
        
        # 1. CamelCase/PascalCase (Code Classes/Functions)
        for m in re.finditer(r'\b([A-Z][a-z]+[A-Z][A-Za-z]+)\b', text):
            name = m.group(1)
            if name not in seen:
                entities.append({"name": name, "type": "Component", "properties": {"description": "Auto-extracted Component"}})
                seen.add(name)
                
        # 2. File paths
        for m in re.finditer(r'\b(/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b', text):
            name = m.group(1)
            if name not in seen:
                entities.append({"name": name, "type": "Document", "properties": {"description": "Auto-extracted File Path"}})
                seen.add(name)
                
        # 3. Capitalized Phrases (Names/Concepts)
        for m in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b', text):
            name = m.group(1)
            if name not in seen:
                entities.append({"name": name, "type": "Concept", "properties": {"description": "Auto-extracted Concept"}})
                seen.add(name)
                
        return entities

    def _write_to_dlq(self, raw_content: str, error: str):
        """Append failed extractions to Dead Letter Queue for human review."""
        import datetime
        # In Docker, path is likely /a0/usr/logs
        log_dir = "/a0/usr/logs"
        if not os.path.exists(log_dir):
            # Fallback for host diagnostics
            log_dir = os.path.join(os.path.dirname(__file__), "../../../agent-zero-fork/usr/logs")
            
        os.makedirs(log_dir, exist_ok=True)
        dlq_path = os.path.join(log_dir, "failed_extractions.jsonl")
        
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "model": f"{self.provider}/{self.model_name}",
            "error": error,
            "raw_content": raw_content
        }
        try:
            with open(dlq_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
            logger.warning(f"GraphRAG: Extraction failed, raw output secured in DLQ: {dlq_path}")
        except Exception as e:
            logger.error(f"GraphRAG DLQ FAILURE: {e}")

    def _get_config(self, key: str, default: Any) -> Any:
        """Get config from environment or fallback to default"""
        return os.environ.get(key, default)

    def _redact_secrets(self, text: str) -> str:
        """Basic redaction for potential secrets in evidence snippets"""
        import re
        # Case-insensitive redaction for common secret-carrying patterns
        # 1. Assignments: key="secret", pass: 12345, password is admin123, etc.
        # We catch the 'is' or '=' or ':' followed by a potential secret.
        assignment_pattern = r'(?i)(?:key|pass(?:word)?|pw|secret|token|auth)\s*(?:[:=]|\bis\b)\s*["\']?([a-zA-Z0-9_\-!@#$%^&*]{4,})["\']?'
        # 2. Long identifiers: 32+ char hex/base64-like strings
        long_id_pattern = r'\b[a-zA-Z0-9_\-]{32,}\b'
        
        redacted = text
        
        # Redact assignments
        def redact_assignment(m):
            # If we have a captured group, redact it in the full match
            if m.group(1):
                return m.group(0).replace(m.group(1), "[REDACTED]")
            return "[REDACTED]"

        redacted = re.sub(assignment_pattern, redact_assignment, redacted)
        
        # Redact long standalone tokens
        redacted = re.sub(long_id_pattern, "[REDACTED]", redacted)
        
        return redacted

    def _validate_extraction_schema(self, data: Any) -> bool:
        """Validate the extraction payload against required schema"""
        if not isinstance(data, dict):
            return False
        if "entities" not in data or not isinstance(data["entities"], list):
            return False
        if "relationships" not in data or not isinstance(data["relationships"], list):
            return False
        
        # Check entity structure
        for ent in data["entities"]:
            if not isinstance(ent, dict) or "name" not in ent or "type" not in ent:
                return False
        
        # Check relationship structure
        for rel in data["relationships"]:
            if not isinstance(rel, dict) or "source" not in rel or "target" not in rel:
                return False
        
        return True

    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract entities and relationships using the LLM-First Semantic Pipeline.
        """
        mode = self._get_config("GRAPHRAG_EXTRACTION_MODE", "llm_first")
        max_entities = int(self._get_config("GRAPHRAG_MAX_ENTITIES", 20))
        max_rels = int(self._get_config("GRAPHRAG_MAX_RELATIONSHIPS", 30))
        max_snippet_chars = int(self._get_config("GRAPHRAG_EVIDENCE_SNIPPET_MAX_CHARS", 300))

        # Tier 0: Heuristic Pass (Candidate Hints only)
        baseline_entities = self._fast_ner_extraction(text)
        hints_json = json.dumps(baseline_entities[:10], indent=2) if baseline_entities else "[]"
        
        if mode == "heuristic":
            return {"entities": baseline_entities, "relationships": []}

        # Tier 1: Deep LLM Semantic Sweep
        prompt = f"""
### TASK
Perform a deep semantic sweep to extract significant entities and their relationships. 
First, THINK and reason about the text interactions. Identify implicit concepts, decisions, and evolving states.

### CANDIDATE HINTS (Heuristic)
{hints_json}

### GUIDELINES
1. **Discover & Link**: Find entities beyond the hints. Focus on semantic depth.
2. **Standard Types**: Person, Team, System, Component, Concept, Event, Decision, Incident, Change, Document.
3. **Evidence**: For each entity/relationship, provide a concise 'evidence' snippet (max 300 chars) from the text.
4. **Safety**: Do not extract secrets, keys, or private identifiers.

### TEXT TO ANALYZE
{text}

### OUTPUT FORMAT
Return a valid JSON object within ```json ... ``` blocks.
{{
  "entities": [
    {{ 
      "name": "Entity Name", 
      "type": "Type", 
      "properties": {{ "description": "...", "evidence": "..." }},
      "aliases": ["synonym1", "synonym2"] 
    }}
  ],
  "relationships": [
    {{ 
      "source": "Source Name", 
      "target": "Target Name", 
      "type": "TYPE", 
      "properties": {{ "evidence": "..." }} 
    }}
  ]
}}
"""
        content = ""
        try:
            model_id = f"{self.provider}/{self.model_name}" if self.provider != "openai" else self.model_name
            messages = [{"role": "user", "content": prompt}]
            if self.system_optimization:
                messages.insert(0, {"role": "system", "content": self.system_optimization})
            
            response = litellm.completion(model=model_id, messages=messages, timeout=180)
            content = response.choices[0].message.content

            # MULTI-STAGE PARSER
            json_content = None
            if "```json" in content:
                json_content = content.split("```json")[1].split("```")[0].strip()
            else:
                import re
                match = re.search(r'(\{.*\})', content, re.DOTALL)
                if match:
                    json_content = match.group(1)
            
            if not json_content:
                json_content = content.strip()

            # Final Parse & Safety Bounds
            data = json.loads(json_content)
            
            if not self._validate_extraction_schema(data):
                raise ValueError("LLM output failed schema validation")

            # Apply Bounds & Redaction
            data["entities"] = data["entities"][:max_entities]
            data["relationships"] = data["relationships"][:max_rels]

            for ent in data["entities"]:
                props = ent.get("properties", {})
                snippet = props.get("evidence", "")
                props["evidence"] = self._redact_secrets(str(snippet)[:max_snippet_chars])
                ent["properties"] = props
                
            for rel in data["relationships"]:
                props = rel.get("properties", {})
                snippet = props.get("evidence", "")
                props["evidence"] = self._redact_secrets(str(snippet)[:max_snippet_chars])
                rel["properties"] = props

            return data

        except Exception as e:
            logger.error(f"GraphRAG: LLM extraction failed ({e}). Falling back to heuristics.")
            if content:
                self._write_to_dlq(content, str(e))
            return {"entities": baseline_entities, "relationships": []}
