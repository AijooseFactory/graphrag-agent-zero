from __future__ import annotations

import hashlib
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Union

app = FastAPI()


class ChatMsg(BaseModel):
    role: str
    content: Any


class ChatReq(BaseModel):
    model: str
    messages: List[ChatMsg]
    stream: Optional[bool] = False


class EmbedReq(BaseModel):
    model: str
    input: Union[str, List[str]]


def _get_graphrag_hash(messages: List[ChatMsg]) -> Optional[str]:
    blob = "\n".join([str(m.content) for m in messages if m.content is not None])
    start = blob.find("GRAPHRAG_CONTEXT_BLOCK_START")
    end = blob.find("GRAPHRAG_CONTEXT_BLOCK_END")
    if start != -1 and end != -1:
        block = blob[start:end + len("GRAPHRAG_CONTEXT_BLOCK_END")]
        return hashlib.sha256(block.encode("utf-8")).hexdigest()
    return None


@app.post("/v1/chat/completions")
def chat_completions(req: ChatReq) -> Dict[str, Any]:
    ctx_hash = _get_graphrag_hash(req.messages)
    seen = ctx_hash is not None
    user_text = ""
    for m in reversed(req.messages):
        if m.role == "user":
            user_text = str(m.content)
            break

    content = f"[stub] graphrag_seen={'YES' if seen else 'NO'} | graphrag_hash_seen={ctx_hash or 'None'} | echo={user_text[:120]}"
    return {
        "id": "chatcmpl-stub",
        "object": "chat.completion",
        "created": 0,
        "model": req.model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
    }


@app.post("/v1/embeddings")
def embeddings(req: EmbedReq) -> Dict[str, Any]:
    inputs = req.input if isinstance(req.input, list) else [req.input]
    data = []
    for i, text in enumerate(inputs):
        h = hashlib.sha256(text.encode("utf-8")).digest()
        # 16-dim deterministic vector
        vec = [(b / 255.0) for b in h[:16]]
        data.append({"object": "embedding", "index": i, "embedding": vec})
    return {"object": "list", "model": req.model, "data": data}

@app.get("/v1/models")
def get_models() -> Dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {"id": "gpt-4o-mini-stub", "object": "model", "created": 1686935002, "owned_by": "openai"},
            {"id": "text-embedding-3-stub", "object": "model", "created": 1686935002, "owned_by": "openai"}
        ]
    }
