#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="dev/docker-compose.graphrag-dev.yml"
RUN_ID="$(date -u +"%Y%m%dT%H%M%SZ")"
ART_DIR="artifacts/e2e/${RUN_ID}"
DEV_ENV_FILE="dev/.env"
DEV_ENV_BACKUP="$(mktemp "/tmp/graphrag-dev-env.${RUN_ID}.XXXXXX")"
DEV_ENV_HAD_FILE="false"
RUNTIME_SETTINGS_BACKUP="$(mktemp "/tmp/graphrag-settings.${RUN_ID}.XXXXXX")"
RUNTIME_SETTINGS_BACKED_UP="false"

NEO4J_TARGET_URI="bolt://host.docker.internal:7687"
NEO4J_TARGET_USER="neo4j"
NEO4J_TARGET_PASSWORD=""
NEO4J_TARGET_DATABASE="neo4j"
NEO4J_TARGET_SOURCE="detected_endpoint"
NEO4J_FALLBACK_PASSWORD="graphrag2026"

mkdir -p "$ART_DIR"

if [ -f "$DEV_ENV_FILE" ]; then
  cp "$DEV_ENV_FILE" "$DEV_ENV_BACKUP"
  DEV_ENV_HAD_FILE="true"
fi

restore_dev_env() {
  if [ "$DEV_ENV_HAD_FILE" = "true" ]; then
    cp "$DEV_ENV_BACKUP" "$DEV_ENV_FILE"
  else
    rm -f "$DEV_ENV_FILE"
  fi
  rm -f "$DEV_ENV_BACKUP"
}

container_running() {
  docker ps --format '{{.Names}}' | grep -Fxq "agent-zero-graphrag-dev"
}

backup_runtime_settings() {
  if container_running && docker cp \
    agent-zero-graphrag-dev:/a0/usr/settings.json "$RUNTIME_SETTINGS_BACKUP" >/dev/null 2>&1; then
    RUNTIME_SETTINGS_BACKED_UP="true"
    echo "Backed up /a0/usr/settings.json before E2E run."
    return 0
  fi

  echo "WARNING: Could not backup /a0/usr/settings.json before E2E run."
}

restore_runtime_settings() {
  if [ "$RUNTIME_SETTINGS_BACKED_UP" != "true" ]; then
    rm -f "$RUNTIME_SETTINGS_BACKUP"
    return 0
  fi

  if ! container_running; then
    echo "WARNING: agent-zero-graphrag-dev not running; skipping settings restore."
    rm -f "$RUNTIME_SETTINGS_BACKUP"
    return 0
  fi

  if docker cp "$RUNTIME_SETTINGS_BACKUP" agent-zero-graphrag-dev:/a0/usr/settings.json >/dev/null 2>&1; then
    docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
      "supervisorctl restart run_ui >/dev/null 2>&1 || true" || true
    echo "Restored /a0/usr/settings.json after E2E run."
  else
    echo "WARNING: Failed to restore /a0/usr/settings.json after E2E run."
  fi

  rm -f "$RUNTIME_SETTINGS_BACKUP"
}

cleanup() {
  restore_dev_env
  restore_runtime_settings
}
trap cleanup EXIT

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

get_root_env_value() {
  local key="$1"
  if [ ! -f .env ]; then
    return 1
  fi
  grep -m1 "^${key}=" .env | cut -d= -f2-
}

ensure_neo4j_driver() {
  if docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
    'source /opt/venv-a0/bin/activate && python3 - <<PY
import importlib.util, sys
sys.exit(0 if importlib.util.find_spec("neo4j") else 1)
PY'; then
    echo "Neo4j python driver already installed in runtime venv."
  else
    docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
      "source /opt/venv-a0/bin/activate && pip install -q neo4j"
  fi
}

neo4j_available_from_agent() {
  local uri="$1"
  local user="$2"
  local password="$3"
  local database="$4"

  docker compose -f "$COMPOSE_FILE" exec -T \
    -e TEST_NEO4J_URI="$uri" \
    -e TEST_NEO4J_USER="$user" \
    -e TEST_NEO4J_PASSWORD="$password" \
    -e TEST_NEO4J_DATABASE="$database" \
    agent-zero-graphrag-dev bash -c 'source /opt/venv-a0/bin/activate && python3 - <<"PY"
import os
import sys
from neo4j import GraphDatabase

uri = os.environ["TEST_NEO4J_URI"]
user = os.environ["TEST_NEO4J_USER"]
password = os.environ["TEST_NEO4J_PASSWORD"]
database = os.environ.get("TEST_NEO4J_DATABASE", "neo4j")

try:
    drv = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=3)
    with drv.session(database=database) as session:
        session.run("RETURN 1 AS ok").single()
    drv.close()
