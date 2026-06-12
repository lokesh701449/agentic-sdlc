"""CodingAgent — generates implementation code from structured engineering tasks."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from llm.base_client import BaseLLMClient
from llm.gemini_client import GeminiClient
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"


class CodingResult(BaseModel):
    filename: str = Field(
        description="The relative file path or name where the code should be saved, e.g., 'auth.py' or 'db/connection.py'"
    )
    code: str = Field(
        description="The complete, self-contained, executable Python code implementation"
    )


class CoderError(Exception):
    """Raised when code generation or file writing fails."""


@dataclass
class CoderConfig:
    model: str = DEFAULT_MODEL
    output_dir: str = field(
        default_factory=lambda: os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "generated_projects")
        )
    )


SYSTEM_PROMPT = """\
You are a senior backend software engineering coder for an AI-orchestrated SDLC workflow.

Given a structured engineering task description and acceptance criteria, produce the complete, production-ready Python implementation.

Rules:
- Generate complete, clean, self-contained, and executable Python code.
- Include all necessary library imports.
- Prioritize MVP simplicity over complex structures, but avoid placeholders or empty stub/todo comments.
- Be extremely concise. Keep the code simple, compact, and minimal to avoid output truncation. Avoid long comments, verbose documentation strings, or redundant helper routines.
- Determine an appropriate relative file path/name for the file (e.g. "auth.py" or "db/connection.py").
- Critical: Do NOT use the `await` keyword outside of functions declared with `async def`. Note that standard calls to bcrypt, passlib, and python-jose (JWT encoding/decoding) are synchronous; do NOT use `await` when calling them.
- Critical: Do NOT import local files or modules (like `app`, `config`, etc.) that are not standard Python libraries or standard third-party packages (like fastapi, jose, bcrypt, passlib, sqlite3, or httpx), unless they are explicitly defined in the task description or are sibling modules.
- Critical: When creating unit tests, ensure that you import functions from the exact filename where they are defined, matching standard Python module namespaces.
- Critical: In Python, ensure that any lambda functions are written entirely on a single line. Do not split lambda declarations across lines to avoid syntax errors.
- Respond with valid JSON only, matching this shape:
  {
    "filename": "string",
    "code": "string"
  }
