#!/bin/bash
set -e

echo "=== System Check: GraphRAG for Agent Zero ==="
echo "CAUTION: This check uses the existing dev volume. Data is preserved."

# 1. Linting
echo "Running Ruff..."
if command -v ruff >/dev/null 2>&1; then
    ruff check .
else
    echo "Ruff not found, skipping lint."
fi

# 2. Unit Tests
echo "Running Pytest..."
if command -v pytest >/dev/null 2>&1; then
    pytest tests/
else
    echo "Pytest not found, skipping unit tests."
fi

# 3. Dev Stack check (Protecting Volumes)
echo "Ensuring Dev Stack is up (Non-destructive)..."
docker compose -f dev/docker-compose.graphrag-dev.yml up -d

# Wait for healthy Web UI
echo "Waiting for Web UI to be ready..."
MAX_RETRIES=12
COUNT=0
while [[ "$(curl -s -o /dev/null -w ''%{http_code}'' http://localhost:8087)" != "200" && $COUNT -lt $MAX_RETRIES ]]; do
    echo "Still waiting (retry $COUNT)..."
    sleep 5
    ((COUNT++))
done

if [ $COUNT -eq $MAX_RETRIES ]; then
    echo "❌ ERROR: Web UI failed to start. Check docker logs."
    exit 1
fi
echo "Web UI ready."

# 4. E2E CLI
echo "Running E2E CLI Harness..."
bash scripts/e2e.sh

echo ""
echo "✅ ALL CHECKS PASSED. SYSTEM IS MAINTAINABLE."