except Exception:
    sys.exit(1)

sys.exit(0)
PY' >/dev/null 2>&1
}

wait_neo4j_ready() {
  local uri="$1"
  local user="$2"
  local password="$3"
  local database="$4"

  for _ in $(seq 1 60); do
    if neo4j_available_from_agent "$uri" "$user" "$password" "$database"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

seed_neo4j_test_data() {
  local uri="$1"
  local user="$2"
  local password="$3"
  local database="$4"

  docker compose -f "$COMPOSE_FILE" exec -T \
    -e TEST_NEO4J_URI="$uri" \
    -e TEST_NEO4J_USER="$user" \
    -e TEST_NEO4J_PASSWORD="$password" \
    -e TEST_NEO4J_DATABASE="$database" \
    agent-zero-graphrag-dev bash -c 'source /opt/venv-a0/bin/activate && python3 - <<"PY"
import os
from neo4j import GraphDatabase

uri = os.environ["TEST_NEO4J_URI"]
user = os.environ["TEST_NEO4J_USER"]
password = os.environ["TEST_NEO4J_PASSWORD"]
database = os.environ.get("TEST_NEO4J_DATABASE", "neo4j")

drv = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=5)
with drv.session(database=database) as session:
    session.run("MERGE (n:Entity {id:$id, name:$name, description:$desc, type:$type})", {
        "id": "eng_graphrag",
        "name": "GRAPH_RAG_TOKEN_123",
        "desc": "E2E seed",
        "type": "Concept",
    })
drv.close()
print("NEO4J_SEED_OK")
PY' | grep -q "NEO4J_SEED_OK"
}

select_neo4j_target() {
  local desktop_uri desktop_user desktop_password desktop_database
  desktop_uri="$(get_root_env_value "NEO4J_URI" || true)"
  desktop_user="$(get_root_env_value "NEO4J_USER" || true)"
  desktop_password="$(get_root_env_value "NEO4J_PASSWORD" || true)"
  desktop_database="$(get_root_env_value "NEO4J_DATABASE" || true)"

  [ -n "$desktop_uri" ] || desktop_uri="bolt://host.docker.internal:7687"
  [ -n "$desktop_user" ] || desktop_user="neo4j"
  [ -n "$desktop_password" ] || desktop_password="$(grep -m1 '^NEO4J_PASSWORD=' "$DEV_ENV_FILE" | cut -d= -f2- || true)"
  [ -n "$desktop_database" ] || desktop_database="neo4j"
  [ -n "$desktop_password" ] || fail "No Neo4j password configured. Set NEO4J_PASSWORD in .env or dev/.env."

  NEO4J_TARGET_URI="$desktop_uri"
  NEO4J_TARGET_USER="$desktop_user"
  NEO4J_TARGET_PASSWORD="$desktop_password"
  NEO4J_TARGET_DATABASE="$desktop_database"
  NEO4J_TARGET_SOURCE="detected_endpoint"

  if neo4j_available_from_agent "$NEO4J_TARGET_URI" "$NEO4J_TARGET_USER" "$NEO4J_TARGET_PASSWORD" "$NEO4J_TARGET_DATABASE"; then
    echo "Neo4j target selected: existing endpoint (${NEO4J_TARGET_URI})."
    return 0
  fi

  echo "No reachable external Neo4j endpoint at ${NEO4J_TARGET_URI}; starting embedded Neo4j in agent-zero-graphrag-dev."
  install_and_start_embedded_neo4j

  NEO4J_TARGET_URI="bolt://localhost:7687"
  NEO4J_TARGET_USER="neo4j"
  NEO4J_TARGET_PASSWORD="$NEO4J_FALLBACK_PASSWORD"
  NEO4J_TARGET_DATABASE="neo4j"
  NEO4J_TARGET_SOURCE="embedded_same_container"

  wait_neo4j_ready "$NEO4J_TARGET_URI" "$NEO4J_TARGET_USER" "$NEO4J_TARGET_PASSWORD" "$NEO4J_TARGET_DATABASE" \
    || fail "Embedded Neo4j failed to become healthy in agent-zero-graphrag-dev."

  echo "Neo4j target selected: embedded same-container endpoint (${NEO4J_TARGET_URI})."
}

