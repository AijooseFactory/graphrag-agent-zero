import asyncio
import os
import sys

# Ensure paths and load DOTENV FIRST before any GraphRAG/AgentZero imports!
sys.path.insert(0, '/a0/src')
sys.path.insert(0, '/a0')
import dotenv
dotenv.load_dotenv('/a0/.env', override=True)
os.environ["GRAPH_RAG_ENABLED"] = "true"

from python.helpers.memory import Memory
from graphrag_agent_zero.neo4j_connector import get_connector
from usr.extensions.agent_init._80_graphrag_patch import GraphRAGPatchExtension
import logging

logging.basicConfig(level=logging.ERROR)

async def main():
    print('--- Testing Memory Deletion Sync across ALL Databases ---')
    print('Applying GraphRAG agent_init hooks to inject patches...')
    patcher = GraphRAGPatchExtension(agent=None)
    await patcher.execute()
    
    mem = await Memory.get_by_subdir('default', preload_knowledge=False)
    
    # 1. Insert test memory
    text = 'GraphRAG deletion test token DO_NOT_IGNORE_777'
    print(f'> Inserting memory: "{text}"')
    doc_id = await mem.insert_text(text, metadata={'title': 'test deletion'})
    print(f'> Inserted into Agent Zero VectorDB with doc_id: {doc_id}')
    
    # Let graph sync process
    await asyncio.sleep(1)
    
    print(f"DEBUG: NEO4J_URI right before connector is {os.environ.get('NEO4J_URI')}")
    conn = get_connector()
    print(f"DEBUG: Connector uri is {conn.config.uri}")
    
    # 2. Verify in Neo4j
    # We can use get_entity_details directly on the doc_id as GraphBuilder creates an Entity with that ID
    res = conn.execute_template('get_entity_details', {'entity_ids': [doc_id], 'limit': 10})
    if res and len(res) > 0:
        print('✅ Verified: Memory node successfully synchronized to Neo4j.')
    else:
        print('❌ Failed: Memory node not found in Neo4j after insert!')
        return
        
    # 3. Delete memory
    print(f'> Deleting memory {doc_id} from Agent Zero VectorDB...')
    await mem.delete_documents_by_ids([doc_id])
    
    # Let graph sync process
    await asyncio.sleep(1)
    
    # 4. Verify deleted in Neo4j
    res_after = conn.execute_template('get_entity_details', {'entity_ids': [doc_id], 'limit': 10})
    if not res_after or len(res_after) == 0:
        print('✅ Verified: Memory node CLEANLY DELETED from Neo4j automatically via extension hook!')
    else:
        print('❌ Failed: Memory node still exists in Neo4j after deletion!')
        return
        
    print("\nSUCCESS: All memory deletion synchronization tests passed!")

if __name__ == "__main__":
    asyncio.run(main())
