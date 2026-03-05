#!/usr/bin/env python3
"""
GraphRAG for Agent Zero - Batch Indexing Utility (v0.2.0)

Crawls Agent Zero's memory corpus and bulk-indexes documents, 
entities, and relationships into Neo4j.
"""

import os
import sys
import logging
import argparse
from typing import Dict, Any

# Root addition for package imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from graphrag_agent_zero.graph_builder import GraphBuilder
    from graphrag_agent_zero.neo4j_connector import is_neo4j_available, get_connector
    from graphrag_agent_zero.logger import setup_logger
except ImportError as e:
    print(f"❌ Failed to import GraphRAG components: {e}")
    print("Ensure you have installed the package: pip install -e .")
    sys.exit(1)

# Configure logging
logger = setup_logger("graphrag_agent_zero.batch_index")

def run_batch_index(memory_path: str, force: bool = False):
    """Execute bulk indexing of the memory corpus."""
    print(f"\n🚀 Starting GraphRAG Batch Indexing")
    print(f"📂 Source: {memory_path}")
    
    if not os.path.isdir(memory_path):
        print(f"❌ Error: Memory path not found: {memory_path}")
        return

    if not is_neo4j_available():
        print("❌ Error: Neo4j is not available. Check your .env and Neo4j status.")
        return

    builder = GraphBuilder(extract_llm=True)
    stats = {"documents": 0, "entities": 0, "relationships": 0}
    
    # We focus on the 'corpus' subdirectory if it exists, otherwise the root
    corpus_path = os.path.join(memory_path, "corpus")
    if not os.path.exists(corpus_path):
        corpus_path = memory_path
        
    md_files = [f for f in os.listdir(corpus_path) if f.endswith(".md")]
    total = len(md_files)
    
    if total == 0:
        print("✅ No markdown memories found to index.")
        return

    print(f"found {total} documents. Starting ingestion...\n")

    for i, filename in enumerate(md_files):
        filepath = os.path.join(corpus_path, filename)
        doc_id = filename.replace(".md", "")
        
        # Simple progress bar
        progress = int((i + 1) / total * 100)
        print(f"[{progress:3}%] {i+1}/{total} | Processing: {doc_id}", end="\r")
        
        try:
            with open(filepath, "r") as f:
                content = f.read()
            
            doc = {
                "id": doc_id,
                "content": content,
                "source": filepath,
            }
            
            doc_stats = builder.build_from_document(doc)
            stats["documents"] += 1
            stats["entities"] += doc_stats.get("entities", 0)
            stats["relationships"] += doc_stats.get("relationships", 0)
        except Exception as e:
            print(f"\n⚠️ Failed to process {doc_id}: {e}")

    print("\n\n" + "="*40)
    print("📈 BATCH INDEXING COMPLETE")
    print("="*40)
    print(f"📄 Documents Processed:  {stats['documents']}")
    print(f"🏷️  Entities Created:   {stats['entities']}")
    print(f"🔗 Relationships Found: {stats['relationships']}")
    print("="*40)
    print("✅ Knowledge Graph is now up to date.\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GraphRAG Batch Indexing Utility")
    parser.add_argument("path", nargs="?", default="/a0/usr/memory/default", 
                        help="Path to Agent Zero memory directory (default: /a0/usr/memory/default)")
    parser.add_argument("--force", action="store_true", help="Force re-indexing of existing documents")
    
    args = parser.parse_args()
    
    # Path resolution for local vs docker
    path = args.path
    if not os.path.exists(path):
        # Universal fallback for Agent Zero memory locations
        fallback_paths = ["/a0/usr/memory/default", "/Mac/data/usr/memory/default"]
        for p in fallback_paths:
            if os.path.exists(p):
                path = p
                break
        
    run_batch_index(path, args.force)
