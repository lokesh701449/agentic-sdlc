"""WorkflowOrchestrator — coordinates planning, persistence, code generation, and validation."""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import sys
import time
import uuid
from typing import Any

from agents.coder import CodingAgent
from agents.planner import PlannerAgent
from llm.gemini_client import GeminiClient
from memory.workflow_memory import WorkflowMemoryManager

logger = logging.getLogger(__name__)


def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
    """Safely get a value from a dict or an object attribute (Pydantic model)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        return getattr(obj, key, default)
    except Exception:
        return default


class WorkflowOrchestrator:
    """Coordinates the end-to-end SDLC pipeline."""

    def __init__(
        self,
        planner: PlannerAgent | None = None,
        coder: CodingAgent | None = None,
        memory: WorkflowMemoryManager | None = None,
    ) -> None:
        """Initialize agents and database memory manager with dynamic path resolution."""
        # Use a shared GeminiClient instance for dependency injection
        client = GeminiClient()
        self.planner = planner or PlannerAgent(client=client)
        self.coder = coder or CodingAgent(client=client)
        self.memory = memory or WorkflowMemoryManager()

    def _print_formatted_plan(self, plan: Any) -> None:
        """Helper to format and print the workflow plan in plain console format."""
        summary = _safe_get(plan, "summary") or "No summary provided"
        req_analysis = _safe_get(plan, "requirements_analysis") or "No requirements analysis provided"
        assumptions = _safe_get(plan, "assumptions") or []
        risks = _safe_get(plan, "risks") or []
        tasks = _safe_get(plan, "tasks") or []

        print("\n" + "=" * 80)
        print("PLANNED WORKFLOW")
        print("================")
        print("\n" + "=" * 50)
        print("WORKFLOW PLAN SUMMARY")
        print("=====================")
        print(f"\nSummary:\n{summary}\n")
        print(f"Requirements Analysis:\n{req_analysis}\n")
        
        print("Assumptions:\n")
        if assumptions:
            for item in assumptions:
                print(f"* {item}")
        else:
            print("No assumptions provided")
        print()

        print("Risks:\n")
        if risks:
            for item in risks:
                print(f"* {item}")
        else:
            print("No risks provided")
        print()

        print("=" * 50)
        print("TASKS")
        print("=====")
        print()

        for t in tasks:
            t_id = _safe_get(t, "id") or _safe_get(t, "task_id") or "UNKNOWN-TASK"
            title = _safe_get(t, "title") or "No title provided"
            dependencies = _safe_get(t, "dependencies") or []
            acceptance_criteria = _safe_get(t, "acceptance_criteria") or []

            print(f"[{t_id}]")
            print(f"Title: {title}")
            
            dep_str = ", ".join(dependencies) if dependencies else "None"
            print(f"Dependencies: {dep_str}\n")

            print("Acceptance Criteria:\n")
            if acceptance_criteria:
                for ac in acceptance_criteria:
                    print(f"* {ac}")
            else:
                print("No acceptance criteria provided")
            print("\n---")
        print()
        print("=" * 80)
        print("END OF PLAN")
        print("===========")
        print()


    def _validate_module(self, relative_path: str) -> bool:
        """Dynamically import the generated module to validate that it executes successfully."""
        if not relative_path.endswith(".py"):
            logger.info("VALIDATION: Skipping import check for non-python file: %s", relative_path)
            return True

        # Resolve path relative to backend folder
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        abs_path = os.path.abspath(os.path.join(backend_dir, relative_path))

        if not os.path.exists(abs_path):
            logger.error("VALIDATION: File does not exist at path: %s", abs_path)
            return False

        module_name = os.path.splitext(os.path.basename(abs_path))[0]
        logger.info("VALIDATION: Running dynamic import runtime check on module: %s", module_name)

        # Temporarily append the module directory to sys.path to allow internal/sibling imports
        module_dir = os.path.dirname(abs_path)
        added_to_path = False
        if module_dir not in sys.path:
            sys.path.insert(0, module_dir)
            added_to_path = True

        temp_module_name = f"temp_validation_{uuid.uuid4().hex}"
        try:
            # Load spec from file location
            spec = importlib.util.spec_from_file_location(module_name, abs_path)
            if spec is None or spec.loader is None:
                logger.error("VALIDATION: Could not build import spec/loader for %s", abs_path)
                return False

            # Create module and add to sys.modules under temp namespace
            module = importlib.util.module_from_spec(spec)
            sys.modules[temp_module_name] = module

            # Execute module code (this will trigger global scope checks)
            spec.loader.exec_module(module)
            logger.info("VALIDATION: Module %s passed runtime validation successfully.", module_name)
            return True
        except Exception as exc:
            logger.error("VALIDATION: Module %s failed runtime validation: %s", module_name, exc)
            return False
        finally:
            sys.modules.pop(temp_module_name, None)
            if added_to_path:
                try:
                    sys.path.remove(module_dir)
                except ValueError:
                    pass

    def _topological_sort(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort tasks topologically using DFS to ensure dependency order is respected."""
        task_map = {t.get("id") or t.get("task_id"): t for t in tasks}
        visited = set()
        temp_visited = set()
        sorted_tasks = []

        def visit(task_id: str) -> None:
            if task_id in temp_visited:
                logger.warning("ORCHESTRATOR: Dependency cycle detected for task: %s. Continuing anyway.", task_id)
                return
            if task_id not in visited:
                temp_visited.add(task_id)
                task = task_map.get(task_id)
                if task:
                    deps = task.get("dependencies", [])
                    for dep in deps:
                        # Ensure dep exists in graph, otherwise skip or execute first
                        if dep in task_map:
                            visit(dep)
                temp_visited.remove(task_id)
                visited.add(task_id)
                if task:
                    sorted_tasks.append(task)

        for t in tasks:
            tid = t.get("id") or t.get("task_id")
            if tid:
                visit(tid)

        return sorted_tasks

    async def run_workflow(self, requirement: str) -> dict[str, Any]:
        """Execute the end-to-end orchestration pipeline from requirement to validated files."""
        workflow_id = f"WF-{uuid.uuid4().hex[:8].upper()}"
        logger.info("ORCHESTRATOR: Starting new workflow %s", workflow_id)
        
        # Save initial workflow state in database as 'planning'
        try:
            self.memory.save_workflow(workflow_id, requirement, "", status="planning")
        except Exception as exc:
            logger.warning("ORCHESTRATOR: Failed to save initial workflow state in DB: %s", exc)
        
        total_start = time.perf_counter()
        
        # Step 1: Planning
        logger.info("ORCHESTRATOR: Starting planning phase for workflow %s", workflow_id)
        plan_start = time.perf_counter()
        planner_error = None
        plan = None
        
        try:
            logger.info("ORCHESTRATOR: Throttling Gemini API. Sleeping for 5 seconds before planning request...")
            await asyncio.sleep(5)
            plan = await self.planner.plan(requirement)
            planning_duration = time.perf_counter() - plan_start
            logger.info("ORCHESTRATOR: Planning phase completed in %.2f seconds", planning_duration)
        except Exception as exc:
            planning_duration = time.perf_counter() - plan_start
            planner_error = str(exc)
            logger.error("ORCHESTRATOR: Planning phase failed: %s", exc)

        if planner_error or not plan:
            total_duration = time.perf_counter() - total_start
            try:
                self.memory.update_workflow_status(workflow_id, "failed")
            except Exception:
                pass
            return {
                "workflow_id": workflow_id,
                "status": "failed",
                "planning_duration": planning_duration,
                "coding_duration": 0.0,
                "total_duration": total_duration,
                "tasks": [],
                "error": f"Planning phase failed: {planner_error}",
            }

        # Temporarily suppress INFO-level logs to reduce noise during approval phase
        root_logger = logging.getLogger()
        orig_level = root_logger.level
        root_logger.setLevel(logging.WARNING)

        try:
            # Display the plan in the requested console format immediately after PlannerAgent completes
            self._print_formatted_plan(plan)

            # Add temporary execution pause to inspect plan
            input("\nPRESS ENTER TO CONTINUE TO APPROVAL...")

            # Convert plan to dict for database saving and downstream task compatibility
            if hasattr(plan, "model_dump"):
                plan_data = plan.model_dump()
            elif hasattr(plan, "dict"):
                plan_data = plan.dict()
            elif isinstance(plan, dict):
                plan_data = plan
            else:
                plan_data = plan

            # Step 2: Persist workflow & tasks in DB with status 'awaiting_approval'
            # (Note: any persistence log outputs are suppressed because level is set to WARNING)
            self.memory.save_workflow(workflow_id, requirement, plan_data, status="awaiting_approval")
            tasks = _safe_get(plan_data, "tasks") or []
            for task in tasks:
                self.memory.save_task(workflow_id, task)

            # Prompt for human approval gate
            approval = input("Approve plan? (yes/no): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            approval = "no"
        finally:
            # Restore original logging level for downstream execution
            root_logger.setLevel(orig_level)

        if approval not in ("yes", "y"):
            logger.warning("ORCHESTRATOR: Plan rejected/cancelled by user. Terminating workflow.")
            try:
                self.memory.update_workflow_status(workflow_id, "cancelled")
            except Exception as exc:
                logger.error("ORCHESTRATOR: Failed to update status to cancelled: %s", exc)
            total_duration = time.perf_counter() - total_start
            return {
                "workflow_id": workflow_id,
                "status": "cancelled",
                "planning_duration": planning_duration,
                "coding_duration": 0.0,
                "total_duration": total_duration,
                "tasks": [],
                "error": "Plan rejected/cancelled by user",
            }

        # User approved the plan
        logger.info("ORCHESTRATOR: Plan approved by user. Transitioning status to approved.")
        try:
            self.memory.update_workflow_status(workflow_id, "approved")
            # Transition to in_progress before running coding tasks
            self.memory.update_workflow_status(workflow_id, "in_progress")
        except Exception as exc:
            logger.warning("ORCHESTRATOR: Failed to update DB state to approved/in_progress: %s", exc)

        # Step 3: Coding and Validation phase
        logger.info("ORCHESTRATOR: Starting coding and validation phase for workflow %s", workflow_id)
        coding_start = time.perf_counter()
        
        # Sort tasks by dependency order
        execution_order = self._topological_sort(tasks)
        logger.info(
            "ORCHESTRATOR: Sorted execution order: %s", 
            [t.get("id") or t.get("task_id") for t in execution_order]
        )

        task_results = []
        workflow_failed = False
        
        for task in execution_order:
            task_id = task.get("id") or task.get("task_id")
            logger.info("ORCHESTRATOR: Processing task %s", task_id)
            
            # Update task status to in_progress in DB
            self.memory.update_task_status(workflow_id, task_id, "in_progress")
            
            # Check if task is cached before doing LLM generation and throttling delay
            cached_path = self.coder.has_cached_file(task)
            if cached_path:
                backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                relative_file_path = os.path.relpath(cached_path, start=backend_dir)
                logger.info(
                    "ORCHESTRATOR: Task caching hit for task %s. Reusing existing file: %s",
                    task_id,
                    relative_file_path
                )
                
                # Perform dynamic import validation for the cached file
                logger.info("ORCHESTRATOR: Invoking runtime validation for cached module %s", relative_file_path)
                valid = self._validate_module(relative_file_path)
                if valid:
                    # Save generated file metadata (updates status to completed in DB)
                    self.memory.save_generated_file(workflow_id, task_id, relative_file_path, 0.0)
                    task_results.append({
                        "task_id": task_id,
                        "status": "completed",
                        "file_path": relative_file_path,
                        "generation_time_seconds": 0.0,
                        "cached": True
                    })
                    logger.info("ORCHESTRATOR: Task %s successfully completed using cache and validated.", task_id)
                else:
                    self.memory.update_task_status(workflow_id, task_id, "failed")
                    task_results.append({
                        "task_id": task_id,
                        "status": "failed",
                        "file_path": relative_file_path,
                        "generation_time_seconds": 0.0,
                        "error": "Runtime validation failed for cached file"
                    })
                    workflow_failed = True
                    logger.error("ORCHESTRATOR: Cached task %s failed dynamic runtime validation check.", task_id)
                continue

            # Sleep 5 seconds before CodingAgent LLM call to throttle requests
            logger.info("ORCHESTRATOR: Throttling Gemini API. Sleeping for 5 seconds before code generation...")
            await asyncio.sleep(5)
            
            try:
                # Invoke CodingAgent
                coder_result = await self.coder.code_task(task)
            except Exception as exc:
                logger.error("ORCHESTRATOR: Unexpected error running CodingAgent for task %s: %s", task_id, exc)
                coder_result = {
                    "task_id": task_id,
                    "status": "failed",
                    "file_path": "",
                    "generation_time_seconds": 0.0,
                    "error": str(exc)
                }
            
            status = coder_result.get("status", "failed")
            relative_path = coder_result.get("file_path", "")
            gen_time = coder_result.get("generation_time_seconds", 0.0)
            
            if status == "success" and relative_path:
                # Dynamic import validation
                logger.info("ORCHESTRATOR: Invoking runtime validation for %s", relative_path)
                valid = self._validate_module(relative_path)
                if valid:
                    # Save generated file metadata (this updates status to completed in DB)
                    self.memory.save_generated_file(workflow_id, task_id, relative_path, gen_time)
                    task_results.append({
                        "task_id": task_id,
                        "status": "completed",
                        "file_path": relative_path,
                        "generation_time_seconds": gen_time
                    })
                    logger.info("ORCHESTRATOR: Task %s successfully completed and validated.", task_id)
                else:
                    self.memory.update_task_status(workflow_id, task_id, "failed")
                    task_results.append({
                        "task_id": task_id,
                        "status": "failed",
                        "file_path": relative_path,
                        "generation_time_seconds": gen_time,
                        "error": "Runtime validation failed"
                    })
                    workflow_failed = True
                    logger.error("ORCHESTRATOR: Task %s failed dynamic runtime validation check.", task_id)
            else:
                self.memory.update_task_status(workflow_id, task_id, "failed")
                task_results.append({
                    "task_id": task_id,
                    "status": "failed",
                    "file_path": "",
                    "generation_time_seconds": gen_time,
                    "error": coder_result.get("error", "Code generation failed")
                })
                workflow_failed = True
                logger.error("ORCHESTRATOR: Task %s failed code generation.", task_id)

        coding_duration = time.perf_counter() - coding_start
        total_duration = time.perf_counter() - total_start
        
        final_status = "failed" if workflow_failed else "completed"
        logger.info(
            "ORCHESTRATOR: Workflow %s execution finished with status: %s (Total time: %.2f seconds)",
            workflow_id,
            final_status,
            total_duration
        )

        try:
            self.memory.update_workflow_status(workflow_id, final_status)
        except Exception as exc:
            logger.error("ORCHESTRATOR: Failed to update final workflow status in DB: %s", exc)

        return {
            "workflow_id": workflow_id,
            "status": final_status,
            "planning_duration": planning_duration,
            "coding_duration": coding_duration,
            "total_duration": total_duration,
            "tasks": task_results,
            "error": "One or more tasks failed execution/validation" if workflow_failed else None,
        }
