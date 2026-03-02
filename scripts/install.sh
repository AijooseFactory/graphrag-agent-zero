#!/usr/bin/env bash
# Hybrid GraphRAG for Agent Zero — One-Command Installer
#
# Usage:
#   ./scripts/install.sh /path/to/agent-zero
#
# What it does:
#   1. Installs the graphrag-agent-zero Python package (+ Neo4j driver)
#   2. Copies extension files into your Agent Zero installation (persisted in usr/)
#   3. Creates a starter .env if one doesn't exist
#
set -euo pipefail

# ── Args ──────────────────────────────────────────────────────────────
A0_ROOT="${1:-}"

if [ -z "$A0_ROOT" ]; then
  echo ""
  echo "  Hybrid GraphRAG for Agent Zero — Installer"
  echo "  ───────────────────────────────────────────"
  echo ""
  echo "  Usage:  ./scripts/install.sh <agent-zero-path>"
  echo ""
  echo "  Example:"
  echo "    ./scripts/install.sh /home/user/agent-zero"
  echo "    ./scripts/install.sh /a0"
  echo ""
  exit 1
fi

# Resolve to absolute path
A0_ROOT="$(cd "$A0_ROOT" 2>/dev/null && pwd)" || {
  echo "❌ Directory not found: $1"
  exit 1
}

echo ""
echo "  Hybrid GraphRAG for Agent Zero — Installer"
echo "  ───────────────────────────────────────────"
echo "  Agent Zero path: $A0_ROOT"
echo ""

# ── Sanity check ──────────────────────────────────────────────────────
if [ ! -f "$A0_ROOT/python/api/api.py" ] && [ ! -f "$A0_ROOT/python/helpers/memory.py" ]; then
  echo "❌ This doesn't look like an Agent Zero installation."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ── Step 1: Install Python package ────────────────────────────────────
echo "  [1/4] Installing Python package..."

PIP_CMD="pip"

# Check if we are inside the Kali Virtual Environment (/opt/venv-a0/)
if [ -x "/opt/venv-a0/bin/pip" ]; then
    echo "  → Detected Agent Zero Container VENV (/opt/venv-a0/). Using isolated pip."
    PIP_CMD="/opt/venv-a0/bin/pip"
else
    # Fallback to checking for missing pip in base image
    if ! command -v pip &> /dev/null; then
        echo "  → System pip not found. Attempting to install python3-pip via apt..."
        if [ "$EUID" -ne 0 ]; then 
            sudo apt-get update && sudo apt-get install -y python3-pip || echo "  ⚠️ Failed to install pip."
        else
            apt-get update && apt-get install -y python3-pip || echo "  ⚠️ Failed to install pip."
        fi
    fi
fi

# Install the package. We apply --break-system-packages conditionally if using global pip.
if [ "$PIP_CMD" = "pip" ] || [ "$PIP_CMD" = "pip3" ]; then
    $PIP_CMD install -e "$SCRIPT_DIR[neo4j]" --break-system-packages --quiet 2>/dev/null || \
    $PIP_CMD install -e "$SCRIPT_DIR[neo4j]" --break-system-packages
else
    $PIP_CMD install -e "$SCRIPT_DIR[neo4j]" --quiet 2>/dev/null || \
    $PIP_CMD install -e "$SCRIPT_DIR[neo4j]"
fi

echo "  ✅  Package installed"

# ── Step 2: Copy extensions ───────────────────────────────────────────
echo "  [2/4] Copying extensions to persistent storage (usr/extensions)..."

# 2a. Prompt injection extension
mkdir -p "$A0_ROOT/usr/extensions/message_loop_prompts_after"
cp "$SCRIPT_DIR/installer_files/_80_graphrag.py" \
   "$A0_ROOT/usr/extensions/message_loop_prompts_after/"

# 2b. Auto-sync extensions
mkdir -p "$A0_ROOT/usr/extensions/memory_saved_after"
cp "$SCRIPT_DIR/installer_files/_80_graphrag_sync.py" \
   "$A0_ROOT/usr/extensions/memory_saved_after/"

mkdir -p "$A0_ROOT/usr/extensions/memory_deleted_after"
cp "$SCRIPT_DIR/installer_files/_80_graphrag_delete.py" \
   "$A0_ROOT/usr/extensions/memory_deleted_after/"

# 2c. Prompt template
mkdir -p "$A0_ROOT/usr/prompts"
cp "$SCRIPT_DIR/installer_files/agent.system.graphrag.md" \
   "$A0_ROOT/usr/prompts/"

# 2d. Dynamic Memory Patcher
mkdir -p "$A0_ROOT/usr/extensions/agent_init"
cp "$SCRIPT_DIR/installer_files/_80_graphrag_patch.py" \
   "$A0_ROOT/usr/extensions/agent_init/"

echo "  ✅  Extensions copied"

# ── Step 3: Apply memory hooks ─────────────────────────────
echo "  [3/4] Applying memory hooks..."
echo "  ✅  Using safe dynamic monkey-patch in usr/extensions/agent_init (Requires no core edits limit!)"

# ── Step 4: Create .env if missing ────────────────────────────────────
echo "  [4/4] Checking config..."

if [ ! -f "$A0_ROOT/.env" ]; then
  cp "$SCRIPT_DIR/.env.example" "$A0_ROOT/.env"
  echo "  ✅  Created .env from example (edit NEO4J_PASSWORD before starting)"
else
  # Append GraphRAG vars if not already present
  if ! grep -q "GRAPH_RAG_ENABLED" "$A0_ROOT/.env"; then
    echo "" >> "$A0_ROOT/.env"
    cat "$SCRIPT_DIR/.env.example" >> "$A0_ROOT/.env"
    echo "  ✅  Appended GraphRAG config to existing .env"
  else
    echo "  ✅  GraphRAG config already present in .env"
  fi
fi

# ── Done ──────────────────────────────────────────────────────────────
echo ""
echo "  ───────────────────────────────────────────"
echo "  ✅  Hybrid GraphRAG installed safely into persistent usr/ volume!"
echo ""
echo "  Next steps:"
echo "    1. Edit $A0_ROOT/.env and set your Neo4j password"
echo "    2. Set GRAPH_RAG_ENABLED=true"
echo "    3. Restart Agent Zero container to execute patches."
echo ""
