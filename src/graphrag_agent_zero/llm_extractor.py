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
        self.model_name = None
        self.provider = None
        self._load_settings()
        
    def _load_settings(self):
        """Load model settings from Agent Zero configuration"""
        try:
            path = self.settings_path
            if not os.path.exists(path):
                # Fallback for host diagnostics
                path = "/Users/george/Mac/data/usr/settings.json"
                
            if os.path.exists(path):
                with open(path, "r") as f:
                    settings = json.load(f)
                    self.model_name = settings.get("util_model_name")
                    self.provider = settings.get("util_model_provider")
                    
                    # litellm config
                    if "litellm_global_kwargs" in settings:
                        api_base = settings["litellm_global_kwargs"].get("base_url")
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

    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract entities and relationships using the tiered Hybrid NER Pipeline.
        """
        # Tier 1: Fast NER Pass
        baseline_entities = self._fast_ner_extraction(text)
        baseline_json = json.dumps(baseline_entities, indent=2) if baseline_entities else "[]"
        
        # Tier 2: Deep LLM Relationship Extraction
        prompt = f"""
### TASK
Extract all significant entities and their relationships from the text below for a knowledge graph.

### FAST NER BASELINE
A fast heuristic pass has already identified these baseline entities. You MUST include them in your final output array, but your primary job is to find the complex RELATIONSHIPS between them (and any other entities you discover).
{baseline_json}

### GUIDELINES
1. **Think and Reason**: First, analyze the text to identify how the entities interact. 
2. **Entity Types**: Categorize entities into these standard types: Person, Team, System, Component, Concept, Event, Decision, Incident, Change, or Document.
3. **Relationship Types**: Use meaningful relationship types such as REFERENCES, CONTAINS, MENTIONS, DEPENDS_ON, RELATED_TO, AUTHORED_BY, AFFECTS, MANAGED_BY, or WORKS_ON.

### TEXT TO ANALYZE
{text}

### OUTPUT FORMAT
Provide your reasoning first, then return a valid JSON object demarcated with ```json ... ``` blocks.

Structure:
{{
  "entities": [
    {{ "name": "Entity Name", "type": "Type", "properties": {{ "description": "..." }} }}
  ],
  "relationships": [
    {{ "source": "Source Name", "target": "Target Name", "type": "TYPE", "properties": {{}} }}
  ]
}}
"""
        content = ""
        try:
            model_id = f"{self.provider}/{self.model_name}" if self.provider != "openai" else self.model_name
            
            # Tier 2: Deep LLM Relationship Extraction
            messages = []
            if self.system_optimization:
                messages.append({"role": "system", "content": self.system_optimization})
            
            messages.append({"role": "user", "content": prompt})
            
            # Call litellm with a long timeout for reasoning models
            response = litellm.completion(
                model=model_id,
                messages=messages,
                timeout=180
            )
            
            content = response.choices[0].message.content

            
            # MULTI-STAGE PARSER
            json_content = None
            
            # 1. Try to extract from markdown blocks
            if "```json" in content:
                json_content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                # Find the last block if multiple exist
                blocks = content.split("```")
                if len(blocks) >= 3:
                    json_content = blocks[-2].strip()
            
            # 2. If no blocks, try to find the first '{' and last '}'
            if not json_content:
                import re
                match = re.search(r'(\{.*\})', content, re.DOTALL)
                if match:
                    json_content = match.group(1)
            
            if not json_content:
                json_content = content.strip()

            # 3. Final Parse
            try:
                data = json.loads(json_content)
                # Success - return early
                return data
            except json.JSONDecodeError:
                # Clean up potential trailing commas or other common issues
                # Very basic cleanup for trailing commas in arrays/objects
                import re
                cleaned = re.sub(r',\s*([\]}])', r'\1', json_content)
                parsed = json.loads(cleaned)
                return parsed

        except Exception as e:
            logger.error(f"GraphRAG: LLM extraction failed: {e}")
            if content:
                self._write_to_dlq(content, str(e))
            return {"entities": [], "relationships": []}
