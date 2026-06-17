"""WorkflowMemoryManager — SQLite-based database manager for tracking SDLC workflow state."""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class WorkflowMemoryManager:
    """Manages the workflow execution memory state in a SQLite database."""

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize database connection. Resolves path dynamically to ensure portability."""
        if db_path is None:
            # Dynamically resolve db_path relative to backend/memory directory
            db_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "workflow_memory.db")
            )
        self.db_path = db_path
        logger.info("Initializing WorkflowMemoryManager with database at: %s", self.db_path)
        self.initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a new database connection with row factory configured."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize_database(self) -> None:
        """Create workflows and tasks tables if they do not exist."""
        logger.info("DB_OP: Initializing SQLite database tables.")
        try:
            # Enable foreign keys
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA foreign_keys = ON;")
                
                # workflows table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS workflows (
                        workflow_id TEXT PRIMARY KEY,
                        original_requirement TEXT NOT NULL,
                        planner_output TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'planning',
                        created_at TEXT NOT NULL
                    )
                """)
                
                # Dynamic migration: Add status column if it doesn't exist in workflows table
                try:
                    cursor.execute("ALTER TABLE workflows ADD COLUMN status TEXT NOT NULL DEFAULT 'planning';")
                    logger.info("DB_OP: Successfully migrated workflows table to include status column.")
                except sqlite3.OperationalError:
                    # Column already exists
                    pass
                
                # tasks table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        workflow_id TEXT NOT NULL,
                        task_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        task_type TEXT NOT NULL,
                        priority TEXT,
                        dependencies TEXT, -- JSON array of strings
                        acceptance_criteria TEXT, -- JSON array of strings
                        estimated_effort TEXT,
                        status TEXT NOT NULL, -- pending, in_progress, completed, failed
                        file_path TEXT, -- relative path to file
                        generation_time_seconds REAL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (workflow_id, task_id),
                        FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id) ON DELETE CASCADE
                    )
                """)
                
                # test_results table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS test_results (
                        workflow_id TEXT NOT NULL,
                        test_name TEXT NOT NULL,
                        execution_time REAL NOT NULL,
                        status TEXT NOT NULL,
                        error_message TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id) ON DELETE CASCADE
                    )
                """)
                
                # review_issues table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS review_issues (
                        workflow_id TEXT NOT NULL,
                        file_name TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        issue_description TEXT NOT NULL,
                        suggested_fix TEXT,
                        correction_attempt INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id) ON DELETE CASCADE
                    )
                """)

                # monitoring_metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS monitoring_metrics (
                        workflow_id TEXT NOT NULL,
                        agent_name TEXT NOT NULL,
                        execution_duration REAL NOT NULL,
                        status TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id) ON DELETE CASCADE
                    )
                """)
                conn.commit()
                logger.info("DB_OP: SQLite database tables initialized successfully.")
        except Exception as exc:
            logger.error("DB_OP: Failed to initialize SQLite database: %s", exc)
            raise
 
    def save_workflow(
        self,
        workflow_id: str,
        original_requirement: str,
        planner_output: dict[str, Any] | str,
        status: str = "planning",
    ) -> None:
        """Save workflow metadata to the database."""
        logger.info("DB_OP: Saving workflow %s with status '%s' to database.", workflow_id, status)
        if isinstance(planner_output, dict):
            planner_output_str = json.dumps(planner_output)
        else:
            planner_output_str = planner_output
 
        created_at = datetime.utcnow().isoformat()
 
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO workflows (workflow_id, original_requirement, planner_output, status, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(workflow_id) DO UPDATE SET
                        original_requirement=excluded.original_requirement,
                        planner_output=excluded.planner_output,
                        status=excluded.status
                    """,
                    (workflow_id, original_requirement, planner_output_str, status, created_at),
                )
                conn.commit()
                logger.info("DB_OP: Workflow %s saved successfully.", workflow_id)
        except Exception as exc:
            logger.error("DB_OP: Failed to save workflow %s: %s", workflow_id, exc)
            raise

    def update_workflow_status(self, workflow_id: str, status: str) -> None:
        """Update the status of a specific workflow."""
        logger.info("DB_OP: Updating status of workflow %s to %s", workflow_id, status)
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE workflows
                    SET status = ?
                    WHERE workflow_id = ?
                    """,
                    (status, workflow_id),
                )
                conn.commit()
                logger.info("DB_OP: Workflow %s status updated successfully.", workflow_id)
        except Exception as exc:
            logger.error("DB_OP: Failed to update status for workflow %s: %s", workflow_id, exc)
            raise

    def save_task(self, workflow_id: str, task: dict[str, Any]) -> None:
        """Save a task to the database. Supports dictionary with string or list fields."""
        task_id = task.get("id") or task.get("task_id")
        if not task_id:
            raise ValueError("Task must contain an 'id' or 'task_id' field")

        logger.info("DB_OP: Saving task %s for workflow %s to database.", task_id, workflow_id)

        title = task.get("title", "")
        description = task.get("description", "")
        task_type = task.get("type") or task.get("task_type", "feature")
        priority = task.get("priority", "medium")

        # Handle dependencies (ensure stored as JSON string)
        deps = task.get("dependencies", [])
        if isinstance(deps, list):
            deps_str = json.dumps(deps)
        else:
            deps_str = str(deps)

        # Handle acceptance criteria (ensure stored as JSON string)
        criteria = task.get("acceptance_criteria", [])
        if isinstance(criteria, list):
            criteria_str = json.dumps(criteria)
        else:
            criteria_str = str(criteria)

        estimated_effort = task.get("estimated_effort", "")
        status = task.get("status", "pending")
        file_path = task.get("file_path", "")
        gen_time = task.get("generation_time_seconds")

        now = datetime.utcnow().isoformat()

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO tasks (
                        workflow_id, task_id, title, description, task_type, priority,
                        dependencies, acceptance_criteria, estimated_effort, status,
                        file_path, generation_time_seconds, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(workflow_id, task_id) DO UPDATE SET
                        title=excluded.title,
                        description=excluded.description,
                        task_type=excluded.task_type,
                        priority=excluded.priority,
                        dependencies=excluded.dependencies,
                        acceptance_criteria=excluded.acceptance_criteria,
                        estimated_effort=excluded.estimated_effort,
                        status=excluded.status,
                        file_path=excluded.file_path,
                        generation_time_seconds=excluded.generation_time_seconds,
                        updated_at=excluded.updated_at
                    """,
                    (
                        workflow_id,
                        task_id,
                        title,
                        description,
                        task_type,
                        priority,
                        deps_str,
                        criteria_str,
                        estimated_effort,
                        status,
                        file_path,
                        gen_time,
                        now,
                        now,
                    ),
                )
                conn.commit()
                logger.info("DB_OP: Task %s saved successfully.", task_id)
        except Exception as exc:
            logger.error("DB_OP: Failed to save task %s: %s", task_id, exc)
            raise

    def get_pending_tasks(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        """Retrieve pending tasks, optionally filtered by workflow_id."""
        logger.info("DB_OP: Retrieving pending tasks. Filter workflow_id: %s", workflow_id)

        query = "SELECT * FROM tasks WHERE status = 'pending'"
        params: list[Any] = []
        if workflow_id:
            query += " AND workflow_id = ?"
            params.append(workflow_id)

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()

                tasks = []
                for row in rows:
                    task_dict = dict(row)
                    # Deserialize JSON array strings back to Python lists
                    try:
                        task_dict["dependencies"] = (
                            json.loads(row["dependencies"]) if row["dependencies"] else []
                        )
                    except Exception:
                        task_dict["dependencies"] = []

                    try:
                        task_dict["acceptance_criteria"] = (
                            json.loads(row["acceptance_criteria"])
                            if row["acceptance_criteria"]
                            else []
                        )
                    except Exception:
                        task_dict["acceptance_criteria"] = []

                    tasks.append(task_dict)

                logger.info("DB_OP: Successfully retrieved %d pending tasks.", len(tasks))
                return tasks
        except Exception as exc:
            logger.error("DB_OP: Failed to retrieve pending tasks: %s", exc)
            raise

    def update_task_status(self, workflow_id: str, task_id: str, status: str) -> None:
        """Update the status of a specific task."""
        logger.info("DB_OP: Updating status of task %s to %s in workflow %s", task_id, status, workflow_id)
        now = datetime.utcnow().isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE tasks
                    SET status = ?, updated_at = ?
                    WHERE workflow_id = ? AND task_id = ?
                    """,
                    (status, now, workflow_id, task_id),
                )
                conn.commit()
                logger.info("DB_OP: Task %s status updated successfully.", task_id)
        except Exception as exc:
            logger.error("DB_OP: Failed to update status for task %s: %s", task_id, exc)
            raise

    def save_generated_file(
        self,
        workflow_id: str,
        task_id: str,
        file_path: str,
        generation_time: float | None = None,
    ) -> None:
        """Save the generated relative file path and optional generation time, setting status to completed."""
        logger.info(
            "DB_OP: Saving generated file for task %s (workflow %s): %s (time: %s)",
            task_id,
            workflow_id,
            file_path,
            generation_time,
        )
        now = datetime.utcnow().isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE tasks
                    SET file_path = ?, generation_time_seconds = ?, status = 'completed', updated_at = ?
                    WHERE workflow_id = ? AND task_id = ?
                    """,
                    (file_path, generation_time, now, workflow_id, task_id),
                )
                conn.commit()
                logger.info(
                    "DB_OP: Generated file for task %s saved, status updated to completed.",
                    task_id,
                )
        except Exception as exc:
            logger.error("DB_OP: Failed to save generated file for task %s: %s", task_id, exc)
            raise

    def save_test_result(
        self,
        workflow_id: str,
        test_name: str,
        execution_time: float,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Save a test execution result to the database."""
        logger.info(
            "DB_OP: Saving test result for test '%s' in workflow %s (status: %s, time: %s)",
            test_name,
            workflow_id,
            status,
            execution_time,
        )
        now = datetime.utcnow().isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO test_results (
                        workflow_id, test_name, execution_time, status, error_message, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workflow_id,
                        test_name,
                        execution_time,
                        status,
                        error_message,
                        now,
                    ),
                )
                conn.commit()
                logger.info("DB_OP: Test result for '%s' saved successfully.", test_name)
        except Exception as exc:
            logger.error("DB_OP: Failed to save test result for test '%s': %s", test_name, exc)
            raise

    def save_review_issue(
        self,
        workflow_id: str,
        file_name: str,
        severity: str,
        issue_description: str,
        suggested_fix: str,
        correction_attempt: int,
    ) -> None:
        """Save a review issue to the database."""
        logger.info(
            "DB_OP: Saving review issue for file %s (severity: %s, attempt: %d)",
            file_name,
            severity,
            correction_attempt,
        )
        now = datetime.utcnow().isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO review_issues (
                        workflow_id, file_name, severity, issue_description, suggested_fix, correction_attempt, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workflow_id,
                        file_name,
                        severity,
                        issue_description,
                        suggested_fix,
                        correction_attempt,
                        now,
                    ),
                )
                conn.commit()
                logger.info("DB_OP: Review issue for '%s' saved successfully.", file_name)
        except Exception as exc:
            logger.error("DB_OP: Failed to save review issue for file '%s': %s", file_name, exc)
            raise

    def save_monitoring_metric(
        self,
        workflow_id: str,
        agent_name: str,
        execution_duration: float,
        status: str,
    ) -> None:
        """Save a monitoring metric to the database."""
        logger.info(
            "DB_OP: Saving monitoring metric for agent '%s' in workflow %s (status: %s, duration: %s)",
            agent_name,
            workflow_id,
            status,
            execution_duration,
        )
        now = datetime.utcnow().isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO monitoring_metrics (
                        workflow_id, agent_name, execution_duration, status, timestamp
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        workflow_id,
                        agent_name,
                        execution_duration,
                        status,
                        now,
                    ),
                )
                conn.commit()
                logger.info("DB_OP: Monitoring metric for agent '%s' saved successfully.", agent_name)
        except Exception as exc:
            logger.error("DB_OP: Failed to save monitoring metric for agent '%s': %s", agent_name, exc)
            raise

    def get_workflows(self) -> list[dict[str, Any]]:
        """Retrieve all workflows ordered by creation date descending."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM workflows ORDER BY created_at DESC")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as exc:
            logger.error("DB_OP: Failed to retrieve workflows: %s", exc)
            return []

    def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        """Retrieve a specific workflow by id."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM workflows WHERE workflow_id = ?", (workflow_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as exc:
            logger.error("DB_OP: Failed to retrieve workflow %s: %s", workflow_id, exc)
            return None

    def get_tasks(self, workflow_id: str) -> list[dict[str, Any]]:
        """Retrieve all tasks associated with a workflow."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM tasks WHERE workflow_id = ?", (workflow_id,))
                rows = cursor.fetchall()
                tasks = []
                for row in rows:
                    task_dict = dict(row)
                    try:
                        task_dict["dependencies"] = json.loads(row["dependencies"]) if row["dependencies"] else []
                    except Exception:
                        task_dict["dependencies"] = []
                    try:
                        task_dict["acceptance_criteria"] = json.loads(row["acceptance_criteria"]) if row["acceptance_criteria"] else []
                    except Exception:
                        task_dict["acceptance_criteria"] = []
                    tasks.append(task_dict)
                return tasks
        except Exception as exc:
            logger.error("DB_OP: Failed to retrieve tasks for workflow %s: %s", workflow_id, exc)
            return []

    def get_test_results(self, workflow_id: str) -> list[dict[str, Any]]:
        """Retrieve test results for a workflow."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM test_results WHERE workflow_id = ?", (workflow_id,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as exc:
            logger.error("DB_OP: Failed to retrieve test results for workflow %s: %s", workflow_id, exc)
            return []

    def get_review_issues(self, workflow_id: str) -> list[dict[str, Any]]:
        """Retrieve review issues for a workflow."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM review_issues WHERE workflow_id = ?", (workflow_id,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as exc:
            logger.error("DB_OP: Failed to retrieve review issues for workflow %s: %s", workflow_id, exc)
            return []

    def get_monitoring_metrics(self, workflow_id: str) -> list[dict[str, Any]]:
        """Retrieve monitoring metrics for a workflow."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM monitoring_metrics WHERE workflow_id = ?", (workflow_id,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as exc:
            logger.error("DB_OP: Failed to retrieve monitoring metrics for workflow %s: %s", workflow_id, exc)
            return []

    def get_generated_files(self, workflow_id: str) -> list[dict[str, Any]]:
        """Retrieve files that were successfully generated in the workflow (completed tasks with file_path)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT file_path, MAX(generation_time_seconds) as generation_time_seconds, status 
                    FROM tasks 
                    WHERE workflow_id = ? AND status = 'completed' AND file_path IS NOT NULL AND file_path != ''
                    GROUP BY file_path
                    """,
                    (workflow_id,)
                )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as exc:
            logger.error("DB_OP: Failed to retrieve generated files for workflow %s: %s", workflow_id, exc)
            return []


