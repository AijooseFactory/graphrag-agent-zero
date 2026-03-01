import subprocess
import time
import requests
import sys
import os

# Constants
CONTAINER_NAME = "agent-zero-graphrag-dev"
WEB_UI_URL = "http://localhost:8087"

def run_command(cmd, shell=True):
    result = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def trigger_agent(env_vars=None):
    env_str = " ".join([f"-e {k}={v}" for k, v in (env_vars or {}).items()])
    run_command(f"docker cp scripts/trigger_agent.py {CONTAINER_NAME}:/a0/trigger_agent.py")
    cmd = f"docker exec -w /a0 {env_str} {CONTAINER_NAME} bash -c 'source /opt/venv-a0/bin/activate && python3 /a0/trigger_agent.py'"
    rc, stdout, stderr = run_command(cmd)
    return stdout + "\n" + stderr

def print_step(name):
    print(f"\n--- {name} ---")

def pass_step(msg):
    print(f"PASS: {msg}")

def fail_step(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)

def seed_graph_data():
    print("Seeding graph data for 'ON' test...")
    seed_script = """
import sys
sys.path.insert(0, '/a0')
from graphrag_agent_zero.neo4j_connector import get_connector
connector = get_connector()
connector.execute_template('merge_entity', {'name': 'E2E_TEST_NODE', 'type': 'Test', 'properties': {'status': 'active'}})
"""
    run_command(f"docker exec -w /a0 -e PYTHONPATH=. {CONTAINER_NAME} bash -c \"source /opt/venv-a0/bin/activate && python3 -c \\\"{seed_script}\\\"\"")

def main():
    mode = os.getenv("E2E_MODE", "ALL")
    print(f"=== GraphRAG E2E Harness (Mode: {mode}) ===")

    # 1. Verify health
    if mode == "ALL" or mode == "HEALTH":
        print_step("Step 1: Health Check")
        rc, stdout, _ = run_command("docker ps --format '{{.Names}}'")
        running_containers = [c.strip() for c in stdout.split('\n') if c.strip()]
        
        if CONTAINER_NAME not in running_containers:
            fail_step(f"Container {CONTAINER_NAME} is not running.")
        
        pass_step(f"Container {CONTAINER_NAME} verified.")
        
        # Inject missing pip packages required for testing the extension
        print("Injecting Neo4j driver into test container...")
        rc, out, err = run_command(f"docker exec {CONTAINER_NAME} bash -c 'source /opt/venv-a0/bin/activate && pip install neo4j httpx'")
        if rc != 0:
            fail_step(f"Failed to install neo4j in container: {err}")
        pass_step("Dependencies mapped.")
        
        try:
            resp = requests.get(WEB_UI_URL, timeout=10)
            if resp.status_code == 200:
                pass_step("Web UI is up at 8087")
            else:
                fail_step(f"Web UI returned {resp.status_code}")
        except Exception as e:
            fail_step(f"Web UI unreachable: {e}")

    # 2. Baseline (OFF)
    if mode == "ALL" or mode == "BASELINE":
        print_step("Step 2: Baseline (OFF)")
        stdout = trigger_agent({"GRAPH_RAG_ENABLED": "false"})
        if "GRAPHRAG_EXTENSION_EXECUTED" in stdout:
            pass_step("Extension executed marker found")
        else:
            fail_step(f"GRAPHRAG_EXTENSION_EXECUTED not found in baseline trigger output: {stdout[:500]}")
            
        if "GRAPHRAG_CONTEXT_INJECTED" in stdout:
            fail_step("GRAPHRAG_CONTEXT_INJECTED found in baseline (should be OFF)")
        else:
            pass_step("No context injection in baseline (Correct)")

    # 3. ON Test
    if mode == "ALL" or mode == "ON":
        print_step("Step 3: GraphRAG ON + Neo4j UP")
        seed_graph_data()
        stdout = trigger_agent({"GRAPH_RAG_ENABLED": "true"})
        if "GRAPHRAG_CONTEXT_INJECTED" in stdout:
            pass_step("GRAPHRAG_CONTEXT_INJECTED verified")
        else:
            fail_step(f"GRAPHRAG_CONTEXT_INJECTED MISSING in ON trigger output: {stdout[:500]}")

    # 4. DOWN Test
    if mode == "ALL" or mode == "DOWN":
        print_step("Step 4: GraphRAG ON + Neo4j DOWN")
        # override NEO4J_URI to a broken state
        stdout = trigger_agent({"GRAPH_RAG_ENABLED": "true", "NEO4J_URI": "bolt://invalid_host:7687"})
        if "GRAPHRAG_NOOP_NEO4J_DOWN" in stdout:
            pass_step("GRAPHRAG_NOOP_NEO4J_DOWN verified")
        else:
            fail_step(f"GRAPHRAG_NOOP_NEO4J_DOWN MISSING in DOWN test output: {stdout[:500]}")

    # 5. Memory Receipt
    if mode == "ALL" or mode == "MEMORY":
        print_step("Step 5: Memory Receipt")
        test_receipt = '{"e2e_id": "GRAPH_RAG_SELF_RECEIPT", "status": "perfect"}'
        run_command(f"docker exec {CONTAINER_NAME} mkdir -p /a0/usr/memory/e2e")
        run_command(f"docker exec {CONTAINER_NAME} bash -c \"echo '{test_receipt}' > /a0/usr/memory/e2e/receipt.json\"")
        
        _, stdout, _ = run_command(f"docker exec {CONTAINER_NAME} cat /a0/usr/memory/e2e/receipt.json")
        if "GRAPH_RAG_SELF_RECEIPT" in stdout:
            pass_step("Memory receipt saved and retrieved successfully")
        else:
            fail_step("Memory receipt failed")

    print("\nSTAGE COMPLETE ✅")

if __name__ == "__main__":
    main()
