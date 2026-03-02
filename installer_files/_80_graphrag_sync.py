"""
GraphRAG Memory Sync Extension
Extension Point: memory_saved_after

Automatically indexes newly saved memories into the Neo4j knowledge graph.

Safety:
  - Feature-flag gated (GRAPHRAG_ENABLED / GRAPH_RAG_ENABLED)
  - Full exception isolation — never crashes the memory save flow
  - Lazy imports — no hard dependency on graphrag_agent_zero package
  - Fire-and-forget indexing — if Neo4j is down, silently skips

This extension is placed in python/extensions/ (global) so it fires for ALL
agent profiles, regardless of which profile saved the memory.
"""

import logging
from python.helpers.extension import Extension

logger = logging.getLogger(__name__)


class GraphRAGSyncExtension(Extension):
    """
    Indexes each new memory into the Neo4j knowledge graph via GraphBuilder.

    Triggered by the memory_saved_after hook in Memory.insert_text().
    """

    async def execute(self, text="", metadata=None, doc_id="", memory_subdir="", **kwargs):
        """
        Index a single saved memory into Neo4j.

        Args:
            text: The memory content that was just saved.
            metadata: Dict of memory metadata (area, timestamp, etc.).
            doc_id: The FAISS document ID assigned to this memory.
            memory_subdir: Which memory subdirectory it was saved to.
        """
        try:
            # Lazy import to avoid hard dependency
            from graphrag_agent_zero.extension_hook import is_enabled
            from graphrag_agent_zero.neo4j_connector import is_neo4j_available
            from graphrag_agent_zero.extension_hook import get_builder
        except ImportError:
            # graphrag_agent_zero package not installed — nothing to do
            return

        # Gate 1: Feature flag
        if not is_enabled():
            return

        # Gate 2: Neo4j availability
        if not is_neo4j_available():
            return

        try:
            builder = get_builder()
            doc = {
                "id": doc_id,
                "content": text,
                "source": f"memory/{memory_subdir}",
                "title": (metadata or {}).get("title", doc_id),
            }
            success = builder.build_from_document(doc)
            if success:
                logger.debug(f"GraphRAG: indexed memory {doc_id} into Neo4j")
        except Exception as e:
            # Never crash the agent — log and move on
            logger.warning(f"GraphRAG sync failed for {doc_id} (non-fatal): {e}")