install_and_start_embedded_neo4j() {
  docker compose -f "$COMPOSE_FILE" exec -T \
    -e NEO4J_PASS="$NEO4J_FALLBACK_PASSWORD" \
    agent-zero-graphrag-dev bash -lc 'set -euo pipefail
if ! command -v java >/dev/null 2>&1; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openjdk-21-jre-headless curl >/dev/null
fi

if [ ! -x /opt/neo4j/bin/neo4j ]; then
  cd /opt
  curl -fsSL https://dist.neo4j.org/neo4j-community-5.17.0-unix.tar.gz -o neo4j-community-5.17.0-unix.tar.gz
  tar -xzf neo4j-community-5.17.0-unix.tar.gz
  ln -sfn /opt/neo4j-community-5.17.0 /opt/neo4j
fi

mkdir -p /a0/usr/neo4j/data /a0/usr/neo4j/logs /a0/usr/neo4j/run
cat > /opt/neo4j/conf/neo4j.conf <<CONF
server.default_listen_address=0.0.0.0
server.bolt.listen_address=:7687
server.http.listen_address=:7474
server.memory.heap.initial_size=256m
server.memory.heap.max_size=512m
server.directories.data=/a0/usr/neo4j/data
server.directories.logs=/a0/usr/neo4j/logs
server.directories.run=/a0/usr/neo4j/run
dbms.security.auth_enabled=true
CONF

/opt/neo4j/bin/neo4j stop >/dev/null 2>&1 || true
NEO4J_AUTH="neo4j/${NEO4J_PASS}" /opt/neo4j/bin/neo4j start >/dev/null
'
}

write_env() {
  local graphrag_enabled="$1"
  local neo4j_uri="$2"
  local neo4j_user="$3"
  local neo4j_password="$4"
  local neo4j_database="$5"

  cat > "$DEV_ENV_FILE" <<EOF_ENV
WEB_UI_HOST=0.0.0.0
WEB_UI_PORT=80

# Embedded local LLM stub runs in the same container
OPENAI_API_BASE=http://127.0.0.1:8000/v1
OPENAI_API_KEY=dummy

A0_SET_chat_model_provider=openai
A0_SET_chat_model_name=openai/gpt-4o-mini-stub
A0_SET_chat_model_api_base=http://127.0.0.1:8000/v1

A0_SET_util_model_provider=openai
A0_SET_util_model_name=openai/gpt-4o-mini-stub
A0_SET_util_model_api_base=http://127.0.0.1:8000/v1

A0_SET_embed_model_provider=openai
A0_SET_embed_model_name=openai/text-embedding-3-stub
A0_SET_embed_model_api_base=http://127.0.0.1:8000/v1

A0_SET_browser_model_provider=openai
A0_SET_browser_model_name=openai/gpt-4o-mini-stub
A0_SET_browser_model_api_base=http://127.0.0.1:8000/v1

GRAPH_RAG_ENABLED=${graphrag_enabled}
PYTHONPATH=/a0/src

NEO4J_URI=${neo4j_uri}
NEO4J_USER=${neo4j_user}
NEO4J_PASSWORD=${neo4j_password}
NEO4J_DATABASE=${neo4j_database}
NEO4J_CONNECTION_TIMEOUT_MS=1500
NEO4J_QUERY_TIMEOUT_MS=10000
GRAPH_EXPAND_MAX_HOPS=2
GRAPH_EXPAND_LIMIT=100
GRAPH_MAX_RESULTS=50
EOF_ENV
}

recreate() {
  docker compose -f "$COMPOSE_FILE" down --remove-orphans
  docker compose -f "$COMPOSE_FILE" up -d --build --force-recreate agent-zero-graphrag-dev
}

inject_deps() {
  sleep 5
  ensure_neo4j_driver
  docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
    "source /opt/venv-a0/bin/activate && pip install -q httpx setuptools && pip install -q --upgrade faiss-cpu"
  docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
    "supervisorctl restart run_ui run_llm_stub" || true
}

echo "=== Top 1% Extensibility: Compatibility Matrix ==="
cat docs/COMPATIBILITY.md
echo "=================================================="
backup_runtime_settings

