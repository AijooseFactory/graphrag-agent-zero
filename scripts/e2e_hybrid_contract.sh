#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="dev/docker-compose.graphrag-dev.yml"
SERVICE="agent-zero-graphrag-dev"
DEV_ENV_FILE="dev/.env"
RUN_ID="$(date -u +"%Y%m%dT%H%M%SZ")"
ART_DIR="artifacts/e2e-hybrid/${RUN_ID}"
mkdir -p "${ART_DIR}"

DEV_ENV_BACKUP="$(mktemp "/tmp/graphrag-dev-env.${RUN_ID}.XXXXXX")"
DEV_ENV_HAD_FILE="false"
SETTINGS_BACKUP="$(mktemp "/tmp/graphrag-settings.${RUN_ID}.XXXXXX")"
SETTINGS_BACKED_UP="false"

MEMORY_SENTINEL_ID="HYBRID_MEMORY_SENTINEL=${RUN_ID}"
SHARED_TOKEN="HYBRID_SHARED_TOKEN_${RUN_ID}"

if [ -f "${DEV_ENV_FILE}" ]; then
  cp "${DEV_ENV_FILE}" "${DEV_ENV_BACKUP}"
  DEV_ENV_HAD_FILE="true"
fi

restore_dev_env() {
  if [ "${DEV_ENV_HAD_FILE}" = "true" ]; then
    cp "${DEV_ENV_BACKUP}" "${DEV_ENV_FILE}"
  else
    rm -f "${DEV_ENV_FILE}"
  fi
  rm -f "${DEV_ENV_BACKUP}"
}

container_running() {
  docker ps --format '{{.Names}}' | grep -Fxq "${SERVICE}"
}

backup_settings() {
  if container_running && docker cp "${SERVICE}:/a0/usr/settings.json" "${SETTINGS_BACKUP}" >/dev/null 2>&1; then
    SETTINGS_BACKED_UP="true"
    echo "Backed up /a0/usr/settings.json"
    return 0
  fi
  echo "WARNING: could not backup /a0/usr/settings.json (container may not be running yet)"
}

restore_settings() {
  if [ "${SETTINGS_BACKED_UP}" != "true" ]; then
    rm -f "${SETTINGS_BACKUP}"
    return 0
  fi
  if ! container_running; then
    echo "WARNING: ${SERVICE} is not running; skipping settings restore"
    rm -f "${SETTINGS_BACKUP}"
    return 0
  fi
  docker cp "${SETTINGS_BACKUP}" "${SERVICE}:/a0/usr/settings.json" >/dev/null 2>&1 || true
  docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE}" bash -lc \
    "supervisorctl restart run_ui >/dev/null 2>&1 || true" || true
  rm -f "${SETTINGS_BACKUP}"
  echo "Restored /a0/usr/settings.json"
}

cleanup() {
  restore_dev_env
  restore_settings
}
trap cleanup EXIT

