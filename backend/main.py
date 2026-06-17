import os
import json
import uuid
import time
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any

from orchestrator.workflow_orchestrator import WorkflowOrchestrator
from memory.workflow_memory import WorkflowMemoryManager
from agents.monitoring import AgentMetrics
from websocket.manager import manager

app = FastAPI(title="Agentic SDLC API")

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = WorkflowOrchestrator()
memory = orchestrator.memory


@app.websocket("/ws/workflows/{workflow_id}")
async def websocket_endpoint(websocket: WebSocket, workflow_id: str):
    await manager.connect(websocket, workflow_id)
    try:
        while True:
            # Keep client socket open by receiving frames
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, workflow_id)
    except Exception:
        manager.disconnect(websocket, workflow_id)



class PlanRequest(BaseModel):
    requirements: str = Field(min_length=1)


class WorkflowRequest(BaseModel):
    requirement: str = Field(min_length=1)


# Background task for Planning phase
async def run_planning_in_background(workflow_id: str, requirement: str):
    try:
        await orchestrator.plan_workflow(workflow_id, requirement)
    except Exception as exc:
        print(f"Background planning failed for workflow {workflow_id}: {exc}")
        try:
            memory.update_workflow_status(workflow_id, "failed")
        except Exception:
            pass


# Background task for Coding, Testing, Review and Validation phases
async def run_execution_in_background(workflow_id: str):
    try:
        wf = memory.get_workflow(workflow_id)
        if not wf:
            raise ValueError(f"Workflow {workflow_id} not found in database.")

        plan_data = {}
        if wf["planner_output"]:
            try:
                plan_data = json.loads(wf["planner_output"])
            except Exception:
                plan_data = {}

        metrics_rows = memory.get_monitoring_metrics(workflow_id)
        agent_metrics = []
        planner_row = next((r for r in metrics_rows if r["agent_name"] == "PlannerAgent"), None)

        planning_duration = 0.0
        total_start = time.perf_counter()
        if planner_row:
            planning_duration = planner_row["execution_duration"]
            total_start -= planning_duration
            agent_metrics.append(AgentMetrics(
                agent_name="PlannerAgent",
                start_time=planner_row["timestamp"],
                end_time=planner_row["timestamp"],
                duration=planning_duration,
                status=planner_row["status"],
                retry_count=0,
                generated_files_count=0
            ))

        await orchestrator.execute_approved_workflow(
            workflow_id=workflow_id,
            plan_data=plan_data,
            agent_metrics_list=agent_metrics,
            total_start=total_start,
            planning_duration=planning_duration
        )
    except Exception as exc:
        print(f"Background execution failed for workflow {workflow_id}: {exc}")
        try:
            memory.update_workflow_status(workflow_id, "failed")
        except Exception:
            pass


@app.post("/plan")
async def create_plan(request: PlanRequest) -> dict:
    """Legacy endpoint for planning validation checks."""
    try:
        return await orchestrator.planner.plan(request.requirements)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/workflow")
async def create_workflow(request: WorkflowRequest, background_tasks: BackgroundTasks) -> dict:
    """Create a new workflow and start the planning phase in a background task."""
    workflow_id = f"WF-{uuid.uuid4().hex[:8].upper()}"
    try:
        memory.save_workflow(workflow_id, request.requirement, "", status="planning")
        background_tasks.add_task(run_planning_in_background, workflow_id, request.requirement)
        return {
            "workflow_id": workflow_id,
            "status": "planning",
            "requirement": request.requirement,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create workflow: {exc}")


@app.post("/workflow/{id}/approve")
async def approve_workflow(id: str, background_tasks: BackgroundTasks) -> dict:
    """Approve planning output and trigger backend workflow execution in a background task."""
    wf = memory.get_workflow(id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    if wf["status"] not in ("awaiting_approval", "cancelled", "failed"):
        raise HTTPException(status_code=400, detail=f"Workflow is in '{wf['status']}' state and cannot be approved")
    
    try:
        memory.update_workflow_status(id, "approved")
        memory.update_workflow_status(id, "in_progress")
        background_tasks.add_task(run_execution_in_background, id)
        return {
            "workflow_id": id,
            "status": "in_progress",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to approve workflow: {exc}")


@app.post("/workflow/{id}/reject")
async def reject_workflow(id: str) -> dict:
    """Reject planning output and terminate workflow."""
    wf = memory.get_workflow(id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    try:
        memory.update_workflow_status(id, "cancelled")
        return {
            "workflow_id": id,
            "status": "cancelled",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to reject workflow: {exc}")


@app.get("/workflows")
async def get_workflows() -> list[dict]:
    """Retrieve history of all workflows."""
    workflows = memory.get_workflows()
    parsed_workflows = []
    for wf in workflows:
        wf_dict = dict(wf)
        if wf_dict["planner_output"]:
            try:
                wf_dict["planner_output"] = json.loads(wf_dict["planner_output"])
            except Exception:
                pass
        parsed_workflows.append(wf_dict)
    return parsed_workflows


@app.get("/workflow/{id}")
async def get_workflow(id: str) -> dict:
    """Retrieve details for a single workflow."""
    wf = memory.get_workflow(id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    wf_dict = dict(wf)
    if wf_dict["planner_output"]:
        try:
            wf_dict["planner_output"] = json.loads(wf_dict["planner_output"])
        except Exception:
            pass
    return wf_dict


@app.get("/workflow/{id}/tasks")
async def get_workflow_tasks(id: str) -> list[dict]:
    """Retrieve tasks for a workflow."""
    return memory.get_tasks(id)


@app.get("/workflow/{id}/metrics")
async def get_workflow_metrics(id: str) -> dict:
    """Retrieve test results, review issues, and monitoring metrics for a workflow."""
    return {
        "test_results": memory.get_test_results(id),
        "review_issues": memory.get_review_issues(id),
        "monitoring_metrics": memory.get_monitoring_metrics(id)
    }


@app.get("/workflow/{id}/files")
async def get_workflow_files(id: str) -> list[dict]:
    """Retrieve list of generated files for a workflow."""
    return memory.get_generated_files(id)


@app.get("/file-content")
async def get_file_content(path: str = Query(..., min_length=1)) -> dict:
    """Retrieve source code text content of a generated file."""
    # Ensure path contains standard relative naming conventions
    backend_dir = os.path.abspath(os.path.dirname(__file__))
    resolved_path = os.path.abspath(os.path.join(backend_dir, path))
    allowed_base = os.path.join(backend_dir, "generated_projects")

    # Validate directory containment to prevent path traversal issues
    if not resolved_path.startswith(allowed_base):
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(resolved_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {
            "file_name": os.path.basename(resolved_path),
            "path": path,
            "content": content
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read file content: {exc}")
