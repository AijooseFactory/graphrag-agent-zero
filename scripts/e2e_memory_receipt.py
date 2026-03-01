import asyncio
from python.helpers.memory import Memory
from python.helpers.print_style import PrintStyle
from agent import Agent  # Agent exists in container runtime

RECEIPT = "GRAPH_RAG_SELF_RECEIPT"

async def main():
    # Create a minimal agent via initialize path
    import initialize
    agent = initialize.initialize_agent0()

    mem = await Memory.get(agent)
    _id = await mem.insert_text(RECEIPT, metadata={"area": Memory.Area.SOLUTIONS.value})
    PrintStyle.standard(f"receipt_saved id={_id}")

    hits = await mem.search_similarity_threshold(
        query=RECEIPT,
        limit=3,
        threshold=0.0,
        filter=f"area == '{Memory.Area.SOLUTIONS.value}'",
    )
    ok = any(RECEIPT in h.page_content for h in hits)
    if not ok:
        raise SystemExit("receipt_not_found")
    PrintStyle.standard("receipt_retrieved OK")

if __name__ == "__main__":
    asyncio.run(main())