wait_http_200() {
  local url="$1"
  for _ in $(seq 1 90); do
    if curl -fsS -o /dev/null "${url}"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

env_or_default() {
  local key="$1"
  local default="$2"
  if [ "${DEV_ENV_HAD_FILE}" = "true" ]; then
    local value
    value="$(grep -m1 "^${key}=" "${DEV_ENV_BACKUP}" | cut -d= -f2- || true)"
    if [ -n "${value}" ]; then
      echo "${value}"
      return 0
    fi
  fi
  if [ -f ".env" ]; then
    local root_value
    root_value="$(grep -m1 "^${key}=" ".env" | cut -d= -f2- || true)"
    if [ -n "${root_value}" ]; then
      echo "${root_value}"
      return 0
    fi
  fi
  echo "${default}"
}

write_env() {
  local enabled="$1"
  local neo4j_uri="$2"
  local neo4j_user="$3"
  local neo4j_password="$4"
  local neo4j_database="$5"

  cat > "${DEV_ENV_FILE}" <<EOF_ENV
WEB_UI_HOST=0.0.0.0
WEB_UI_PORT=80

# Keyless deterministic test routing via in-container stub
OPENAI_API_BASE=http://127.0.0.1:8000/v1
OPENAI_API_KEY=dummy
LLM_STUB_DUMP_PROMPT=true

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

# Force memory recall every iteration for deterministic sentinel visibility.
A0_SET_memory_recall_enabled=true
A0_SET_memory_recall_interval=1
A0_SET_memory_recall_query_prep=false
A0_SET_memory_recall_post_filter=false
A0_SET_memory_recall_similarity_threshold=0.0

# Hybrid GraphRAG switch (preferred + legacy alias)
GRAPHRAG_ENABLED=${enabled}
GRAPH_RAG_ENABLED=${enabled}
PYTHONPATH=/a0/src

NEO4J_URI=${neo4j_uri}
NEO4J_USER=${neo4j_user}
NEO4J_PASSWORD=${neo4j_password}
NEO4J_DATABASE=${neo4j_database}
E2E_DISABLE_WS_CSRF=true
NEO4J_CONNECTION_TIMEOUT_MS=1200
NEO4J_QUERY_TIMEOUT_MS=5000
GRAPH_EXPAND_MAX_HOPS=2
GRAPH_EXPAND_LIMIT=100
GRAPH_MAX_RESULTS=50
EOF_ENV
}

recreate() {
  docker compose -f "${COMPOSE_FILE}" down --remove-orphans
  docker compose -f "${COMPOSE_FILE}" up -d --force-recreate "${SERVICE}"
}

force_stub_settings() {
  docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE}" bash -lc \
    "python3 - <<'PY'
import json
path = '/a0/usr/settings.json'
with open(path, 'r', encoding='utf-8') as f:
    s = json.load(f)

s['chat_model_provider'] = 'openai'
s['chat_model_name'] = 'openai/gpt-4o-mini-stub'
s['chat_model_api_base'] = 'http://127.0.0.1:8000/v1'

s['util_model_provider'] = 'openai'
s['util_model_name'] = 'openai/gpt-4o-mini-stub'
s['util_model_api_base'] = 'http://127.0.0.1:8000/v1'

s['embed_model_provider'] = 'openai'
s['embed_model_name'] = 'openai/text-embedding-3-stub'
s['embed_model_api_base'] = 'http://127.0.0.1:8000/v1'

s['browser_model_provider'] = 'openai'
s['browser_model_name'] = 'openai/gpt-4o-mini-stub'
s['browser_model_api_base'] = 'http://127.0.0.1:8000/v1'

s['memory_recall_enabled'] = True
s['memory_recall_interval'] = 1
s['memory_recall_query_prep'] = False
s['memory_recall_post_filter'] = False
s['memory_recall_similarity_threshold'] = 0.0

with open(path, 'w', encoding='utf-8') as f:
    json.dump(s, f, indent=2)

print('SETTINGS_FORCED_STUB')
PY" | grep -q "SETTINGS_FORCED_STUB"

  docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE}" bash -lc \
    "supervisorctl restart run_ui >/dev/null 2>&1 || true"
}

seed_memory() {
  docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE}" bash -lc \
    "source /opt/venv-a0/bin/activate && cd /a0 && python3 - <<'PY'
import asyncio
from python.helpers.memory import Memory

MEMORY_SENTINEL_ID = '${MEMORY_SENTINEL_ID}'
SHARED_TOKEN = '${SHARED_TOKEN}'

async def main():
    memory = await Memory.get_by_subdir('default', preload_knowledge=False)
    to_delete = []
    for doc in memory.db.get_all_docs().values():
        text = getattr(doc, 'page_content', '') or ''
        if 'HYBRID_MEMORY_SENTINEL=' in text:
            doc_id = doc.metadata.get('id')
            if doc_id:
                to_delete.append(doc_id)
    if to_delete:
        await memory.delete_documents_by_ids(to_delete)

    text = (
        f'{MEMORY_SENTINEL_ID}\\n'
        f'context_token={SHARED_TOKEN}\\n'
        'This memory proves baseline memory injection remains active.'
    )
    await memory.insert_text(text, metadata={'area': 'main'})
    print('MEMORY_SEEDED')

asyncio.run(main())
PY" | tee "${ART_DIR}/memory_seed.txt" | grep -q "MEMORY_SEEDED"
}

