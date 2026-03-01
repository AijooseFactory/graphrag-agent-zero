"""
GraphRAG Extension for Agent Zero
Extension Point: message_loop_prompts_after

Injects graph-derived context into the agent's prompt extras when:
  1. GRAPH_RAG_ENABLED=true
  2. Neo4j is reachable

NO core patches. Uses only the upstream Extensions Framework.
"""

import os
import logging
import json
from python.helpers.extension import Extension

logger = logging.getLogger(__name__)

# Lazy import to avoid hard dependency on the graphrag package
_graphrag_available = None


def _check_graphrag():
    """Check if graphrag_agent_zero package is importable."""
    global _graphrag_available
    if _graphrag_available is None:
        try:
            from graphrag_agent_zero.extension_hook import is_enabled, is_neo4j_available  # noqa: F401
            _graphrag_available = True
        except ImportError:
            _graphrag_available = False
            logger.info("graphrag_agent_zero package not installed — GraphRAG disabled")
    return _graphrag_available


class GraphRAGExtension(Extension):
    """
    GraphRAG Intelligence Extension for Agent Zero.
    
    This extension intercepts the message loop after basic retrieval but before 
    the prompt is finalized. It performs a parallel graph search in Neo4j 
    and injects discovered entities and context into the prompt extras.
    
    MAINTENANCE NOTE for Mac:
    - This is a standard 'Extension' subclass defined by the Agent Zero framework.
    - It uses 'extras_persistent' to communicate with the prompt templating system.
    - No core files are modified; this is a pure add-on.

    ⚠️ TOP 1% LLM-KEYLESS TESTING ARCHITECTURE ⚠️
    Any AI agent modifying this file MUST honor the deterministic E2E verification pattern:
    1. During E2E tests, LiteLLM is spoofed to route to a local stub (`dev/llm_stub/app.py`).
    2. The stub mathematically verifies `GRAPHRAG_CONTEXT` via SHA256 Hash Round-Tripping.
    3. You must NEVER remove the `GRAPHRAG_*` print log markers, as these act as unbreakable
       verification gates for the E2E bash scripting. Do not add API keys to test files.
    """

    async def execute(self, loop_data=None, **kwargs):
        """
        Main execution hook called by the Agent Zero message loop.
        
        Args:
            loop_data: The state object for the current message loop iteration.
            kwargs: Additional framework-provided parameters.
        """
        # Mandatory marker for E2E verification
        print("GRAPHRAG_AGENT_EXTENSION_EXECUTED", flush=True)

        # GATE 1: Feature Flag Check
        # Allows for safe deployment where GraphRAG is installed but dormant.
        if os.getenv("GRAPH_RAG_ENABLED", "false").lower() != "true":
            return

        # GATE 2: Package Availability Check
        # Ensures a clean fail if the graphrag-agent-zero package is missing.
        if not _check_graphrag():
            return

        # GATE 3: Neo4j Availability Check (Safe Resilience)
        # Prevents crashing or slowdowns if the graph database is offline.
        from graphrag_agent_zero.extension_hook import (
            is_neo4j_available,
            enhance_retrieval,
        )

        if not is_neo4j_available():
            # Log marker for E2E resilience verification
            print("GRAPHRAG_NOOP_NEO4J_DOWN", flush=True)
            return

        # VALIDATION: Ensure we have loop state to work with
        if loop_data is None:
            return

        # EXTRACT: Get the user's raw input message
        user_msg = ""
        if hasattr(loop_data, "user_message") and loop_data.user_message:
            user_msg = loop_data.user_message.output_text()

        if not user_msg:
            return

        try:
            # ENHANCE: Call the core hybrid retrieval logic from the src package
            # This is where entities are extracted and Neo4j is queried.
            result = enhance_retrieval(
                query=user_msg,
                vector_results=[],  # Agent Zero's native memory handles its own vector search
            )

            # INJECT: Provide structured JSON to Agent Zero for "Top 1% Perfect" parsing
            # Agent Zero's prompt system automatically renders anything in extras_persistent
            extras = loop_data.extras_persistent
            
            graph_data = {
                "source": "GraphRAG (Neo4j)",
                "injected_knowledge": result["text"].strip(),
            }
            
            if result.get("entities"):
                graph_data["related_entities"] = result["entities"][:30] # expanded entity capture
            
            import hashlib
            context_text = json.dumps(graph_data, indent=2)
            block = f"GRAPHRAG_CONTEXT_BLOCK_START\n{context_text}\nGRAPHRAG_CONTEXT_BLOCK_END"
            
            # Hash round-trip for Top 1% validation
            ctx_hash = hashlib.sha256(block.encode("utf-8")).hexdigest()
            print(f"GRAPHRAG_CONTEXT_SHA256={ctx_hash}", flush=True)
            print("GRAPHRAG_HOOKPOINT=message_loop_prompts_after", flush=True)
            print(f"GRAPHRAG_LOOPDATA_KEYS={sorted(list(extras.keys()))}", flush=True)

            # We inject this as a formatted JSON string to guarantee it's treated as a single, clear object block
            extras["graphrag"] = block

            # Mandatory marker for E2E success verification
            print("GRAPHRAG_CONTEXT_INJECTED", flush=True)
            print(
                f"GraphRAG injected {len(result.get('entities', []))} entities, "
                f"latency={result.get('latency_ms', 0):.0f}ms", flush=True
            )
        except Exception as e:
            # SAFETY: Never crash the main agent message loop.
            # If GraphRAG fails, we log a warning and let the agent proceed normally.
            logger.warning(f"GraphRAG extension error (graceful no-op): {e}")
