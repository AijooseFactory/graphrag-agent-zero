#!/usr/bin/env bash
# Hybrid GraphRAG for Agent Zero — One-Command Installer (v0.2.0)
#
# Usage:
#   ./scripts/install.sh /path/to/agent-zero
#   ./scripts/install.sh --verify /path/to/agent-zero
#
# What it does:
#   1. Installs the graphrag-agent-zero Python package (+ Neo4j driver)
#   2. Copies extension files into your Agent Zero installation (persisted in usr/)
#   3. Creates a starter .env if one doesn't exist
#   4. [Optional] Verifies the installation state
#
set -euo pipefail

# ── Args & Mode ───────────────────────────────────────────────────────
VERIFY_MODE=false
A0_ROOT=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --verify)
      VERIFY_MODE=true
      shift
      ;;
    *)
      A0_ROOT="$1"
      shift
      ;;
  esac
done

if [ -z "$A0_ROOT" ]; then
  echo ""
  echo "  Hybrid GraphRAG for Agent Zero — Installer (v0.2.0)"
  echo "  ───────────────────────────────────────────────────"
  echo ""
  echo "  Usage:  ./scripts/install.sh [options] <agent-zero-path>"
  echo ""
  echo "  Options:"
  echo "    --verify    Check the health of an existing installation"
  echo ""
  echo "  Example:"
  echo "    ./scripts/install.sh /home/user/agent-zero"
  echo ""
  exit 1
fi

