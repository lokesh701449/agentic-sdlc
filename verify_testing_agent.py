import asyncio
import json
import logging
import os
import shutil
import sys
from unittest.mock import patch

# Configure sys.path to find backend modules
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("VerifyTestingAgent")

from memory.workflow_memory import WorkflowMemoryManager
from orchestrator.workflow_orchestrator import WorkflowOrchestrator


async def main():
    print("Planner")
    print("↓")
    
    # 1. Clean generated_projects directory for a clean run
    generated_dir = os.path.join(BACKEND_DIR, "generated_projects")
    if os.path.exists(generated_dir):
        print(f"Cleaning existing generated files in {generated_dir}...")
        try:
            shutil.rmtree(generated_dir)
        except Exception as e:
            print(f"Warning: could not clean directory: {e}")

    # Set up verification DB
    db_path = os.path.join(BACKEND_DIR, "orchestrator", "workflow_verify.db")
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

    memory = WorkflowMemoryManager(db_path=db_path)
    orchestrator = WorkflowOrchestrator(memory=memory)

    # 2. Mock approval
    print("Approval")
    print("↓")
    
    requirement = (
        "Generate a simple FastAPI CRUD API with a SQLite database connection. "
        "The application should allow creating, reading, updating, and deleting items. "
        "It must consist of exactly two tasks: "
        "1) auth.py to implement password hashing and verify functions "
        "2) main.py to setup routes."
    )

    # We patch builtins.input to automatically approve the plan
    # and bypass any manual prompts.
    with patch("builtins.input", side_effect=["", "yes"]):
        print("Coding")
        print("↓")
        print("Testing")
        print("↓")
        print("Runtime Validation")
        print("↓")
        
        result = await orchestrator.run_workflow(requirement)

    print("Workflow Summary")
    print("================")
    print(json.dumps(result, indent=2))
    
    # Check assertions to verify the output conforms
    assert "workflow_id" in result
    assert "status" in result
    assert result["status"] == "completed" or result["status"] == "failed"
    assert "test_suite" in result
    
    # Check DB to verify persistence of test execution metadata
    with memory._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM test_results WHERE workflow_id = ?", (result["workflow_id"],))
        test_count = cursor.fetchone()[0]
        print(f"\nPersisted test cases in DB: {test_count}")
        
        cursor.execute("SELECT test_name, status, execution_time, error_message FROM test_results WHERE workflow_id = ?", (result["workflow_id"],))
        rows = cursor.fetchall()
        for idx, row in enumerate(rows, 1):
            print(f"  {idx}. Test: {row['test_name']} | Status: {row['status']} | Time: {row['execution_time']}s | Error: {row['error_message']}")

    # Clean up test DB
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
