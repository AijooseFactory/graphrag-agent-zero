import os
import sys
import argparse
import logging
import asyncio
from pathlib import Path

# Try to load dotenv, but handle gracefully if not present
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def find_agent_zero_root():
    """Attempt to find the Agent Zero root directory."""
    # Check current directory
    if os.path.exists("initialize.py") and os.path.exists("python/helpers/memory.py"):
        return os.getcwd()
    
    # Check if running inside standard docker container path
    if os.path.exists("/a0/initialize.py"):
        return "/a0"
        
    return None

async def verify_memory(present_ids=None, deleted_ids=None):
    print("=== Agent Zero Vector Memory - Ground Truth Verification ===\n")
    
    a0_root = find_agent_zero_root()
    if not a0_root:
        print("❌ Error: Could not locate Agent Zero root directory.")
        print("Please run this script from inside your Agent Zero folder, or securely within its Docker container.")
        sys.exit(1)
        
    if a0_root not in sys.path:
        sys.path.insert(0, a0_root)
        
    if load_dotenv:
        env_path = os.path.join(a0_root, ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
            
    print(f"✅ Found Agent Zero root at: {a0_root}")
    
    # Ground Truth context: show explicitly where settings/memory are loaded from
    usr_path = os.path.join(a0_root, "usr")
    if os.path.exists(usr_path):
        is_link = os.path.islink(usr_path)
        print(f"📊 Persistence Check: /usr directory found ({'Symlink' if is_link else 'Directory'})")
        print(f"   Storage Mode: { 'Named Volume/Bind Mount' if os.path.exists(os.path.join(usr_path, 'settings.json')) else 'Unknown'}")
    
    # Check Agent Zero Vector Memory (Standard Memory)
    print("\n--- Agent Zero Vector Memory Check ---")
    try:
        import initialize
        import python.helpers.memory as memory_mod
        Memory = memory_mod.Memory
        
        agent_config = initialize.initialize_agent()
        db, _ = Memory.initialize(None, agent_config.embeddings_model, "default", False)
        print("✅ Vector Memory index loaded successfully.")
        
        if present_ids:
            print(f"\nVerifying Presence of {len(present_ids)} Memory IDs in Vector Memory:")
            found_docs = db.get_by_ids(present_ids)
            found_ids = [doc.metadata.get('id') for doc in found_docs if doc is not None]
            
            for cid in present_ids:
                if cid in found_ids:
                    print(f"  ✅ VERIFIED PRESENT: {cid}")
                else:
                    print(f"  ❌ FAILED (MISSING): {cid}")
                    
        if deleted_ids:
            print(f"\nVerifying Deletion of {len(deleted_ids)} Memory IDs:")
            found_deleted = db.get_by_ids(deleted_ids)
            found_deleted_ids = [doc.metadata.get('id') for doc in found_deleted if doc is not None]
            
            all_clean = True
            for did in deleted_ids:
                if did in found_deleted_ids:
                    print(f"  ❌ FAILED (STILL EXISTS): {did}")
                    all_clean = False
            
            if all_clean:
                print(f"  ✅ VERIFIED DELETED: All {len(deleted_ids)} IDs are completely gone from Vector Memory.")
                
    except Exception as e:
        print(f"❌ Vector Memory check failed: {e}")

    # Check Neo4j
    print("\n--- Neo4j Knowledge Graph Check ---")
    try:
        import neo4j
        # We check os.environ to see if the user has Neo4j configured, fallback to .env defaults
        neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
        neo4j_pass = os.environ.get("NEO4J_PASSWORD")
        neo4j_db = os.environ.get("NEO4J_DATABASE", "neo4j")
        
        if not neo4j_pass:
            print("⚠️ NEO4J_PASSWORD is not set in environment or .env file.")
            print("To verify Neo4j, ensure your Agent Zero .env file contains database credentials.")
        else:
            driver = neo4j.GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pass))
            driver.verify_connectivity()
            print(f"✅ Successfully connected to Neo4j at {neo4j_uri} (Database: {neo4j_db})")
            
            if present_ids:
                print(f"\nVerifying Graph Entities and RRF Context for {len(present_ids)} IDs:")
                with driver.session(database=neo4j_db) as session:
                    for cid in present_ids:
                        # Check graph for exact ID matches
                        result = session.run("MATCH (n) WHERE n.name = $id OR n.id = $id RETURN n.type as type, head(labels(n)) as label LIMIT 1", id=cid)
                        record = result.single()
                        if record:
                            etype = record.get("type") or record.get("label") or "Entity"
                            print(f"  ✅ VERIFIED IN GRAPH: {cid} (Type: {etype})")
                            
                            # Check for document relationships (SPEP Protocol)
                            rel_result = session.run("MATCH (n)-[r:MENTIONS|CONTAINS|REFERENCES]-(d:Document) WHERE n.name = $id OR n.id = $id RETURN d.id as doc_id LIMIT 5", id=cid)
                            rels = [r["doc_id"] for r in rel_result]
                            if rels:
                                print(f"    🔗 Linked Documents (RRF Candidates): {', '.join(rels)}")
                        else:
                            print(f"  ❌ FAILED (MISSING IN GRAPH): {cid}")
            
            driver.close()
            
    except ImportError:
        print("❌ neo4j python package not installed. (Run: pip install neo4j)")
    except Exception as e:
        print(f"❌ Neo4j/RRF check failed: {e}")
        
    print("\n=== Verification Complete ===")

def main():
    parser = argparse.ArgumentParser(description="GraphRAG for Agent Zero - Generic Memory Verification Script")
    parser.add_argument("--present", type=str, help="Comma-separated list of Memory IDs that MUST be present.")
    parser.add_argument("--deleted", type=str, help="Comma-separated list of Memory IDs that MUST be deleted.")
    
    args = parser.parse_args()
    
    present_ids = [i.strip() for i in args.present.split(",")] if args.present else []
    deleted_ids = [i.strip() for i in args.deleted.split(",")] if args.deleted else []
    
    if not present_ids and not deleted_ids:
        print("Notice: No explicit IDs provided. Running general health check only.")
        print("Use --present ID1,ID2 or --deleted ID3,ID4 to check specific memories.\n")
        
    asyncio.run(verify_memory(present_ids, deleted_ids))

if __name__ == "__main__":
    main()