# Resolve to absolute path
A0_ROOT="$(cd "$A0_ROOT" 2>/dev/null && pwd)" || {
  echo "❌ Directory not found: $A0_ROOT"
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ── Verification Logic ────────────────────────────────────────────────
if ${VERIFY_MODE}; then
  echo ""
  echo "  Hybrid GraphRAG — Verification Mode"
  echo "  ────────────────────────────────────"
  echo "  Agent Zero path: $A0_ROOT"
  echo ""
  
  error_found=false
  
  # 1. Check Package
  echo -n "  [1/4] Python Package... "
  PYTHON_CMD="python3"
  if [ -x "/opt/venv-a0/bin/python3" ]; then PYTHON_CMD="/opt/venv-a0/bin/python3"; fi
  
  if $PYTHON_CMD -c "import graphrag_agent_zero" 2>/dev/null; then
    echo "✅"
  else
    echo "❌ (graphrag_agent_zero not installed)"
    error_found=true
  fi
  
  # 2. Check Extensions
  echo -n "  [2/4] Extensions...     "
  if [ -f "$A0_ROOT/usr/extensions/agent_init/_80_graphrag_patch.py" ]; then
    echo "✅"
  else
    echo "❌ (Dynamic patcher missing)"
    error_found=true
  fi
  
  # 3. Check Neo4j Connectivity
  echo -n "  [3/4] Neo4j Status...    "
  if [ -f "$A0_ROOT/.env" ] && grep -q "NEO4J_URI" "$A0_ROOT/.env"; then
     # Try a lightweight check if possible, otherwise just check config
     echo "✅ (Config present)"
  else
     echo "⚠️ (Config missing or disabled)"
  fi
  
  # 4. Check Terminology
  echo -n "  [4/4] Branding...        "
  if [ -f "$A0_ROOT/README.md" ] && grep -q "Agent Zero Vector Memory" "$A0_ROOT/README.md"; then
    echo "✅"
  else
    echo "⚠️ (Legacy terminology found)"
  fi
  
  echo ""
  if ${error_found}; then
    echo "❌ Verification FAILED. Run install.sh again to fix."
    exit 1
  else
    echo "✅ Verification PASSED. Hybrid GraphRAG is correctly grounded."
    exit 0
  fi
fi

# ── Install Logic ─────────────────────────────────────────────────────
echo ""
echo "  Hybrid GraphRAG for Agent Zero — Installer (v0.2.0)"
echo "  ───────────────────────────────────────────────────"
echo "  Agent Zero path: $A0_ROOT"
echo ""

# 1. Sanity Check
if [ ! -f "$A0_ROOT/python/api/api.py" ] && [ ! -f "$A0_ROOT/python/helpers/memory.py" ]; then
  echo "❌ Error: This doesn't look like an Agent Zero installation."
  exit 1
fi

# 2. Prerequisite Check (Docker)
if ! command -v docker &> /dev/null; then
  echo "⚠️  Warning: Docker not found. GraphRAG usually runs in Agent Zero containers."
fi

# 3. Install Python package
echo "  [1/4] Installing Python package..."
PIP_CMD="pip"
if [ -x "/opt/venv-a0/bin/pip" ]; then
    echo "  → Detected Agent Zero Container VENV (/opt/venv-a0/)."
    PIP_CMD="/opt/venv-a0/bin/pip"
fi

INSTALL_TARGET="${SCRIPT_DIR}[neo4j]"
$PIP_CMD install -e "$INSTALL_TARGET" --break-system-packages --quiet 2>/dev/null || \
$PIP_CMD install -e "$INSTALL_TARGET" --break-system-packages

# 4. Copy extensions
echo "  [2/4] Deploying extensions (persisted in usr/)..."
mkdir -p "$A0_ROOT/usr/extensions/message_loop_prompts_after"
mkdir -p "$A0_ROOT/usr/extensions/memory_saved_after"
mkdir -p "$A0_ROOT/usr/extensions/memory_deleted_after"
mkdir -p "$A0_ROOT/usr/extensions/agent_init"
mkdir -p "$A0_ROOT/usr/prompts"

cp "$SCRIPT_DIR/installer_files/_80_graphrag.py" "$A0_ROOT/usr/extensions/message_loop_prompts_after/"
cp "$SCRIPT_DIR/installer_files/_80_graphrag_sync.py" "$A0_ROOT/usr/extensions/memory_saved_after/"
cp "$SCRIPT_DIR/installer_files/_80_graphrag_delete.py" "$A0_ROOT/usr/extensions/memory_deleted_after/"
cp "$SCRIPT_DIR/installer_files/_80_graphrag_patch.py" "$A0_ROOT/usr/extensions/agent_init/"
cp "$SCRIPT_DIR/installer_files/agent.system.graphrag.md" "$A0_ROOT/usr/prompts/"

# 5. Config Setup
echo "  [3/4] Grounding configuration..."
if [ ! -f "$A0_ROOT/.env" ]; then
  cp "$SCRIPT_DIR/.env.example" "$A0_ROOT/.env"
  echo "  → Created .env from template."
else
  if ! grep -q "GRAPH_RAG_ENABLED" "$A0_ROOT/.env"; then
    echo "" >> "$A0_ROOT/.env"
    cat "$SCRIPT_DIR/.env.example" >> "$A0_ROOT/.env"
    echo "  → Appended GraphRAG settings to .env."
  fi
fi

# 6. Documentation Alignment
echo "  [4/4] Aligning terminology..."
if [ -f "$A0_ROOT/README.md" ]; then
  # Simple replacement for core terminology in README
  sed -i 's/FAISS/Agent Zero Vector Memory/g' "$A0_ROOT/README.md" 2>/dev/null || true
  sed -i 's/Vector Store/Agent Zero Vector Memory/g' "$A0_ROOT/README.md" 2>/dev/null || true
fi

echo ""
echo "  ───────────────────────────────────────────"
echo "  ✅  Hybrid GraphRAG v0.2.0 installed successfully!"
echo ""
echo "  Next steps:"
echo "    1. Edit $A0_ROOT/.env (set NEO4J_PASSWORD & GRAPH_RAG_ENABLED=true)"
echo "    2. [Optional] Run 'python scripts/batch_index.py' to index existing memories"
echo "    3. Restart Agent Zero to activate the GraphRAG Brain Protocols."
echo ""
