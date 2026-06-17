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
logger = logging.getLogger("VerifyReviewAgent")

from memory.workflow_memory import WorkflowMemoryManager
from orchestrator.workflow_orchestrator import WorkflowOrchestrator
from agents.coder import CodingAgent


class ImperfectCodingAgent(CodingAgent):
    """Wraps CodingAgent to generate intentionally imperfect code on the first call, forcing correction."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.call_count = 0

    async def code_task(self, task):
        self.call_count += 1
        # On the very first call, return an intentionally imperfect implementation
        if self.call_count == 1:
            logger.info("IMPERFECT_CODER: Generating intentionally imperfect code for testing.")
            resolved_path = os.path.abspath(os.path.join(self._config.output_dir, "auth.py"))
            os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
            
            imperfect_code = """
def get_password_hash(password: str) -> str:
    # Intentionally insecure raw text return
    return password

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Intentionally always returns True
    return True
"""
            with open(resolved_path, "w", encoding="utf-8") as f:
                f.write(imperfect_code)
                
            task_id = getattr(task, "id", "TASK-001") if not isinstance(task, dict) else task.get("id", "TASK-001")
            return {
                "task_id": task_id,
                "status": "success",
                "file_path": "generated_projects/auth.py",
                "generation_time_seconds": 0.1,
            }
        else:
            # On subsequent calls, let it run the normal logic (real LLM or fallback)
            logger.info("IMPERFECT_CODER: Generating corrected code (attempt %d).", self.call_count)
            # Remove from cache if any
            cached_path = self.has_cached_file(task)
            if cached_path and os.path.exists(cached_path):
                try:
                    os.remove(cached_path)
                except Exception:
                    pass
            return await super().code_task(task)


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
    db_path = os.path.join(BACKEND_DIR, "orchestrator", "workflow_verify_review.db")
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

    memory = WorkflowMemoryManager(db_path=db_path)
    
    # Create the workflow orchestrator with the ImperfectCodingAgent injected
    imperfect_coder = ImperfectCodingAgent()
    orchestrator = WorkflowOrchestrator(memory=memory, coder=imperfect_coder)

    # 2. Mock approval
    print("Approval")
    print("↓")
    
    requirement = (
        "Generate a simple authentication utility module in auth.py. "
        "It must implement get_password_hash and verify_password functions. "
        "It must consist of exactly two tasks: "
        "1) auth.py implementation "
        "2) test_auth.py unit tests."
    )

    # Patch input to auto-approve the plan
    with patch("builtins.input", side_effect=["", "yes"]):
        print("Coding")
        print("↓")
        print("Testing")
        print("↓")
        print("Review")
        print("↓")
        print("Self-Correction")
        print("↓")
        print("Re-Test")
        print("↓")
        print("Re-Review")
        print("↓")
        print("Runtime Validation")
        print("↓")
        
        result = await orchestrator.run_workflow(requirement)

    print("Workflow Summary")
    print("================")
    print(json.dumps(result, indent=2))
    
    # Verify outcomes
    assert "workflow_id" in result
    assert "status" in result
    assert result["status"] == "completed" or result["status"] == "failed"
    
    # Check DB to verify persistence of review issues
    with memory._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM review_issues WHERE workflow_id = ?", (result["workflow_id"],))
        issue_count = cursor.fetchone()[0]
        print(f"\nPersisted review issues in DB: {issue_count}")
        
        cursor.execute("SELECT file_name, severity, issue_description, suggested_fix, correction_attempt FROM review_issues WHERE workflow_id = ?", (result["workflow_id"],))
        rows = cursor.fetchall()
        for idx, row in enumerate(rows, 1):
            print(f"  {idx}. File: {row['file_name']} | Severity: {row['severity']} | Attempt: {row['correction_attempt']} | Error: {row['issue_description']}")

    # Clean up test DB
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