seed_graph() {
  local neo4j_uri="$1"
  local neo4j_user="$2"
  local neo4j_password="$3"
  local neo4j_database="$4"
  docker compose -f "${COMPOSE_FILE}" exec -T \
    -e TEST_NEO4J_URI="${neo4j_uri}" \
    -e TEST_NEO4J_USER="${neo4j_user}" \
    -e TEST_NEO4J_PASSWORD="${neo4j_password}" \
    -e TEST_NEO4J_DATABASE="${neo4j_database}" \
    "${SERVICE}" bash -lc "source /opt/venv-a0/bin/activate && python3 - <<'PY'
import os
from neo4j import GraphDatabase

shared = '${SHARED_TOKEN}'
uri = os.environ['TEST_NEO4J_URI']
user = os.environ['TEST_NEO4J_USER']
password = os.environ['TEST_NEO4J_PASSWORD']
database = os.environ.get('TEST_NEO4J_DATABASE', 'neo4j')

drv = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=3)
with drv.session(database=database) as session:
    session.run(
        'MERGE (e:Entity {id:\$id}) '
        'SET e.name=\$name, e.description=\$description, e.type=\$type',
        {
            'id': f'e2e_hybrid_{shared}',
            'name': shared,
            'description': f'Hybrid graph sentinel for {shared}',
            'type': 'Concept',
        },
    )
drv.close()
print('GRAPH_SEEDED')
PY" | tee "${ART_DIR}/graph_seed.txt" | grep -q "GRAPH_SEEDED"
}

probe_prompt() {
  local prompt="$1"
  node scripts/hybrid_prompt_probe.mjs --url "http://localhost:8087" --prompt "${prompt}" --timeout-ms 150000
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  local label="$3"
  if [[ "${haystack}" != *"${needle}"* ]]; then
    echo "FAIL: ${label} missing '${needle}'"
    echo "Response: ${haystack}"
    exit 1
  fi
}

assert_not_contains() {
  local haystack="$1"
  local needle="$2"
  local label="$3"
  if [[ "${haystack}" == *"${needle}"* ]]; then
    echo "FAIL: ${label} unexpectedly contained '${needle}'"
    echo "Response: ${haystack}"
    exit 1
  fi
}

# Per-case result tracking for summary.json
declare -A CASE_RESULTS

run_case() {
  local case_name="$1"
  local enabled="$2"
  local neo4j_uri="$3"
  local neo4j_user="$4"
  local neo4j_password="$5"
  local neo4j_database="$6"
  local expect_memory="$7"
  local expect_graph="$8"
  local expect_noop_marker="$9"

  echo "=== Running case: ${case_name} ==="
  write_env "${enabled}" "${neo4j_uri}" "${neo4j_user}" "${neo4j_password}" "${neo4j_database}"
  recreate
  wait_http_200 "http://localhost:8087/health"
  wait_http_200 "http://localhost:8000/v1/models"
  force_stub_settings
  wait_http_200 "http://localhost:8087/health"

  # ── Evidence: compose ps ──
  docker compose -f "${COMPOSE_FILE}" ps > "${ART_DIR}/${case_name}.compose_ps.txt" 2>&1 || true

  # ── Evidence: scrubbed environment ──
  if [ -f "${DEV_ENV_FILE}" ]; then
    sed -E \
      -e 's/(PASSWORD=).*/\1***/' \
      -e 's/(API_KEY=).*/\1***/' \
      -e 's/(SECRET=).*/\1***/' \
      "${DEV_ENV_FILE}" > "${ART_DIR}/${case_name}.env_scrubbed.txt"
  fi

  seed_memory
  if [ "${expect_graph}" = "YES" ]; then
    seed_graph "${neo4j_uri}" "${neo4j_user}" "${neo4j_password}" "${neo4j_database}"
  fi

  local prompt="Use GraphRAG if available: what do you know about ${SHARED_TOKEN} and ${MEMORY_SENTINEL_ID}? Reply in one short sentence."
  local warmup
  warmup="$(probe_prompt "Warmup pass for hybrid verification. Reply with READY only.")"
  echo "${warmup}" > "${ART_DIR}/${case_name}.warmup.txt"
  local response
  response="$(probe_prompt "${prompt}")"
  echo "${response}" | tee "${ART_DIR}/${case_name}.response.txt"

  assert_contains "${response}" "memory_seen=${expect_memory}" "${case_name}"
  assert_contains "${response}" "graphrag_seen=${expect_graph}" "${case_name}"

  # ── Evidence: per-service logs ──
  docker logs --tail 500 "${SERVICE}" > "${ART_DIR}/${case_name}.agent.log" 2>&1 || true

  # Capture llm-stub logs (runs inside the same container on port 8000)
  docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE}" bash -c \
    "cat /var/log/supervisor/run_llm_stub-*.log 2>/dev/null || echo 'no stub log'" \
    > "${ART_DIR}/${case_name}.stub.log" 2>&1 || true

  local logs
  logs="$(cat "${ART_DIR}/${case_name}.agent.log")"

  if [ "${expect_graph}" = "YES" ]; then
    echo "${logs}" | grep -q "GRAPHRAG_CONTEXT_INJECTED" || {
      echo "FAIL: ${case_name} missing GRAPHRAG_CONTEXT_INJECTED"
      CASE_RESULTS["${case_name}"]="FAIL"
      exit 1
    }
  else
    if [ "${expect_noop_marker}" = "YES" ]; then
      echo "${logs}" | grep -q "GRAPHRAG_NOOP_NEO4J_DOWN" || {
        echo "FAIL: ${case_name} missing GRAPHRAG_NOOP_NEO4J_DOWN"
        CASE_RESULTS["${case_name}"]="FAIL"
        exit 1
      }
    fi
  fi

  CASE_RESULTS["${case_name}"]="PASS"
  echo "PASS: ${case_name}"
}

