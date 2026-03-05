import pickle
import os
import json
from typing import Dict

# Ensure we can import from langchain_core inside the container
try:
    from langchain_core.documents import Document
except ImportError:
    # Fallback/Mock if running outside for some reason
    class Document:
        pass

def extract_metadata_content(pkl_path: str) -> Dict[str, str]:
    """
    Extracts doc_id -> content mapping from index.pkl
    """
    if not os.path.exists(pkl_path):
        return {}
    
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    
    # Langchain FAISS usually pickles a tuple (docstore, index_to_id)
    # where docstore is an InMemoryDocstore
    docstore = data[0] if isinstance(data, (tuple, list)) else data
    
    # InMemoryDocstore has a _dict attribute
    docs_dict = getattr(docstore, "_dict", {})
    
    mapping = {}
    for internal_id, doc in docs_dict.items():
        doc_id = doc.metadata.get("id") or doc.metadata.get("doc_id")
        if doc_id:
            mapping[doc_id] = doc.page_content
            
    return mapping

if __name__ == "__main__":
    path = "/a0/usr/memory/default/index.pkl"
    if not os.path.exists(path):
        # Universal fallback for Agent Zero index location
        fallback_paths = ["/a0/usr/memory/default/index.pkl", "/Mac/data/usr/memory/default/index.pkl"]
        for p in fallback_paths:
            if os.path.exists(p):
                path = p
                break
        
    result = extract_metadata_content(path)
    # Print as JSON for easy capture by shell
    print(json.dumps(result))
