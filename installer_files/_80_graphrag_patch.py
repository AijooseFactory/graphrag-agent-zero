"""
GraphRAG EPHEMERAL PATCH EXTENSION
Extension Point: agent_init
Location: /usr/extensions/agent_init/

Dynamically monkey-patches the core `Memory.insert_text` and `Memory.delete_documents_by_ids`
methods at runtime during Agent Zero startup. 
This elegantly allows emitting `memory_saved_after` and `memory_deleted_after` hooks 
without permanently modifying `/a0/python/helpers/memory.py` preventing data-loss 
during docker container recreations.
"""

import logging
from python.helpers.extension import Extension

logger = logging.getLogger("graphrag_patch")

_patched = False

class GraphRAGPatchExtension(Extension):
    async def execute(self, **kwargs):
        global _patched
        if _patched:
            return

        try:
            from python.helpers.memory import Memory
            from python.helpers.extension import call_extensions
            
            # --- PATCH insert_text ---
            original_insert_text = Memory.insert_text

            async def patched_insert_text(self_mem, text, metadata=None):
                # Call original method
                doc_id = await original_insert_text(self_mem, text, metadata)
                
                # Fire memory_saved_after hook
                try:
                    await call_extensions(
                        "memory_saved_after",
                        agent=getattr(self_mem, "agent", None),
                        text=text,
                        metadata=metadata or {},
                        doc_id=doc_id,
                        memory_subdir=self_mem.memory_subdir,
                    )
                except Exception as e:
                    logger.warning(f"GraphRAG memory_saved_after hook failed: {e}")
                    
                return doc_id

            Memory.insert_text = patched_insert_text
            
            # --- PATCH delete_documents_by_ids ---
            original_delete_documents_by_ids = Memory.delete_documents_by_ids

            async def patched_delete_documents_by_ids(self_mem, ids):
                # Call original method
                rem_docs = await original_delete_documents_by_ids(self_mem, ids)
                
                # Fire memory_deleted_after hook
                try:
                    await call_extensions(
                        "memory_deleted_after",
                        agent=getattr(self_mem, "agent", None),
                        ids=ids,
                        memory_subdir=self_mem.memory_subdir,
                    )
                except Exception as e:
                    logger.warning(f"GraphRAG memory_deleted_after hook failed: {e}")
                    
                return rem_docs

            Memory.delete_documents_by_ids = patched_delete_documents_by_ids
            
            # --- PATCH models._merge_provider_defaults ---
            # Automatically allocate enough context window for local Ollama models 
            # to handle the GraphRAG memory injections, without requiring user config edits.
            try:
                import sys
                models_mod = sys.modules.get('models')
                if models_mod and hasattr(models_mod, '_merge_provider_defaults'):
                    original_merge_provider_defaults = models_mod._merge_provider_defaults

                    def patched_merge_provider_defaults(provider_type, original_provider, kwargs):
                        provider_name, new_kwargs = original_merge_provider_defaults(provider_type, original_provider, kwargs)
                        if provider_name and isinstance(provider_name, str) and provider_name.lower() == "ollama":
                            if "num_ctx" not in new_kwargs:
                                new_kwargs["num_ctx"] = 8192
                        return provider_name, new_kwargs

                    models_mod._merge_provider_defaults = patched_merge_provider_defaults
                    logger.info("GraphRAG dynamically patched Ollama models for improved context length.")
            except Exception as e:
                logger.warning(f"GraphRAG failed to patch models for context length: {e}")
            
            _patched = True
            logger.info("GraphRAG dynamically patched Agent Zero successfully.")
            
        except Exception as e:
            logger.error(f"Failed to patch Memory for GraphRAG hooks: {e}")

