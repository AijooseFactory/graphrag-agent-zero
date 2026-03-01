from python.helpers.extension import Extension

class GraphRAGBaselineExtension(Extension):
    """
    Dummy baseline extension to prove Agent Zero override precedence.
    This file resides in the base 'python/extensions' folder.
    The real extension in 'agents/default/extensions' with the same name overrides it.
    """
    async def execute(self, loop_data=None, **kwargs):
        print("GRAPHRAG_BASE_EXTENSION_EXECUTED", flush=True)