backup_settings

if [ ! -d node_modules ]; then
  npm install
fi

# Capture git SHA and build
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
GIT_SHA_FULL="$(git rev-parse HEAD 2>/dev/null || echo 'unknown')"
export BUILD_GIT_SHA="${GIT_SHA}"

docker compose -f "${COMPOSE_FILE}" build "${SERVICE}"

# Capture docker image digest
IMAGE_DIGEST="$(docker inspect --format='{{index .RepoDigests 0}}' "agentzero/graphrag-dev:latest" 2>/dev/null || echo 'local-build')"

NEO4J_URI_UP="$(env_or_default "NEO4J_URI" "bolt://host.docker.internal:7687")"
NEO4J_USER_UP="$(env_or_default "NEO4J_USER" "neo4j")"
NEO4J_PASSWORD_UP="$(env_or_default "NEO4J_PASSWORD" "graphrag2026")"
NEO4J_DATABASE_UP="$(env_or_default "NEO4J_DATABASE" "neo4j")"

run_case "A_off_stock_memory_only" "false" \
  "${NEO4J_URI_UP}" "${NEO4J_USER_UP}" "${NEO4J_PASSWORD_UP}" "${NEO4J_DATABASE_UP}" \
  "YES" "NO" "NO"

run_case "B_on_memory_plus_graph" "true" \
  "${NEO4J_URI_UP}" "${NEO4J_USER_UP}" "${NEO4J_PASSWORD_UP}" "${NEO4J_DATABASE_UP}" \
  "YES" "YES" "NO"

run_case "C_on_neo4j_down_memory_only" "true" \
  "bolt://127.0.0.1:17687" "${NEO4J_USER_UP}" "${NEO4J_PASSWORD_UP}" "${NEO4J_DATABASE_UP}" \
  "YES" "NO" "YES"

# ── Evidence: summary.json ──
cat > "${ART_DIR}/summary.json" <<EOF_JSON
{
  "verdict": "PASS",
  "run_id": "${RUN_ID}",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "git_sha": "${GIT_SHA_FULL}",
  "git_sha_short": "${GIT_SHA}",
  "docker_image_digest": "${IMAGE_DIGEST}",
  "memory_sentinel": "${MEMORY_SENTINEL_ID}",
  "shared_token": "${SHARED_TOKEN}",
  "cases": {
    "A_off_stock_memory_only": {
      "result": "${CASE_RESULTS[A_off_stock_memory_only]:-UNKNOWN}",
      "graphrag_enabled": false,
      "expect_memory": true,
      "expect_graph": false
    },
    "B_on_memory_plus_graph": {
      "result": "${CASE_RESULTS[B_on_memory_plus_graph]:-UNKNOWN}",
      "graphrag_enabled": true,
      "neo4j_reachable": true,
      "expect_memory": true,
      "expect_graph": true
    },
    "C_on_neo4j_down_memory_only": {
      "result": "${CASE_RESULTS[C_on_neo4j_down_memory_only]:-UNKNOWN}",
      "graphrag_enabled": true,
      "neo4j_reachable": false,
      "expect_memory": true,
      "expect_graph": false,
      "expect_noop_marker": true
    }
  }
}
EOF_JSON

echo "PASS: hybrid contract verified. Artifacts: ${ART_DIR}"
