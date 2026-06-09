"""PlannerAgent — converts natural-language requirements into structured engineering tasks."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 1.0
RETRYABLE_EXCEPTIONS = (APIConnectionError, APITimeoutError, RateLimitError)


class TaskType(str, Enum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    TEST = "test"
    DOCS = "docs"
    INFRA = "infra"
    RESEARCH = "research"


class TaskPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EngineeringTask(BaseModel):
    id: str = Field(description="Stable task identifier, e.g. TASK-001")
    title: str
    description: str
    type: TaskType
    priority: TaskPriority
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(min_length=1)
    estimated_effort: str = Field(
        description="Rough effort estimate, e.g. '2h', '1d', '3d'"
    )


class EngineeringPlan(BaseModel):
    summary: str
    requirements_analysis: str
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    tasks: list[EngineeringTask] = Field(min_length=1)


class PlannerError(Exception):
    """Raised when planning fails after retries or validation."""


@dataclass
class PlannerConfig:
    model: str = DEFAULT_MODEL
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY
    temperature: float = 0.2
    api_key: str | None = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))


SYSTEM_PROMPT = """\
You are a senior software engineering planner for an AI-orchestrated SDLC workflow.

Given natural-language software requirements, produce a practical implementation plan
as structured engineering tasks suitable for downstream coder, reviewer, and tester agents.

Rules:
- Break work into small, independently actionable tasks (typically 3–12).
- Use stable task IDs: TASK-001, TASK-002, etc.
- List dependencies only as other task IDs that must complete first.
- Every task must have clear, testable acceptance criteria.
- Prefer vertical slices over purely technical layers when possible.
- Include assumptions and risks when requirements are ambiguous.
"""


class OpenAIPlannerClient:
    """Thin async wrapper around the OpenAI chat completions API."""

    def __init__(self, config: PlannerConfig) -> None:
        if not config.api_key:
            raise PlannerError("OPENAI_API_KEY is not set")
        self._config = config
        self._client = AsyncOpenAI(api_key=config.api_key)

    async def generate_plan(self, requirements: str) -> EngineeringPlan:
        schema = EngineeringPlan.model_json_schema()
        response = await self._client.chat.completions.create(
            model=self._config.model,
            temperature=self._config.temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Convert the following software requirements into an engineering plan.\n\n"
                        f"Requirements:\n{requirements.strip()}"
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "engineering_plan",
                    "strict": True,
                    "schema": schema,
                },
            },
        )

        raw = response.choices[0].message.content
        if not raw:
            raise PlannerError("OpenAI returned an empty response")

        try:
            payload = json.loads(raw)
            return EngineeringPlan.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise PlannerError(f"Invalid plan JSON from model: {exc}") from exc


async def _with_retry(
    fn: Any,
    *,
    max_retries: int,
    base_delay: float,
    label: str,
) -> EngineeringPlan:
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return await fn()
        except RETRYABLE_EXCEPTIONS as exc:
            last_error = exc
            if attempt == max_retries:
                break
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "%s failed (attempt %d/%d): %s — retrying in %.1fs",
                label,
                attempt,
                max_retries,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
        except APIStatusError as exc:
            if exc.status_code and exc.status_code >= 500 and attempt < max_retries:
                last_error = exc
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "%s server error %s (attempt %d/%d) — retrying in %.1fs",
                    label,
                    exc.status_code,
                    attempt,
                    max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
                continue
            raise PlannerError(f"OpenAI API error: {exc}") from exc
        except PlannerError:
            raise
        except Exception as exc:
            raise PlannerError(f"Unexpected planning error: {exc}") from exc

    raise PlannerError(
        f"{label} failed after {max_retries} attempts: {last_error}"
    ) from last_error


class PlannerAgent:
    """Accepts natural-language requirements and returns a structured engineering plan."""

    def __init__(
        self,
        config: PlannerConfig | None = None,
        client: OpenAIPlannerClient | None = None,
    ) -> None:
        self._config = config or PlannerConfig()
        self._client = client or OpenAIPlannerClient(self._config)

    async def plan(self, requirements: str) -> dict[str, Any]:
        """Convert requirements into a JSON-serializable engineering plan."""
        if not requirements or not requirements.strip():
            raise PlannerError("Requirements must be a non-empty string")

        engineering_plan = await _with_retry(
            lambda: self._client.generate_plan(requirements),
            max_retries=self._config.max_retries,
            base_delay=self._config.retry_base_delay,
            label="PlannerAgent",
        )
        return engineering_plan.model_dump(mode="json")
