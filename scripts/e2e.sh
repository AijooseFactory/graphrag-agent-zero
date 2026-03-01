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

post_message() {
  local text="$1"
  docker cp scripts/trigger_agent.py agent-zero-graphrag-dev:/a0/trigger_agent.py
  docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c "source /opt/venv-a0/bin/activate && python /a0/trigger_agent.py \"$text\""
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

echo "=== Top 1% Extensibility: Compatibility Matrix ==="
cat docs/COMPATIBILITY.md
echo "=================================================="

echo "== E2E: Gate D (UI up) =="
write_env "false"
recreate
# Inject dependencies before hitting API — setuptools is needed for numpy.distutils compat (faiss-cpu on Python 3.12+)
sleep 5   # let supervisord initialize
docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c "source /opt/venv-a0/bin/activate && pip install -q neo4j httpx setuptools && pip install -q --upgrade faiss-cpu"
# Restart the app process so it picks up the new deps
docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c "supervisorctl restart run_ui" || true
wait_http_200 "http://localhost:8087/health" || fail "UI health not reachable"
pass "UI health reachable"

echo "== E2E: GraphRAG OFF (no injected context) =="
sleep 2
TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
RESP="$(post_message "E2E OFF check")"
echo "$RESP" | grep -q "graphrag_seen=NO" || fail "Stub did not report graphrag_seen=NO"
sleep 2

# Check extension precedence
if logs_since "$TS" | grep -q "GRAPHRAG_BASE_EXTENSION_EXECUTED"; then fail "Base extension fired instead of acting as baseline override."; fi
logs_since "$TS" | grep -q "GRAPHRAG_AGENT_EXTENSION_EXECUTED" || fail "Missing GRAPHRAG_AGENT_EXTENSION_EXECUTED"

# Check side-effect limits
if logs_since "$TS" | grep -q "GRAPHRAG_CONTEXT_INJECTED"; then fail "Unexpected injection while OFF"; fi
pass "GraphRAG OFF + Extension Precedence verified"

echo "== E2E: GraphRAG ON + Neo4j reachable (injected) =="
# Start neo4j
docker compose -f "$COMPOSE_FILE" up -d neo4j-graphrag-dev
echo "Waiting for neo4j health..."
docker compose -f "$COMPOSE_FILE" exec -T neo4j-graphrag-dev bash -c 'for i in {1..40}; do curl -f http://localhost:7474 && break || sleep 1; done'
# Seed data
docker compose -f "$COMPOSE_FILE" exec -T neo4j-graphrag-dev cypher-shell -u neo4j -p graphrag2026 \
  "MERGE (n:Entity {id:'eng_graphrag', name:'GRAPH_RAG_TOKEN_123', description:'E2E seed', type:'Concept'}) RETURN n;" >/dev/null

write_env "true"
recreate
# Inject dependencies again (container recreated)
sleep 5
docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c "source /opt/venv-a0/bin/activate && pip install -q neo4j httpx setuptools && pip install -q --upgrade faiss-cpu"
docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c "supervisorctl restart run_ui" || true

wait_http_200 "http://localhost:8087/health" || fail "UI health not reachable (ON)"
sleep 2
TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
RESP="$(post_message "Tell me about GRAPH_RAG_TOKEN_123")"
sleep 2

# Hook Integrity Check
logs_since "$TS" | grep -q "GRAPHRAG_HOOKPOINT=message_loop_prompts_after" || fail "Hook point marker missing"

# Validation
echo "$RESP" | grep -q "graphrag_seen=YES" || fail "Stub did not report graphrag_seen=YES"
logs_since "$TS" | grep -q "GRAPHRAG_CONTEXT_INJECTED" || fail "Missing GRAPHRAG_CONTEXT_INJECTED"

# Hash Round Trip verification
EXT_HASH=$(logs_since "$TS" | grep "GRAPHRAG_CONTEXT_SHA256=" | tail -1 | cut -d'=' -f2 | tr -d '\r')
if [ -z "$EXT_HASH" ]; then fail "Hash not computed by extension"; fi
echo "$RESP" | grep -q "graphrag_hash_seen=$EXT_HASH" || fail "Stub failed hash round-trip validation mismatch ($EXT_HASH)"

pass "GraphRAG ON Hash Round-Trip verified"

echo "== E2E: GraphRAG ON + Neo4j DOWN (no-op, no crash) =="
docker compose -f "$COMPOSE_FILE" stop neo4j-graphrag-dev
sleep 2
TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
RESP="$(post_message "Tell me about GRAPH_RAG_TOKEN_123 (neo4j down)")"
echo "$RESP" | grep -q "graphrag_seen=NO" || fail "Stub expected graphrag_seen=NO when neo4j down"
sleep 2
logs_since "$TS" | grep -q "GRAPHRAG_NOOP_NEO4J_DOWN" || fail "Missing GRAPHRAG_NOOP_NEO4J_DOWN"
pass "GraphRAG ON + Neo4j down verified"

echo "== E2E: Memory receipt save/retrieve =="
docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c "source /opt/venv-a0/bin/activate && python /a0/usr/e2e_memory_receipt.py" \
  || fail "Memory receipt check failed"
pass "Memory receipt verified"

echo "== Artifact-Grade Evidence Bundle Generation =="
docker compose -f "$COMPOSE_FILE" ps > "$ART_DIR/compose.ps.txt"
docker logs agent-zero-graphrag-dev > "$ART_DIR/agent-zero.logs.txt" 2>&1
docker logs llm-stub > "$ART_DIR/llm-stub.logs.txt" 2>&1
docker logs neo4j-graphrag-dev > "$ART_DIR/neo4j.logs.txt" 2>&1 || true

cat > "$ART_DIR/verify.summary.json" <<EOF
{
  "status": "PASS",
  "hash_validated": "$EXT_HASH",
  "commit": "$(git rev-parse HEAD)",
  "date": "$RUN_ID"
}
EOF
pass "Evidence bundle dumped to $ART_DIR"

echo "== E2E SUMMARY =="
echo "PASS: all 7 Agent Zero extension gate constraints satisfied."
exit 0
