"""workflow.py — standalone orchestrator verification pipeline test runner."""

import asyncio
import importlib.util
import json
import logging
import os
import sys
import uuid
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("WorkflowVerificationRunner")

# 1. Clean and portable backend path resolution
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

try:
    from memory.workflow_memory import WorkflowMemoryManager
    from orchestrator.workflow_orchestrator import WorkflowOrchestrator
except (ImportError, ModuleNotFoundError) as exc:
    print("\n" + "=" * 80)
    print("ERROR: ENVIRONMENT COMPATIBILITY ISSUE")
    print("=" * 80)
    print(f"Failed to import required dependencies: {exc}")
    print("\nThis script is configured to run inside the project's Python 3.13 virtual environment.")
    print("Please execute the script using the correct python binary:")
    print("\n    ./venv/bin/python orchestrator/workflow.py")
    print("=" * 80 + "\n")
    sys.exit(1)


async def run_verification() -> dict:
    """Run end-to-end SDLC pipeline, perform DB and runtime validations, and output a summary."""
    logger.info("VERIFICATION: Starting orchestration verification test pipeline.")

    # Setup database path portably
    db_path = os.path.abspath(os.path.join(BACKEND_DIR, "orchestrator", "workflow_verify.db"))
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            logger.info("DATABASE: Removed pre-existing temporary verification database at %s", db_path)
        except Exception as exc:
            logger.warning("DATABASE: Failed to remove pre-existing test database: %s", exc)

    # Initialize SQLite manager and components
    memory = WorkflowMemoryManager(db_path=db_path)
    orchestrator = WorkflowOrchestrator(memory=memory)

    requirement = (
    "Build a FastAPI task management backend system with JWT authentication. "
    "Generate these files only: "
    "1) models.py for SQLite task/user models, "
    "2) auth.py for JWT authentication and password hashing, "
    "3) routes.py for CRUD task APIs, "
    "4) database.py for SQLite connection handling, "
    "5) test_routes.py for unit tests. "
    "Use FastAPI, SQLite, bcrypt, and python-jose. "
    "Do not generate documentation or frontend code."
)

    logger.info("VERIFICATION: Invoking orchestrator with requirement: '%s'", requirement)
    result = await orchestrator.run_workflow(requirement)
    logger.info("VERIFICATION: Orchestrator completed with status: %s", result.get("status"))

    # 2. Assertions validating orchestration result structure
    logger.info("VERIFICATION: Validating orchestration result object structure.")
    assert "workflow_id" in result, "Assertion Error: workflow_id is missing from result"
    assert "status" in result, "Assertion Error: status is missing from result"
    assert result["status"] in ("completed", "failed", "cancelled"), f"Assertion Error: invalid status: {result['status']}"
    assert "planning_duration" in result, "Assertion Error: planning_duration is missing from result"
    assert "coding_duration" in result, "Assertion Error: coding_duration is missing from result"
    assert "total_duration" in result, "Assertion Error: total_duration is missing from result"
    assert "tasks" in result, "Assertion Error: tasks is missing from result"
    assert isinstance(result["tasks"], list), "Assertion Error: tasks must be a list"

    workflow_id = result["workflow_id"]
    workflow_status = result["status"]

    # 3. Database validation and assertions
    logger.info("DATABASE: Starting database state assertions.")
    db_validation = "success"
    try:
        with memory._get_connection() as conn:
            # Assert workflows table contains exactly one workflow
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM workflows")
            workflow_count = cursor.fetchone()[0]
            assert workflow_count == 1, f"Assertion Error: Expected exactly 1 workflow row in DB, found {workflow_count}"

            # Verify workflow ID matches
            cursor.execute("SELECT workflow_id, original_requirement FROM workflows")
            db_workflow = cursor.fetchone()
            assert db_workflow["workflow_id"] == workflow_id, "Assertion Error: Workflow ID mismatch in DB"

            # Assert tasks table contains generated tasks
            cursor.execute("SELECT * FROM tasks WHERE workflow_id = ?", (workflow_id,))
            db_tasks = cursor.fetchall()
            assert len(db_tasks) > 0, "Assertion Error: No tasks were saved in DB for this workflow"

            # Verify generated file paths are persisted as relative paths, and statuses updated correctly
            db_task_map = {row["task_id"]: row for row in db_tasks}
            for task_res in result["tasks"]:
                task_id = task_res["task_id"]
                assert task_id in db_task_map, f"Assertion Error: Task {task_id} missing from tasks table"
                
                db_task = db_task_map[task_id]
                expected_status = task_res["status"]
                assert db_task["status"] == expected_status, f"Assertion Error: Task {task_id} status mismatch in DB"

                if expected_status == "completed":
                    file_path = db_task["file_path"]
                    assert file_path == task_res["file_path"], f"Assertion Error: File path mismatch for task {task_id}"
                    assert not os.path.isabs(file_path), f"Assertion Error: File path must be relative: {file_path}"
                    assert file_path.startswith("generated_projects"), f"Assertion Error: File path should be in output directory: {file_path}"

        logger.info("DATABASE: Database validation assertions completed successfully.")
    except Exception as exc:
        logger.error("DATABASE: Database validation assertions failed: %s", exc)
        db_validation = "failed"

    # 4. Runtime validation and code execution check
    logger.info("RUNTIME: Starting runtime execution validation on generated files.")
    runtime_validation = "success"
    generated_files = []

    for task_res in result["tasks"]:
        if task_res["status"] == "completed" and task_res["file_path"]:
            rel_path = task_res["file_path"]
            if not rel_path.endswith(".py"):
                logger.info("RUNTIME: Skipping runtime execution check for non-python file: %s", rel_path)
                generated_files.append(rel_path)
                continue

            abs_path = os.path.abspath(os.path.join(BACKEND_DIR, rel_path))
            generated_files.append(rel_path)

            logger.info("RUNTIME: Performing runtime execution check on %s", rel_path)
            if not os.path.exists(abs_path):
                logger.error("RUNTIME: Validation failed. File does not exist: %s", abs_path)
                runtime_validation = "failed"
                continue

            module_name = os.path.splitext(os.path.basename(abs_path))[0]
            module_dir = os.path.dirname(abs_path)

            # Adjust sys.path to resolve internal sibling imports portably
            added_to_path = False
            if module_dir not in sys.path:
                sys.path.insert(0, module_dir)
                added_to_path = True

            temp_module_name = f"verify_runner_{uuid.uuid4().hex}"
            try:
                # Dynamic load and execution
                spec = importlib.util.spec_from_file_location(module_name, abs_path)
                if spec is None or spec.loader is None:
                    raise ImportError(f"Could not load spec for {abs_path}")

                module = importlib.util.module_from_spec(spec)
                sys.modules[temp_module_name] = module
                spec.loader.exec_module(module)

                logger.info("RUNTIME: Generated code in %s executed and validated successfully.", rel_path)
            except Exception as exc:
                logger.error("RUNTIME: Generated code execution failed for %s: %s", rel_path, exc)
                runtime_validation = "failed"
            finally:
                sys.modules.pop(temp_module_name, None)
                if added_to_path:
                    try:
                        sys.path.remove(module_dir)
                    except ValueError:
                        pass

    # Clean up SQLite database but PRESERVE generated python code files
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            logger.info("DATABASE: Cleaned up temporary SQLite database file at %s", db_path)
        except Exception as exc:
            logger.warning("DATABASE: Failed to clean up database file: %s", exc)

    # 5. Build and return structured orchestration summary object
    summary = {
        "workflow_status": workflow_status,
        "workflow_id": workflow_id,
        "db_validation": db_validation,
        "runtime_validation": runtime_validation,
        "generated_files": generated_files,
        "planning_duration": result["planning_duration"],
        "coding_duration": result["coding_duration"],
        "total_duration": result["total_duration"],
    }

    logger.info("VERIFICATION: Summary object created successfully.")
    return summary


if __name__ == "__main__":
    # Run the verification workflow and print the formatted summary object
    try:
        summary_result = asyncio.run(run_verification())
        print("\n" + "=" * 50)
        print("STRUCTURED ORCHESTRATION SUMMARY:")
        print("=" * 50)
        print(json.dumps(summary_result, indent=2))
        print("=" * 50)
        
        # Raise system exit if any validation failed to act as a proper test runner exit code
        if (
            summary_result["db_validation"] != "success"
            or summary_result["runtime_validation"] != "success"
            or summary_result["workflow_status"] not in ("completed", "failed", "cancelled")
        ):
            logger.error("Verification pipeline finished with validation errors.")
            sys.exit(1)
        else:
            logger.info("Verification pipeline completed successfully (workflow status: %s).", summary_result["workflow_status"])
            sys.exit(0)
    except AssertionError as assert_exc:
        logger.critical("Verification aborted due to structure assertion failure: %s", assert_exc)
        sys.exit(2)
    except Exception as general_exc:
        logger.critical("Verification aborted due to unexpected pipeline error: %s", general_exc)
        sys.exit(3)
