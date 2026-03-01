from __future__ import annotations

import hashlib
import json
import time
import re
import os
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Union

app = FastAPI()
MEMORY_SENTINEL_PATTERN = re.compile(r"HYBRID_MEMORY_SENTINEL=[A-Za-z0-9._:-]+")


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


def _join_message_content(messages: List[ChatMsg]) -> str:
    return "\n".join([str(m.content) for m in messages if m.content is not None])


def _extract_memories_block(blob: str) -> str:
    start = blob.find("# Memories on the topic")
    if start == -1:
        return ""
    end = blob.find("\n# ", start + 1)
    if end == -1:
        return blob[start:]
    return blob[start:end]


def _get_memory_sentinel(messages: List[ChatMsg]) -> Optional[str]:
    blob = _join_message_content(messages)
    direct = MEMORY_SENTINEL_PATTERN.search(blob)
    if direct:
        return direct.group(0)

    memories_block = _extract_memories_block(blob)
    if not memories_block:
        return None
    match = MEMORY_SENTINEL_PATTERN.search(memories_block)
    return match.group(0) if match else None


def _conversation_signature(messages: List[ChatMsg]) -> str:
    joined = "\n".join([f"{m.role}:{m.content}" for m in messages if m.content is not None])
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


def _get_graphrag_hash_from_text(blob: str) -> Optional[str]:
    start = blob.find("GRAPHRAG_CONTEXT_BLOCK_START")
    end = blob.find("GRAPHRAG_CONTEXT_BLOCK_END")
    if start != -1 and end != -1:
        block = blob[start:end + len("GRAPHRAG_CONTEXT_BLOCK_END")]
        return hashlib.sha256(block.encode("utf-8")).hexdigest()
    return None


def _build_agent_zero_response_text(
    graphrag_seen: bool,
    ctx_hash: Optional[str],
    memory_seen: bool,
    memory_sentinel: Optional[str],
    echo: str,
) -> str:
    # Agent Zero expects the model output to be a JSON tool call.
    payload = {
        "thoughts": ["Returning deterministic stub response payload."],
        "headline": "Returning final response to user",
        "tool_name": "response",
        "tool_args": {
            "text": (
                f"[stub-ollama] memory_seen={'YES' if memory_seen else 'NO'} "
                f"| memory_sentinel={memory_sentinel or 'None'} "
                f"| graphrag_seen={'YES' if graphrag_seen else 'NO'} "
                f"| graphrag_hash_seen={ctx_hash or 'None'} "
                f"| echo={echo}"
            )
        },
    }
    return json.dumps(payload, ensure_ascii=False)


