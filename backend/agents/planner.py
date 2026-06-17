"""PlannerAgent — converts natural-language requirements into structured engineering tasks."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from llm.base_client import BaseLLMClient
from llm.gemini_client import GeminiClient
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.5-flash"


class EngineeringTask(BaseModel):
    id: str = Field(description="Stable task identifier, e.g. TASK-001")
    title: str
    description: str
    type: str
    priority: str
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    estimated_effort: str = Field(
        description="Rough effort estimate, e.g. '2h', '1d', '3d'"
    )


class EngineeringPlan(BaseModel):
    summary: str = Field(default_factory=str)
    requirements_analysis: str = Field(default_factory=str)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    tasks: list[EngineeringTask] = Field(default_factory=list)


class PlannerError(Exception):
    """Raised when planning farunils after retries or validation."""


@dataclass
class PlannerConfig:
    model: str = DEFAULT_MODEL
    temperature: float = 0.2


SYSTEM_PROMPT = """\
You are a senior software engineering planner for an AI-orchestrated SDLC workflow.

Given natural-language software requirements, produce a practical implementation plan
as structured engineering tasks suitable for downstream coder, reviewer, and tester agents.

Rules:
- Break work into a small number of actionable tasks, targeting 3–5 tasks maximum. Avoid over-splitting small tasks.
- Use stable task IDs: TASK-001, TASK-002, etc.
- List dependencies only as other task IDs that must complete first.
- Every task must have clear, testable acceptance criteria.
- Prefer vertical slices over purely technical layers when possible.
- Critical: Each task MUST represent the implementation of exactly one target file (e.g., database.py, models.py, auth.py, routes.py). Do not group multiple file creations/modifications into a single task, as the downstream coder agent can only output one file per task.
- Include assumptions and risks when requirements are ambiguous.
- Respond with valid JSON only, matching this shape:
  {
    "summary": "string",
    "requirements_analysis": "string",
    "assumptions": ["string"],
    "risks": ["string"],
    "tasks": [{
      "id": "TASK-001",
      "title": "string",
      "description": "string",
      "type": "feature|bugfix|refactor|test|docs|infra|research",
      "priority": "high|medium|low",
      "dependencies": ["TASK-000"],
      "acceptance_criteria": ["string"],
      "estimated_effort": "2h"
    }]
  }
"""


class PlannerAgent:
    """Accepts natural-language requirements and returns a structured engineering plan."""

    def __init__(
        self,
        config: PlannerConfig | None = None,
        client: BaseLLMClient | None = None,
    ) -> None:
        """Initialize the planner agent with config and the LLM client (dependency injection)."""
        self._config = config or PlannerConfig()
        # Dependency injection support: default to GeminiClient if no client is passed
        self._client = client or GeminiClient(model_name=self._config.model)

    async def plan(self, requirements: str) -> dict[str, Any]:
        """Convert requirements into a JSON-serializable engineering plan using Gemini API."""
        if not requirements or not requirements.strip():
            raise PlannerError("Requirements must be a non-empty string")

        logger.info("PlannerAgent: Requesting plan generation from Gemini API.")
        
        user_prompt = (
            "Convert the following software requirements into an engineering plan.\n\n"
            f"Requirements:\n{requirements.strip()}"
        )

        try:
            raw_response = await self._client.generate(
                prompt=user_prompt,
                system_prompt=SYSTEM_PROMPT,
                response_schema=None,
            )
            
            logger.info("PlannerAgent: Raw response from Gemini: %s", raw_response)
            payload = json.loads(raw_response)
            
            # Normalize tasks to ensure all required fields exist before validation
            if "tasks" in payload and isinstance(payload["tasks"], list):
                for task in payload["tasks"]:
                    if isinstance(task, dict):
                        task_id = task.get("id") or task.get("task_id") or "TASK-UNKNOWN"
                        # Fallback for missing/empty required fields
                        task["id"] = task_id
                        task["title"] = task.get("title") or f"Implement {task_id}"
                        task["description"] = task.get("description") or f"Description for {task['title']}"
                        task["type"] = task.get("type") or "feature"
                        task["priority"] = task.get("priority") or "medium"
                        task["dependencies"] = task.get("dependencies") or []
                        task["acceptance_criteria"] = task.get("acceptance_criteria") or [f"The task '{task['title']}' is successfully implemented."]
                        task["estimated_effort"] = task.get("estimated_effort") or "2h"
            
            engineering_plan = EngineeringPlan.model_validate(payload)
            logger.info("PlannerAgent: Plan generated and validated successfully.")
            return engineering_plan.model_dump(mode="json")
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.error("PlannerAgent: Generated response validation failed: %s", exc)
            raise PlannerError(f"Invalid plan response schema: {exc}") from exc
        except Exception as exc:
            logger.error("PlannerAgent: Plan generation failed: %s", exc)
            raise PlannerError(f"Unexpected planning error: {exc}") from exc
