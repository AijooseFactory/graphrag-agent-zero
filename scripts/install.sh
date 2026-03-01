#!/usr/bin/env bash
# Hybrid GraphRAG for Agent Zero — One-Command Installer
#
# Usage:
#   ./scripts/install.sh /path/to/agent-zero
#
# What it does:
#   1. Installs the graphrag-agent-zero Python package (+ Neo4j driver)
#   2. Copies extension files into your Agent Zero installation
#   3. Applies the memory_saved_after hook (safe, non-destructive)
#   4. Creates a starter .env if one doesn't exist
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
if [ ! -f "$A0_ROOT/python/helpers/memory.py" ]; then
  echo "❌ This doesn't look like an Agent Zero installation."
  echo "   Expected to find: $A0_ROOT/python/helpers/memory.py"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ── Step 1: Install Python package ────────────────────────────────────
echo "  [1/4] Installing Python package..."
pip install -e "$SCRIPT_DIR[neo4j]" --quiet 2>/dev/null || \
pip install -e "$SCRIPT_DIR[neo4j]"
echo "  ✅  Package installed"

# ── Step 2: Copy extensions ───────────────────────────────────────────
echo "  [2/4] Copying extensions..."

# 2a. Prompt injection extension
mkdir -p "$A0_ROOT/agents/default/extensions/message_loop_prompts_after"
cp "$SCRIPT_DIR/agent-zero-fork/agents/default/extensions/message_loop_prompts_after/_80_graphrag.py" \
   "$A0_ROOT/agents/default/extensions/message_loop_prompts_after/"

# 2b. Auto-sync extension
mkdir -p "$A0_ROOT/python/extensions/memory_saved_after"
cp "$SCRIPT_DIR/agent-zero-fork/python/extensions/memory_saved_after/_80_graphrag_sync.py" \
   "$A0_ROOT/python/extensions/memory_saved_after/"

# 2c. Prompt template
mkdir -p "$A0_ROOT/prompts"
cp "$SCRIPT_DIR/agent-zero-fork/prompts/agent.system.graphrag.md" \
   "$A0_ROOT/prompts/"

echo "  ✅  Extensions copied"

# ── Step 3: Apply memory_saved_after hook ─────────────────────────────
echo "  [3/4] Applying memory hook..."

MEMORY_FILE="$A0_ROOT/python/helpers/memory.py"
if grep -q "memory_saved_after" "$MEMORY_FILE" 2>/dev/null; then
  echo "  ✅  Hook already applied (skipped)"
else
  # Find the insert_text method and add the hook after "ids = await self.insert_documents([doc])"
  # We use a safe sed that only modifies if the exact target line is found
  if grep -q 'ids = await self.insert_documents(\[doc\])' "$MEMORY_FILE"; then
    # Create backup
    cp "$MEMORY_FILE" "$MEMORY_FILE.bak"

    # Apply patch using Python for cross-platform safety
    python3 -c "
import re
with open('$MEMORY_FILE', 'r') as f:
    content = f.read()

old = '''        ids = await self.insert_documents([doc])
        return ids[0]'''

new = '''        ids = await self.insert_documents([doc])

        # Fire memory_saved_after extensions (e.g. GraphRAG sync)
        try:
            from python.helpers.extension import call_extensions
            await call_extensions(
                \"memory_saved_after\", agent=None,
                text=text, metadata=metadata, doc_id=ids[0],
                memory_subdir=self.memory_subdir,
            )
        except Exception:
            pass  # Never break memory save

        return ids[0]'''

if old in content:
    content = content.replace(old, new, 1)
    with open('$MEMORY_FILE', 'w') as f:
        f.write(content)
    print('  ✅  Hook applied (backup: memory.py.bak)')
else:
    print('  ⚠️  Could not auto-patch — apply manually (see README)')
"
  else
    echo "  ⚠️  Could not find insert_text target — apply manually (see README)"
  fi
fi

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
echo "  ✅  Hybrid GraphRAG installed!"
echo ""
echo "  Next steps:"
echo "    1. Edit $A0_ROOT/.env and set your Neo4j password"
echo "    2. Set GRAPH_RAG_ENABLED=true"
echo "    3. Restart Agent Zero"
echo ""