"""


class CodingAgent:
    """Accepts structured engineering tasks, generates code, and saves to files."""

    def __init__(
        self,
        config: CoderConfig | None = None,
        client: BaseLLMClient | None = None,
    ) -> None:
        """Initialize CoderConfig and BaseLLMClient dependency injection."""
        self._config = config or CoderConfig()
        self._client = client or GeminiClient(model_name=self._config.model)

    def has_cached_file(self, task: dict[str, Any] | BaseModel) -> str | None:
        """Check if a generated file for the task already exists in output_dir.

        Returns the resolved absolute path of the file if it exists, otherwise None.
        """
        if isinstance(task, dict):
            title = task.get("title", "")
            description = task.get("description", "")
            acceptance_criteria = task.get("acceptance_criteria", [])
        else:
            title = getattr(task, "title", "")
            description = getattr(task, "description", "")
            acceptance_criteria = getattr(task, "acceptance_criteria", [])

        if not title or not description:
            return None

        # Look for words containing .py
        import re
        text_to_search = f"{title} {description} " + " ".join(acceptance_criteria)
        found_files = re.findall(r'[a-zA-Z0-9_\-\\/]+\.py', text_to_search)

        # Clean filenames and check existence
        for f in found_files:
            f_clean = f.strip("`'\"()[]{}*#,;:")
            if f_clean and f_clean.endswith(".py"):
                sanitized_filename = os.path.normpath(f_clean).lstrip(os.path.sep)
                resolved_path = os.path.abspath(os.path.join(self._config.output_dir, sanitized_filename))
                
                # Verify the path is within self._config.output_dir and exists on disk
                if resolved_path.startswith(os.path.abspath(self._config.output_dir)) and os.path.isfile(resolved_path):
                    return resolved_path
        return None

    async def code_task(self, task: dict[str, Any] | BaseModel) -> dict[str, Any]:
        """Generate implementation code from a task using Gemini and save it to the output directory."""
        if isinstance(task, dict):
            task_id = task.get("id") or task.get("task_id") or "UNKNOWN"
            title = task.get("title", "")
            description = task.get("description", "")
            task_type = task.get("type") or task.get("task_type") or "feature"
            acceptance_criteria = task.get("acceptance_criteria", [])
        else:
            # Assume it's a Pydantic model (like EngineeringTask) or has attribute access
            task_id = getattr(task, "id", None) or getattr(task, "task_id", None) or "UNKNOWN"
            title = getattr(task, "title", "")
            description = getattr(task, "description", "")
            task_type = getattr(task, "type", None) or getattr(task, "task_type", "feature")
            acceptance_criteria = getattr(task, "acceptance_criteria", [])

        if not title or not description:
            raise CoderError("Task title and description must be non-empty")

        # Check caching
        cached_file = self.has_cached_file(task)
        if cached_file:
            backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            relative_file_path = os.path.relpath(cached_file, start=backend_dir)
            logger.info(
                "CodingAgent: Task caching hit for task %s (%s). Reusing existing file: %s",
                task_id,
                title,
                relative_file_path,
            )
            return {
                "task_id": task_id,
                "status": "success",
                "file_path": relative_file_path,
                "generation_time_seconds": 0.0,
                "cached": True,
            }

        logger.info("CodingAgent: Starting code generation for task %s (%s)", task_id, title)
        start_time = time.perf_counter()

        # Dynamic search for existing sibling files to provide implementation context (e.g. for unit tests)
        existing_file_context = ""
        try:
            output_dir = self._config.output_dir
            if os.path.exists(output_dir):
                for filename in os.listdir(output_dir):
                    file_path = os.path.join(output_dir, filename)
                    if os.path.isfile(file_path) and filename.endswith(".py"):
                        name_without_ext = os.path.splitext(filename)[0]
                        # If filename (e.g. 'auth') is mentioned in title/description/criteria, read it
                        if (
                            name_without_ext in title.lower()
                            or name_without_ext in description.lower()
                            or any(name_without_ext in c.lower() for c in acceptance_criteria)
                        ):
                            logger.info("CodingAgent: Including existing file context from %s", filename)
                            with open(file_path, "r", encoding="utf-8") as f:
                                content = f.read()
                            existing_file_context += f"\nExisting '{filename}' file content:\n```python\n{content}\n```\n"
        except Exception as exc:
            logger.warning("CodingAgent: Failed to read existing file context: %s", exc)

        criteria_list = "\n".join(f"- {c}" for c in acceptance_criteria)
        user_prompt = (
            f"Implement the following engineering task:\n\n"
            f"Task ID: {task_id}\n"
            f"Title: {title}\n"
            f"Type: {task_type}\n"
            f"Description:\n{description}\n\n"
            f"Acceptance Criteria:\n{criteria_list}"
        )

        if existing_file_context:
            user_prompt += f"\n\nContext on existing project files:\n{existing_file_context}"

        try:
            logger.info("CodingAgent: Calling Gemini API client to generate code.")
            raw_response = await self._client.generate(
                prompt=user_prompt,
                system_prompt=SYSTEM_PROMPT,
                response_schema=None,
            )
            
            # Extract JSON payload, removing potential markdown wrappers
            cleaned_response = raw_response.strip()
            if cleaned_response.startswith("```"):
                lines = cleaned_response.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned_response = "\n".join(lines).strip()

            payload = json.loads(cleaned_response)
            coding_result = CodingResult.model_validate(payload)
            
            filename = coding_result.filename
            code = coding_result.code

            # Determine file path and sanitize
            sanitized_filename = os.path.normpath(filename).lstrip(os.path.sep)
            if sanitized_filename.startswith("..") or os.path.isabs(sanitized_filename):
                # Ensure the path doesn't escape our output directory
                resolved_path = os.path.abspath(os.path.join(self._config.output_dir, sanitized_filename))
                if not resolved_path.startswith(os.path.abspath(self._config.output_dir)):
                    raise CoderError(f"Generated filename escapes output directory: {filename}")
            else:
                resolved_path = os.path.abspath(os.path.join(self._config.output_dir, sanitized_filename))

            # Write code to file asynchronously (off the main event thread)
            logger.info("CodingAgent: Saving generated file to %s", resolved_path)
            def _write_file() -> None:
                dir_path = os.path.dirname(resolved_path)
                os.makedirs(dir_path, exist_ok=True)
                with open(resolved_path, "w", encoding="utf-8") as f:
                    f.write(code)

            await asyncio.to_thread(_write_file)
            logger.info("CodingAgent: Successfully saved file for task %s", task_id)

            generation_time_seconds = time.perf_counter() - start_time
            
            # Resolve relative file path relative to backend/ base directory dynamically
            backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            relative_file_path = os.path.relpath(resolved_path, start=backend_dir)

            logger.info(
                "CodingAgent: Code generation and save completed for task %s in %.2f seconds. File: %s",
                task_id,
                generation_time_seconds,
                relative_file_path,
            )

            return {
                "task_id": task_id,
                "status": "success",
                "file_path": relative_file_path,
                "generation_time_seconds": generation_time_seconds,
            }

        except Exception as exc:
            generation_time_seconds = time.perf_counter() - start_time
            logger.error("CodingAgent: Failed to generate/save code for task %s after %.2f seconds: %s", task_id, generation_time_seconds, exc)
            return {
                "task_id": task_id,
                "status": "failed",
                "file_path": "",
                "generation_time_seconds": generation_time_seconds,
                "error": str(exc),
            }
