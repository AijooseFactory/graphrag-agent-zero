import os
import sys
import logging
import asyncio
import json

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "src"))

from graphrag_agent_zero.neo4j_connector import get_connector # noqa: E402
from graphrag_agent_zero.graph_builder import GraphBuilder # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("enrichment")

async def enrich_existing_graph():
    """
    Crawls existing Document nodes in Neo4j and extracts relationships 
    for those that are currently isolated (0 outgoing relationships).
    """
    # Use environment variables with sensible fallbacks
    os.environ["GRAPH_RAG_ENABLED"] = os.getenv("GRAPH_RAG_ENABLED", "true")
    os.environ["NEO4J_URI"] = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    os.environ["NEO4J_USER"] = os.getenv("NEO4J_USER", "neo4j")
    os.environ["NEO4J_PASSWORD"] = os.getenv("NEO4J_PASSWORD", "B@b@tund3!")
    os.environ["NEO4J_DATABASE"] = os.getenv("NEO4J_DATABASE", "graphrag-agent-zero-neo4j")

    connector = get_connector()
    builder = GraphBuilder(extract_llm=True)
    
    logger.info("Starting graph enrichment process...")
    
    # 1. Fetch documents
    # Using a safe query to get documents
    docs = connector.execute_template("get_all_documents", {"limit": 500})
    if not docs:
        logger.info("No documents found to enrich.")
        return

    logger.info(f"Found {len(docs)} document nodes. Loading content mapping...")
    
    mapping = {}
    try:
        with open("content_mapping.json", "r") as f:
            mapping = json.load(f)
        logger.info(f"Loaded {len(mapping)} content mappings from FAISS.")
    except Exception as e:
        logger.warning(f"Failed to load content_mapping.json: {e}")

    processed = 0
    enriched = 0
    
    for doc in docs:
        doc_id = doc.get("id")
        content = doc.get("content")
        title = doc.get("title")
        
        # Fallback to mapping if Neo4j content is missing
        if not content and doc_id in mapping:
            content = mapping[doc_id]
            
        if not content:
            logger.debug(f"Skipping {doc_id}: no content found in Neo4j or FAISS.")
            continue
            
        logger.info(f"[{processed+1}/{len(docs)}] Enriching document: {title or doc_id}")
        
        try:
            success = builder.build_from_document({
                "id": doc_id,
                "content": content,
                "title": title or doc_id,
                "source": "enrichment_backfill"
            })
            
            if success:
                enriched += 1
            
            processed += 1
            await asyncio.sleep(0.05) # Parallelism check: small delay
            
        except Exception as e:
            logger.error(f"Failed to enrich document {doc_id}: {e}")

    logger.info(f"Enrichment complete. Processed: {processed}, Enriched: {enriched}")
    
    # Show final stats
    stats = connector.execute_template("get_counts")
    rel_stats = connector.execute_template("get_rel_counts")
    logger.info(f"Final Node Counts: {stats}")
    logger.info(f"Final Relationship Counts: {rel_stats}")

if __name__ == "__main__":
    asyncio.run(enrich_existing_graph())
