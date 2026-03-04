"""
GraphRAG for Agent Zero - LLM Extractor

Uses LiteLLM to call the configured Utility Model for high-quality
entity and relationship extraction with reasoning.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
import litellm

logger = logging.getLogger(__name__)

class LLMExtractor:
    """
    Extracts entities and relationships from text using the Utility Model.
    """
    
    def __init__(self, settings_path: str = "/a0/usr/settings.json"):
        self.settings_path = settings_path
        self.model_name = "llama3.2" # Default fallback
        self.provider = "ollama"
        self._load_settings()
        
    def _load_settings(self):
        """Load model settings from Agent Zero configuration"""
        try:
            # In Docker, the path is /a0/usr/settings.json
            # On host (for diagnostics), it might be different
            path = self.settings_path
            if not os.path.exists(path):
                # Try relative to Mac root if on host
                path = "/Users/george/Mac/data/usr/settings.json"
                
            if os.path.exists(path):
                with open(path, "r") as f:
                    settings = json.load(f)
                    self.model_name = settings.get("util_model_name", self.model_name)
                    self.provider = settings.get("util_model_provider", self.provider)
                    
                    # litellm config
                    if "litellm_global_kwargs" in settings:
                        api_base = settings["litellm_global_kwargs"].get("base_url", litellm.api_base)
                        # Fix for running on host: replace host.docker.internal with localhost
                        if api_base and "host.docker.internal" in api_base and not os.path.exists("/.dockerenv"):
                            api_base = api_base.replace("host.docker.internal", "localhost")
                        litellm.api_base = api_base
            
            logger.info(f"GraphRAG: Using Utility Model {self.model_name} via {self.provider}")
        except Exception as e:
            logger.warning(f"GraphRAG: Failed to load settings for LLMExtractor: {e}")

    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract entities and relationships from the provided text.
        """
        prompt = f"""
### TASK
Extract all significant entities and their relationships from the text below for a knowledge graph.

### GUIDELINES
1. **Think and Reason**: First, analyze the text to identify the primary subjects, objects, and how they interact. 
2. **Entity Types**: Categorize entities into these standard types: Person, Team, System, Component, Concept, Event, Decision, Incident, Change, or Document.
3. **Relationship Types**: Use meaningful relationship types such as REFERENCES, CONTAINS, MENTIONS, DEPENDS_ON, RELATED_TO, AUTHORED_BY, AFFECTS, MANAGED_BY, or WORKS_ON.
4. **Consistency**: Ensure entity names are consistent throughout and relationships are logically sound.

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
        try:
            model_id = f"{self.provider}/{self.model_name}" if self.provider != "openai" else self.model_name
            
            # Call litellm with a long timeout for reasoning models
            response = litellm.completion(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                # Note: some local models struggle with response_format="json_object"
                # while others (reasoning models) ignore it and explain first.
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
                return json.loads(json_content)
            except json.JSONDecodeError:
                # Clean up potential trailing commas or other common issues
                logger.warning("GraphRAG: JSON parsing failed, attempting fallback clean-up")
                # Very basic cleanup for trailing commas in arrays/objects
                cleaned = re.sub(r',\s*([\]}])', r'\1', json_content)
                return json.loads(cleaned)

        except Exception as e:
            logger.error(f"GraphRAG: LLM extraction failed: {e}")
            if 'content' in locals():
                logger.debug(f"Raw content: {content}")
            return {"entities": [], "relationships": []}
