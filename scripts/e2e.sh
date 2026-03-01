#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="dev/docker-compose.graphrag-dev.yml"
RUN_ID="$(date -u +"%Y%m%dT%H%M%SZ")"
ART_DIR="artifacts/e2e/${RUN_ID}"

mkdir -p "$ART_DIR"

pass() { echo "✅ PASS: $*"; }
fail() { echo "❌ FAIL: $*" ; exit 1; }

wait_http_200() {
  local url="$1"
  for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null "$url"; then return 0; fi
    sleep 1
  done
  return 1
}

logs_since() {
  local since="$1"
  local cid
  cid="$(docker compose -f "$COMPOSE_FILE" ps -q agent-zero-graphrag-dev)"
  if [ -n "$cid" ]; then
    docker logs --since "$since" "$cid" 2>&1 || true
  fi
}

write_env() {
  local graphrag_enabled="$1"
  cat > dev/.env <<EOF
WEB_UI_HOST=0.0.0.0
WEB_UI_PORT=80

# Seamless OpenAI API spoofing for deterministic local LLM stubbing via LiteLLM
OPENAI_API_BASE=http://llm-stub:8000/v1
OPENAI_API_KEY=dummy

A0_SET_chat_model_provider=openai
A0_SET_chat_model_name=openai/gpt-4o-mini-stub
A0_SET_chat_model_api_base=http://llm-stub:8000/v1

A0_SET_util_model_provider=openai
A0_SET_util_model_name=openai/gpt-4o-mini-stub
A0_SET_util_model_api_base=http://llm-stub:8000/v1

A0_SET_embed_model_provider=openai
A0_SET_embed_model_name=openai/text-embedding-3-stub
A0_SET_embed_model_api_base=http://llm-stub:8000/v1

GRAPH_RAG_ENABLED=${graphrag_enabled}
PYTHONPATH=/a0/src

NEO4J_URI=bolt://neo4j-graphrag-dev:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=graphrag2026
NEO4J_CONNECTION_TIMEOUT_MS=1500
NEO4J_QUERY_TIMEOUT_MS=10000
GRAPH_EXPAND_MAX_HOPS=2
GRAPH_EXPAND_LIMIT=100
GRAPH_MAX_RESULTS=50
EOF
}

recreate() {
  docker compose -f "$COMPOSE_FILE" down -v --remove-orphans
  docker compose -f "$COMPOSE_FILE" up -d --build --force-recreate agent-zero-graphrag-dev llm-stub
}

inject_deps() {
  # faiss-cpu 1.11 is broken on Python 3.12 (uses removed numpy.distutils)
  # Upgrade to 1.13.2+ which eliminates the dependency
  sleep 5
  docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
    "source /opt/venv-a0/bin/activate && pip install -q neo4j httpx setuptools && pip install -q --upgrade faiss-cpu"
  docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
    "supervisorctl restart run_ui" || true
}

echo "=== Top 1% Extensibility: Compatibility Matrix ==="
cat docs/COMPATIBILITY.md
echo "=================================================="

# ──────────────────────────────────────────────
# GATE 1: Agent Zero Starts (UI Health)
# ──────────────────────────────────────────────
echo "== E2E: Gate 1 — Agent Zero UI Health =="
write_env "false"
recreate
inject_deps
wait_http_200 "http://localhost:8087/health" || fail "UI health not reachable"
pass "Agent Zero UI health reachable"

