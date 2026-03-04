"""
GraphRAG Deletion Sync Extension
Extension Point: memory_deleted_after
Location: /usr/extensions/memory_deleted_after/

Automatically deletes Neo4j graph nodes associated with a memory when 
it is deleted from the Agent Zero VectorDB.
"""

import logging
from python.helpers.extension import Extension

logger = logging.getLogger(__name__)

class GraphRAGDeleteExtension(Extension):
    """
    Deletes memory nodes from the Neo4j knowledge graph using their document IDs.
    Triggered by the memory_deleted_after hook in Memory.delete_documents_by_ids().
    """

    async def execute(self, ids=None, memory_subdir="", **kwargs):
        if not ids:
            return

        try:
            # Lazy import to avoid hard dependency
            from graphrag_agent_zero.extension_hook import is_enabled
            from graphrag_agent_zero.neo4j_connector import is_neo4j_available, get_connector
        except ImportError:
            return

        # Gate 1: Feature flag
        if not is_enabled():
            return

        # Gate 2: Neo4j availability
        if not is_neo4j_available():
            return

        try:
            connector = get_connector()
            for doc_id in ids:
                # We identify source based on memory_subdir where it was stored
                success = connector.delete_document(doc_id)
                if success:
                    logger.debug(f"GraphRAG: deleted memory {doc_id} from Neo4j")
        except Exception as e:
            # Never crash the agent — log and move on
            logger.warning(f"GraphRAG delete sync failed for {ids} (non-fatal): {e}")