@app.post("/v1/chat/completions")
def chat_completions(req: ChatReq) -> Dict[str, Any]:
    blob = _join_message_content(req.messages)
    user_text = ""
    for m in reversed(req.messages):
        if m.role == "user":
            user_text = str(m.content)
            break

    if os.getenv("LLM_STUB_DUMP_PROMPT", "").lower() in {"1", "true", "yes", "on"}:
        try:
            with open("/tmp/llm_stub_last_prompt.txt", "w", encoding="utf-8") as f:
                f.write(blob)
            with open("/tmp/llm_stub_prompts.jsonl", "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "ts": int(time.time()),
                            "model": req.model,
                            "user_text": user_text[:400],
                            "has_memory_sentinel": bool(MEMORY_SENTINEL_PATTERN.search(blob)),
                            "has_graphrag_block": "GRAPHRAG_CONTEXT_BLOCK_START" in blob,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except Exception:
            pass

    ctx_hash = _get_graphrag_hash(req.messages)
    graphrag_seen = ctx_hash is not None
    memory_sentinel = _get_memory_sentinel(req.messages)
    memory_seen = memory_sentinel is not None
    conv_sig = _conversation_signature(req.messages)

    content = _build_agent_zero_response_text(
        graphrag_seen=graphrag_seen,
        ctx_hash=ctx_hash,
        memory_seen=memory_seen,
        memory_sentinel=memory_sentinel,
        echo=f"{user_text[:120]} | sig={conv_sig}",
    )

    if req.stream:
        created = int(time.time())

        def _iter_sse():
            role_chunk = {
                "id": "chatcmpl-stub",
                "object": "chat.completion.chunk",
                "created": created,
                "model": req.model,
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(role_chunk, ensure_ascii=False)}\n\n"

            content_chunk = {
                "id": "chatcmpl-stub",
                "object": "chat.completion.chunk",
                "created": created,
                "model": req.model,
                "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(content_chunk, ensure_ascii=False)}\n\n"

            done_chunk = {
                "id": "chatcmpl-stub",
                "object": "chat.completion.chunk",
                "created": created,
                "model": req.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(done_chunk, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(_iter_sse(), media_type="text/event-stream")

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

# --- Ollama Compatibility ---

class OllamaChatReq(BaseModel):
    model: str
    messages: List[ChatMsg]
    stream: Optional[bool] = False

class OllamaEmbedReq(BaseModel):
    model: str
    prompt: Optional[str] = None
    input: Optional[Union[str, List[str]]] = None


@app.post("/api/chat")
@app.post("/v1/api/chat")
def ollama_chat(req: OllamaChatReq) -> Dict[str, Any]:
    ctx_hash = _get_graphrag_hash(req.messages)
    graphrag_seen = ctx_hash is not None
    memory_sentinel = _get_memory_sentinel(req.messages)
    memory_seen = memory_sentinel is not None
    conv_sig = _conversation_signature(req.messages)
    user_text = ""
    for m in reversed(req.messages):
        if m.role == "user":
            user_text = str(m.content)
            break
    content = _build_agent_zero_response_text(
        graphrag_seen=graphrag_seen,
        ctx_hash=ctx_hash,
        memory_seen=memory_seen,
        memory_sentinel=memory_sentinel,
        echo=f"{user_text[:120]} | sig={conv_sig}",
    )
    return {
        "model": req.model,
        "created_at": "2024-01-01T00:00:00Z",
        "message": {"role": "assistant", "content": content},
        "done": True
    }

@app.post("/api/embeddings")
@app.post("/api/embed")
@app.post("/v1/api/embeddings")
@app.post("/v1/api/embed")
def ollama_embeddings(req: OllamaEmbedReq) -> Dict[str, Any]:
    prompt_input = req.input or req.prompt or ""
    inputs = prompt_input if isinstance(prompt_input, list) else [prompt_input]
    embeddings_list = []
    for text in inputs:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = [(b / 255.0) for b in h[:16]]
        embeddings_list.append(vec)
    
    # Ollama /api/embeddings returns "embedding" (single) or "embeddings" (list)
    # Ollama /api/embed returns "embeddings" (list)
    return {
        "model": req.model,
        "embeddings": embeddings_list,
        "embedding": embeddings_list[0] if embeddings_list else []
    }

@app.get("/api/tags")
def ollama_tags():
    return {
        "models": [
            {"name": "qwen3-embedding:8b", "model": "qwen3-embedding:8b", "details": {"family": "llama"}},
            {"name": "glm-5:cloud", "model": "glm-5:cloud", "details": {"family": "chat"}}
        ]
    }


@app.post("/api/generate")
@app.post("/v1/api/generate")
async def ollama_generate(request: Request):
    payload = await request.json()
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {"prompt": payload}

    model = str(payload.get("model", "stub-ollama-generate"))
    prompt = str(payload.get("prompt", ""))
    stream = bool(payload.get("stream", False))

    ctx_hash = _get_graphrag_hash_from_text(prompt)
    graphrag_seen = ctx_hash is not None
    memory_match = MEMORY_SENTINEL_PATTERN.search(_extract_memories_block(prompt))
    memory_sentinel = memory_match.group(0) if memory_match else None
    memory_seen = memory_sentinel is not None
    prompt_sig = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12] if prompt else "none"
    content = _build_agent_zero_response_text(
        graphrag_seen=graphrag_seen,
        ctx_hash=ctx_hash,
        memory_seen=memory_seen,
        memory_sentinel=memory_sentinel,
        echo=f"{prompt[:120]} | sig={prompt_sig}",
    )

    if stream:
        def _iter():
            yield json.dumps(
                {"model": model, "response": content, "done": False},
                ensure_ascii=False,
            ) + "\n"
            yield json.dumps(
                {"model": model, "response": "", "done": True},
                ensure_ascii=False,
            ) + "\n"

        return StreamingResponse(_iter(), media_type="application/x-ndjson")

    return {
        "model": model,
        "response": content,
        "done": True,
    }