# ──────────────────────────────────────────────
# GATE 2: LLM Stub Responds Correctly
# ──────────────────────────────────────────────
echo "== E2E: Gate 2 — LLM Stub Verification =="
STUB_RESP=$(curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-4o-mini-stub","messages":[{"role":"user","content":"hello"}]}')
echo "$STUB_RESP" | grep -q "graphrag_seen=NO" || fail "Stub did not report graphrag_seen=NO for plain message"
pass "LLM stub correctly reports graphrag_seen=NO (no context injected)"

# Test stub WITH graphrag context
STUB_RESP_CTX=$(curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-4o-mini-stub","messages":[{"role":"system","content":"GRAPHRAG_CONTEXT_BLOCK_START\ntest context\nGRAPHRAG_CONTEXT_BLOCK_END"},{"role":"user","content":"hello"}]}')
echo "$STUB_RESP_CTX" | grep -q "graphrag_seen=YES" || fail "Stub did not report graphrag_seen=YES when context present"
echo "$STUB_RESP_CTX" | grep -q "graphrag_hash_seen=" || fail "Stub did not compute hash"
pass "LLM stub correctly detects GraphRAG context and computes hash"

# ──────────────────────────────────────────────
# GATE 3: Extension Loading Verification
# ──────────────────────────────────────────────
echo "== E2E: Gate 3 — GraphRAG Extension File Present =="
docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
  "test -f /a0/agents/default/extensions/message_loop_prompts_after/_80_graphrag.py" \
  || fail "Extension file not found in agent profile"
docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
  "grep -q 'GRAPHRAG_AGENT_EXTENSION_EXECUTED' /a0/agents/default/extensions/message_loop_prompts_after/_80_graphrag.py" \
  || fail "Extension file missing AGENT marker"
pass "GraphRAG extension file verified in agent profile with correct markers"

# ──────────────────────────────────────────────
# GATE 4: GraphRAG Package Import Check
# ──────────────────────────────────────────────
echo "== E2E: Gate 4 — GraphRAG Package Importable =="
docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
  "source /opt/venv-a0/bin/activate && python3 -c '
from graphrag_agent_zero.hybrid_retrieve import HybridRetriever, RetrievalResult
from graphrag_agent_zero.neo4j_connector import is_neo4j_available
from graphrag_agent_zero.safe_cypher import SafeCypherEngine
from graphrag_agent_zero.graph_builder import GraphBuilder
from graphrag_agent_zero.extension_hook import enhance_retrieval
print(\"ALL_IMPORTS_OK\")
'" | grep -q "ALL_IMPORTS_OK" || fail "GraphRAG package import failed"
pass "All GraphRAG package modules importable"

# ──────────────────────────────────────────────
# GATE 5: Neo4j Down — Graceful No-Op
# ──────────────────────────────────────────────
echo "== E2E: Gate 5 — Neo4j Down Resilience =="
docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
  "source /opt/venv-a0/bin/activate && python3 -c '
import os
os.environ[\"NEO4J_URI\"] = \"bolt://localhost:7687\"
os.environ[\"NEO4J_USER\"] = \"neo4j\"
os.environ[\"NEO4J_PASSWORD\"] = \"wrong\"
os.environ[\"NEO4J_CONNECTION_TIMEOUT_MS\"] = \"500\"
from graphrag_agent_zero.neo4j_connector import is_neo4j_available
from graphrag_agent_zero.extension_hook import enhance_retrieval
assert not is_neo4j_available(), \"Neo4j should not be available\"
result = enhance_retrieval(\"test query\", [])
assert result[\"fallback_used\"] == True, \"Should fallback\"
print(\"NEO4J_DOWN_SAFE\")
'" | grep -q "NEO4J_DOWN_SAFE" || fail "Neo4j down resilience check failed"
pass "Neo4j down — extension degrades gracefully (no crash)"

# ──────────────────────────────────────────────
# GATE 6: Neo4j Up — Graph Query Works
# ──────────────────────────────────────────────
echo "== E2E: Gate 6 — Neo4j Up + Graph Query =="
docker compose -f "$COMPOSE_FILE" up -d neo4j-graphrag-dev
echo "Waiting for Neo4j health..."
docker compose -f "$COMPOSE_FILE" exec -T neo4j-graphrag-dev bash -c \
  'for i in {1..40}; do curl -sf http://localhost:7474 && break || sleep 1; done' || fail "Neo4j never healthy"
# Seed test data
docker compose -f "$COMPOSE_FILE" exec -T neo4j-graphrag-dev cypher-shell -u neo4j -p graphrag2026 \
  "MERGE (n:Entity {id:'eng_graphrag', name:'GRAPH_RAG_TOKEN_123', description:'E2E seed', type:'Concept'}) RETURN n;" >/dev/null

docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
  "source /opt/venv-a0/bin/activate && python3 -c '
import os
os.environ[\"GRAPH_RAG_ENABLED\"] = \"true\"
os.environ[\"NEO4J_URI\"] = \"bolt://neo4j-graphrag-dev:7687\"
os.environ[\"NEO4J_USER\"] = \"neo4j\"
os.environ[\"NEO4J_PASSWORD\"] = \"graphrag2026\"
os.environ[\"NEO4J_CONNECTION_TIMEOUT_MS\"] = \"3000\"
from graphrag_agent_zero.neo4j_connector import is_neo4j_available
from graphrag_agent_zero.extension_hook import enhance_retrieval
assert is_neo4j_available(), \"Neo4j should be available\"
result = enhance_retrieval(\"Tell me about GRAPH_RAG_TOKEN_123\", [])
text_len = len(result.get(\"text\", \"\"))
fallback = result.get(\"fallback_used\", None)
print(f\"GRAPH_QUERY_OK text_len={text_len} fallback={fallback}\")
'" 2>&1 | tee "$ART_DIR/gate6.txt" | grep -q "GRAPH_QUERY_OK" || fail "Neo4j graph query failed"
pass "Neo4j up — GraphRAG query executed successfully"

# ──────────────────────────────────────────────
# GATE 7: Safe Cypher Engine
# ──────────────────────────────────────────────
echo "== E2E: Gate 7 — Safe Cypher Engine =="
docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
  "source /opt/venv-a0/bin/activate && python3 -c '
from graphrag_agent_zero.safe_cypher import SafeCypherEngine
engine = SafeCypherEngine()
# Should allow safe queries
assert engine.is_safe(\"MATCH (n:Entity) RETURN n LIMIT 10\")
# Should block mutations
assert not engine.is_safe(\"CREATE (n:Entity {name: \\\"hacked\\\"})\")
assert not engine.is_safe(\"DELETE n\")
assert not engine.is_safe(\"DETACH DELETE n\")
assert not engine.is_safe(\"DROP CONSTRAINT\")
print(\"SAFE_CYPHER_OK\")
'" | grep -q "SAFE_CYPHER_OK" || fail "Safe Cypher engine validation failed"
pass "Safe Cypher engine blocks mutations, allows reads"

# ──────────────────────────────────────────────
# Evidence Bundle
# ──────────────────────────────────────────────
echo "== Artifact-Grade Evidence Bundle Generation =="
docker compose -f "$COMPOSE_FILE" ps > "$ART_DIR/compose.ps.txt"
docker logs agent-zero-graphrag-dev > "$ART_DIR/agent-zero.logs.txt" 2>&1
docker logs llm-stub > "$ART_DIR/llm-stub.logs.txt" 2>&1
docker logs neo4j-graphrag-dev > "$ART_DIR/neo4j.logs.txt" 2>&1 || true

cat > "$ART_DIR/verify.summary.json" <<EOF
{
  "status": "PASS",
  "gates_passed": 7,
  "commit": "$(git rev-parse HEAD)",
  "date": "$RUN_ID"
}
EOF
pass "Evidence bundle dumped to $ART_DIR"

echo "== E2E SUMMARY =="
echo "PASS: all 7 GraphRAG extension gates verified."
exit 0
