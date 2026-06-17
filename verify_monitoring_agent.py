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
logger = logging.getLogger("VerifyMonitoringAgent")

from memory.workflow_memory import WorkflowMemoryManager
from orchestrator.workflow_orchestrator import WorkflowOrchestrator


async def main():
    # 1. Clean generated_projects directory for a clean run
    generated_dir = os.path.join(BACKEND_DIR, "generated_projects")
    if os.path.exists(generated_dir):
        print(f"Cleaning existing generated files in {generated_dir}...")
        try:
            shutil.rmtree(generated_dir)
        except Exception as e:
            print(f"Warning: could not clean directory: {e}")

    # Set up verification DB
    db_path = os.path.join(BACKEND_DIR, "orchestrator", "workflow_verify_monitoring.db")
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

    memory = WorkflowMemoryManager(db_path=db_path)
    
    # Create the workflow orchestrator
    orchestrator = WorkflowOrchestrator(memory=memory)

    # 2. Mock approval and run workflow with specific requirement string to trigger mocks if needed
    requirement = (
        "Generate a simple authentication utility module in auth.py. "
        "It must implement get_password_hash and verify_password functions. "
        "It must consist of exactly two tasks: "
        "1) auth.py implementation "
        "2) test_auth.py unit tests."
    )

    # Patch input to auto-approve the plan
    with patch("builtins.input", side_effect=["", "yes"]):
        print("Running workflow...")
        result = await orchestrator.run_workflow(requirement)

    print("\nWorkflow Summary Output:")
    print("========================")
    print(json.dumps(result, indent=2))
    
    # Verify monitoring report presence and schema in output
    print("\nVerifying Monitoring Report in workflow payload...")
    assert "monitoring_report" in result, "Result must contain 'monitoring_report'"
    report = result["monitoring_report"]
    assert report is not None, "Monitoring report should not be None"
    print(f"Report keys: {list(report.keys())}")
    
    assert "workflow_id" in report
    assert "status" in report
    assert "total_duration" in report
    assert "agents" in report
    
    print("\nVerifying nested agent details in Monitoring Report...")
    agents = report["agents"]
    assert isinstance(agents, list)
    for agent_data in agents:
        print(f"  Agent: {agent_data['agent']} | Duration: {agent_data['duration']}s")
        assert "agent" in agent_data, "Agent summary must have 'agent' key"
        assert "duration" in agent_data, "Agent summary must have 'duration' key"

    # Check database persistence
    print("\nQuerying 'monitoring_metrics' table from workflow_verify_monitoring.db...")
    with memory._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM monitoring_metrics WHERE workflow_id = ?", (result["workflow_id"],))
        metric_count = cursor.fetchone()[0]
        print(f"Total persisted monitoring metric rows in DB: {metric_count}")
        assert metric_count > 0, "No metrics saved in database!"
        
        cursor.execute("SELECT agent_name, execution_duration, status, timestamp FROM monitoring_metrics WHERE workflow_id = ?", (result["workflow_id"],))
        rows = cursor.fetchall()
        for idx, row in enumerate(rows, 1):
            print(f"  {idx}. Agent: {row['agent_name']} | Duration: {row['execution_duration']:.2f}s | Status: {row['status']} | Timestamp: {row['timestamp']}")
            assert row['agent_name'] in ("PlannerAgent", "CodingAgent", "TestingAgent", "WorkflowOrchestrator"), f"Unexpected agent_name in DB: {row['agent_name']}"
            assert row['execution_duration'] >= 0
            assert row['status'] in ("success", "failed", "completed")

    print("\nVerification successful! All checks passed.")

    # Clean up test DB
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