# GATE 1
echo "== E2E: Gate 1 — Agent Zero UI Health =="
write_env "false" "$NEO4J_TARGET_URI" "$NEO4J_TARGET_USER" "${NEO4J_TARGET_PASSWORD:-dummy}" "$NEO4J_TARGET_DATABASE"
recreate
inject_deps
wait_http_200 "http://localhost:8087/health" || fail "UI health not reachable"
pass "Agent Zero UI health reachable"

# GATE 2
echo "== E2E: Gate 2 — Embedded LLM Stub Verification =="
wait_http_200 "http://localhost:8000/v1/models" || fail "Embedded LLM stub not reachable on localhost:8000"
STUB_RESP=$(curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-4o-mini-stub","messages":[{"role":"user","content":"hello"}]}')
echo "$STUB_RESP" | grep -q "graphrag_seen=NO" || fail "Stub did not report graphrag_seen=NO for plain message"
pass "Embedded LLM stub responds correctly"

# GATE 3
echo "== E2E: Gate 3 — GraphRAG Extension File Present =="
AGENT_EXTENSION_PATH=""
if docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
  "test -f /a0/agents/agent0/extensions/message_loop_prompts_after/_80_graphrag.py"; then
  AGENT_EXTENSION_PATH="/a0/agents/agent0/extensions/message_loop_prompts_after/_80_graphrag.py"
elif docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
  "test -f /a0/agents/default/extensions/message_loop_prompts_after/_80_graphrag.py"; then
  AGENT_EXTENSION_PATH="/a0/agents/default/extensions/message_loop_prompts_after/_80_graphrag.py"
fi
[ -n "$AGENT_EXTENSION_PATH" ] || fail "Extension file not found in agent profile"
docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c \
  "grep -q 'GRAPHRAG_AGENT_EXTENSION_EXECUTED' ${AGENT_EXTENSION_PATH}" \
  || fail "Extension file missing AGENT marker"
pass "GraphRAG extension file verified in profile path ${AGENT_EXTENSION_PATH}"

# GATE 4
echo "== E2E: Gate 4 — GraphRAG Package Importable =="
docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c 'source /opt/venv-a0/bin/activate && python3 << PYEOF
from graphrag_agent_zero.hybrid_retrieve import HybridRetriever, RetrievalResult
from graphrag_agent_zero.neo4j_connector import is_neo4j_available
from graphrag_agent_zero.safe_cypher import get_safe_query, validate_parameters, SAFE_CYPHER_TEMPLATES
from graphrag_agent_zero.graph_builder import GraphBuilder
from graphrag_agent_zero.extension_hook import enhance_retrieval
print("ALL_IMPORTS_OK")
PYEOF' | grep -q "ALL_IMPORTS_OK" || fail "GraphRAG package import failed"
pass "All GraphRAG package modules importable"

# GATE 5
echo "== E2E: Gate 5 — Neo4j Down Resilience =="
docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c 'source /opt/venv-a0/bin/activate && python3 << PYEOF
import os
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USER"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "wrong"
os.environ["NEO4J_CONNECTION_TIMEOUT_MS"] = "500"
from graphrag_agent_zero.neo4j_connector import is_neo4j_available
from graphrag_agent_zero.extension_hook import enhance_retrieval
assert not is_neo4j_available(), "Neo4j should not be available"
result = enhance_retrieval("test query", [])
assert result["fallback_used"] == True, "Should fallback"
print("NEO4J_DOWN_SAFE")
PYEOF' | grep -q "NEO4J_DOWN_SAFE" || fail "Neo4j down resilience check failed"
pass "Neo4j down — extension degrades gracefully (no crash)"

# GATE 6
echo "== E2E: Gate 6 — Neo4j Available + Graph Query =="
select_neo4j_target

write_env "true" "$NEO4J_TARGET_URI" "$NEO4J_TARGET_USER" "$NEO4J_TARGET_PASSWORD" "$NEO4J_TARGET_DATABASE"
docker compose -f "$COMPOSE_FILE" up -d --build --force-recreate agent-zero-graphrag-dev
inject_deps

wait_http_200 "http://localhost:8087/health" || fail "UI health not reachable (Gate 6)"
wait_http_200 "http://localhost:8000/v1/models" || fail "Embedded LLM stub not reachable (Gate 6)"

wait_neo4j_ready "$NEO4J_TARGET_URI" "$NEO4J_TARGET_USER" "$NEO4J_TARGET_PASSWORD" "$NEO4J_TARGET_DATABASE" || fail "Neo4j target not healthy"
seed_neo4j_test_data "$NEO4J_TARGET_URI" "$NEO4J_TARGET_USER" "$NEO4J_TARGET_PASSWORD" "$NEO4J_TARGET_DATABASE" || fail "Neo4j seed failed"

docker compose -f "$COMPOSE_FILE" exec -T \
  -e TEST_NEO4J_URI="$NEO4J_TARGET_URI" \
  -e TEST_NEO4J_USER="$NEO4J_TARGET_USER" \
  -e TEST_NEO4J_PASSWORD="$NEO4J_TARGET_PASSWORD" \
  -e TEST_NEO4J_DATABASE="$NEO4J_TARGET_DATABASE" \
  agent-zero-graphrag-dev bash -c 'source /opt/venv-a0/bin/activate && python3 << PYEOF
import os
os.environ["GRAPH_RAG_ENABLED"] = "true"
os.environ["NEO4J_URI"] = os.environ["TEST_NEO4J_URI"]
os.environ["NEO4J_USER"] = os.environ["TEST_NEO4J_USER"]
os.environ["NEO4J_PASSWORD"] = os.environ["TEST_NEO4J_PASSWORD"]
os.environ["NEO4J_DATABASE"] = os.environ.get("TEST_NEO4J_DATABASE", "neo4j")
os.environ["NEO4J_CONNECTION_TIMEOUT_MS"] = "3000"
from graphrag_agent_zero.neo4j_connector import is_neo4j_available
from graphrag_agent_zero.extension_hook import enhance_retrieval
assert is_neo4j_available(), "Neo4j should be available"
result = enhance_retrieval("Tell me about GRAPH_RAG_TOKEN_123", [])
text_len = len(result.get("text", ""))
fallback = result.get("fallback_used", None)
assert fallback is not True, "Graph query should not fallback when Neo4j is healthy"
assert "GRAPH_RAG_TOKEN_123" in result.get("text", ""), "Expected token missing from GraphRAG context"
assert text_len > 0, "GraphRAG context text should not be empty"
print(f"GRAPH_QUERY_OK text_len={text_len} fallback={fallback}")
PYEOF' 2>&1 | tee "$ART_DIR/gate6.txt" | grep -q "GRAPH_QUERY_OK" || fail "Neo4j graph query failed"
pass "Neo4j available — GraphRAG query executed successfully"

# GATE 7
echo "== E2E: Gate 7 — Safe Cypher Engine =="
docker compose -f "$COMPOSE_FILE" exec -T agent-zero-graphrag-dev bash -c 'source /opt/venv-a0/bin/activate && python3 << PYEOF
from graphrag_agent_zero.safe_cypher import get_safe_query, validate_parameters
assert get_safe_query("check_health") is not None
assert get_safe_query("get_neighbors") is not None
assert get_safe_query("get_entity_details") is not None
assert get_safe_query("DROP_DATABASE") is None
assert get_safe_query("arbitrary_cypher") is None
params = {"entity_ids": ["test"], "limit": 5000}
assert validate_parameters(params)
assert params["limit"] == 100
print("SAFE_CYPHER_OK")
PYEOF' | grep -q "SAFE_CYPHER_OK" || fail "Safe Cypher engine validation failed"
pass "Safe Cypher engine blocks mutations, allows reads"

# Evidence bundle
echo "== Artifact-Grade Evidence Bundle Generation =="
docker compose -f "$COMPOSE_FILE" ps > "$ART_DIR/compose.ps.txt"
docker logs agent-zero-graphrag-dev > "$ART_DIR/agent-zero.logs.txt" 2>&1

cat > "$ART_DIR/verify.summary.json" <<EOF_SUMMARY
{
  "status": "PASS",
  "gates_passed": 7,
  "commit": "$(git rev-parse HEAD)",
  "neo4j_target_source": "${NEO4J_TARGET_SOURCE}",
  "neo4j_target_uri": "${NEO4J_TARGET_URI}",
  "stack_mode": "single_container_embedded_llm_stub",
  "date": "${RUN_ID}"
}
EOF_SUMMARY
pass "Evidence bundle dumped to ${ART_DIR}"

echo "== E2E SUMMARY =="
echo "PASS: all 7 GraphRAG extension gates verified."
exit 0
