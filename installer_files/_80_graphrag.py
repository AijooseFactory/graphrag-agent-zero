"""
GraphRAG Extension for Agent Zero
Extension Point: message_loop_prompts_after

Injects graph-derived context into the agent's prompt extras when:
  1. GRAPH_RAG_ENABLED=true
  2. Neo4j is reachable

NO core patches. Uses only the upstream Extensions Framework.
"""

import logging
import json
import hashlib
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


def _clear_graphrag_context(loop_data):
    """Remove stale GraphRAG context so non-graph turns remain baseline-clean."""
    if loop_data is None or not hasattr(loop_data, "extras_persistent"):
        return
    extras = loop_data.extras_persistent
    if isinstance(extras, dict) and extras.pop("graphrag", None) is not None:
        print("GRAPHRAG_CONTEXT_CLEARED", flush=True)


def _ordered_hybrid_extras(extras: dict) -> dict:
    """
    Enforce deterministic additive ordering:
    1) memory recall extras (existing)
    2) graphrag extra (new)
    3) all other extras unchanged (relative order preserved)
    """
    ordered: dict = {}

    for key in ("memories", "solutions"):
        if key in extras:
            ordered[key] = extras[key]

    if "graphrag" in extras:
        ordered["graphrag"] = extras["graphrag"]

    for key, value in extras.items():
        if key not in ordered:
            ordered[key] = value

    return ordered


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

    async def execute(self, loop_data=None, system_prompt: list = None, memory_id: str = None, content: str = None, **kwargs):
        """
        Polymorphic dispatcher for Agent Zero Extension Hooks.
        
        This enables a single 'Master' file to serve multiple extension points:
        1. system_prompt: kwargs['system_prompt'] is present.
        2. memory_saved_after: kwargs['memory_id'] is present.
        3. message_loop_prompts_after: Default execution path.
        """
        
        # Hook 1: Core System Prompt Injection
        if system_prompt is not None:
            return await self._handle_system_prompt(system_prompt, loop_data=loop_data, **kwargs)

        # Hook 2: Real-time Memory Synchronization
        if memory_id is not None and content is not None:
            return await self._handle_memory_saved_after(memory_id, content, **kwargs)

        # Hook 3: Message Loop Context Injection (Default)
        return await self._handle_message_loop_prompts(loop_data, **kwargs)

    async def _handle_system_prompt(self, system_prompt: list, loop_data=None, **kwargs):
        """
        Injects the anti-hallucination guard rails and Cognitive Optimization
        natively into the agent's core instructions.
        """
        from graphrag_agent_zero.extension_hook import is_enabled
        if not is_enabled():
            return

        system_prompt.append(
            "\n\n--- 🧠 GRAPHRAG MEMORY BRAIN CONTROLS ---\n"
            "You are equipped with a GraphRAG Hybrid Memory System.\n"
            "CRITICAL DIRECTIVES FOR MEMORY TOOLS:\n"
            "1. NO SIMULATIONS: You are explicitly forbidden from generating 'simulated' markdown reports of saving or deleting memories if you did not physically invoke the `memory_save` or `memory_delete` tools.\n"
            "2. FACTUAL VERIFICATION REQUIRED: You must never report that a memory was successfully saved until you have actively verified its existence in the database by physically calling `memory_load` to retrieve it.\n"
            "3. HYGIENE: If instructed to test or purge a memory, you must physically call `memory_delete` with the exact ID.\n"
            "Failure to use the actual JSON tool APIs for these actions is a severe violation of your core cognitive parameters."
        )

        # Inject Cognitive Optimization Prompt (Deep Synthesis methodology)
        from graphrag_agent_zero.extension_hook import get_cognitive_optimization_prompt
        optimized_prompt = get_cognitive_optimization_prompt()
        if optimized_prompt:
            system_prompt.append(
                "\n\n--- 🧠 COGNITIVE OPTIMIZATION: INTELLECTUAL RESEARCH ---\n"
                f"{optimized_prompt}"
            )
            print("GRAPHRAG_COGNITIVE_OPTIMIZATION_INJECTED", flush=True)

    async def _handle_message_loop_prompts(self, loop_data=None, **kwargs):
        """
        Original execute logic for message_loop_prompts_after.
        """
        # Mandatory markers for E2E verification
        print("GRAPHRAG_EXTENSION_EXECUTED", flush=True)
        print("GRAPHRAG_AGENT_EXTENSION_EXECUTED", flush=True)

        if not _check_graphrag():
            _clear_graphrag_context(loop_data)
            return

        from graphrag_agent_zero.extension_hook import is_enabled
        if not is_enabled():
            _clear_graphrag_context(loop_data)
            return

        from graphrag_agent_zero.extension_hook import (
            is_neo4j_available,
            enhance_retrieval,
        )

        if not is_neo4j_available():
            print("GRAPHRAG_NOOP_NEO4J_DOWN", flush=True)
            _clear_graphrag_context(loop_data)
            return

        if loop_data is None:
            return

        user_msg = ""
        if hasattr(loop_data, "user_message") and loop_data.user_message:
            user_msg = loop_data.user_message.output_text()

        if not user_msg:
            _clear_graphrag_context(loop_data)
            return

        try:
            result = enhance_retrieval(
                query=user_msg,
                vector_results=[],
            )

            injected_knowledge = result.get("text", "").strip()
            if not injected_knowledge:
                print("GRAPHRAG_NOOP_EMPTY_CONTEXT", flush=True)
                _clear_graphrag_context(loop_data)
                return

            extras = loop_data.extras_persistent
            graph_data = {
                "source": "GraphRAG (Neo4j)",
                "injected_knowledge": injected_knowledge,
            }
            if result.get("entities"):
                graph_data["related_entities"] = result["entities"][:30]
            
            context_text = json.dumps(graph_data, indent=2, sort_keys=True)
            ctx_hash = hashlib.sha256(context_text.encode("utf-8")).hexdigest()
            print(f"GRAPHRAG_CONTEXT_SHA256={ctx_hash}", flush=True)
            print("GRAPHRAG_HOOKPOINT=message_loop_prompts_after", flush=True)

            extras["graphrag"] = self.agent.parse_prompt(
                "agent.system.graphrag.md",
                context_json=context_text,
                context_sha256=ctx_hash,
                context_sentinel="HYBRID_GRAPHRAG_CONTEXT_V1",
            )
            loop_data.extras_persistent = _ordered_hybrid_extras(extras)
            print("GRAPHRAG_CONTEXT_INJECTED", flush=True)
        except Exception as e:
            logger.warning(f"GraphRAG extension error: {e}")

    async def _handle_memory_saved_after(self, memory_id: str, content: str, **kwargs):
        """
        Original memory_saved_after logic.
        """
        if not _check_graphrag():
            return

        from graphrag_agent_zero.extension_hook import is_enabled, build_knowledge_graph
        if not is_enabled():
            return

        try:
            print(f"GRAPHRAG_SYNC_TRIGGERED: {memory_id}", flush=True)
            build_knowledge_graph([{"id": memory_id, "content": content}])
            print(f"GRAPHRAG_SYNC_SUCCESS: {memory_id}", flush=True)
        except Exception as e:
            logger.warning(f"GraphRAG real-time sync failed for {memory_id}: {e}")




