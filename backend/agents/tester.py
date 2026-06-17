"""TesterAgent — generates pytest cases and executes them, returning structured results."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from llm.base_client import BaseLLMClient
from llm.gemini_client import GeminiClient
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.5-flash"


class TestStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class TestResult(BaseModel):
    test_name: str
    status: TestStatus
    execution_time: float
    error_message: str | None = None


class TestSuite(BaseModel):
    workflow_id: str
    tests: list[TestResult] = Field(default_factory=list)
    passed_count: int = 0
    failed_count: int = 0
    stdout: str = ""
    stderr: str = ""
    total_duration: float = 0.0
    feedback: str | None = None


class TestGenerationResult(BaseModel):
    test_filename: str = Field(
        description="The relative filename for the test file, starting with 'test_' and ending with '.py', e.g. 'test_auth.py'"
    )
    code: str = Field(
        description="The complete, self-contained, executable pytest code implementation"
    )


class TesterError(Exception):
    """Raised when test generation or execution fails."""


@dataclass
class TesterConfig:
    model: str = DEFAULT_MODEL
    output_dir: str = field(
        default_factory=lambda: os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "generated_projects")
        )
    )
    test_dir: str = field(
        default_factory=lambda: os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "generated_projects", "tests")
        )
    )


SYSTEM_PROMPT = """\
You are a senior backend software engineering tester for an AI-orchestrated SDLC workflow.

Given a Python code file and its path, generate a comprehensive suite of pytest test cases.

Rules:
- Generate complete, clean, self-contained, and executable Python code using pytest.
- Include all necessary library imports.
- Make sure to import the code elements being tested from the correct module filename. Note that the generated code files are located in the parent directory of the tests folder. Since they are sibling modules in the Python search path, you should import them using absolute imports, e.g. `from <module_name> import ...` or `import <module_name>`. Do NOT use relative imports (e.g. `from ..<module_name> import ...`).
- If the file is a FastAPI service/application or defines FastAPI routes, use `fastapi.testclient.TestClient` for testing.
- Include edge cases, success cases, failure cases, and input validation checks.
- Be extremely concise. Keep the code simple, compact, and minimal to avoid output truncation. Avoid long comments or redundant helper routines.
- Determine an appropriate relative test filename, starting with "test_" and ending with ".py", e.g. "test_auth.py" or "test_db.py".
- Respond with valid JSON only, matching this shape:
  {
    "test_filename": "string",
    "code": "string"
  }
"""


class TesterAgent:
    """Accepts generated code files, generates pytest cases, saves them, executes them, and returns structured results."""

    def __init__(
        self,
        config: TesterConfig | None = None,
        client: BaseLLMClient | None = None,
    ) -> None:
        """Initialize TesterConfig and BaseLLMClient dependency injection."""
        self._config = config or TesterConfig()
        self._client = client or GeminiClient(model_name=self._config.model)

    async def generate_tests(self, code_files: list[str], workflow_id: str) -> list[str]:
        """Generate test files for the given list of code files using Gemini.

        Saves them to self._config.test_dir. Returns the list of saved test file relative paths.
        """
        logger.info("TESTING_AGENT: test generation started")
        generated_test_paths = []
        os.makedirs(self._config.test_dir, exist_ok=True)

        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        for file_path in code_files:
            if not file_path.endswith(".py"):
                logger.info("TESTING_AGENT: Skipping test generation for non-python file: %s", file_path)
                continue

            abs_code_path = os.path.abspath(os.path.join(backend_dir, file_path))
            if not os.path.exists(abs_code_path):
                logger.error("TESTING_AGENT: Generated code file not found: %s", abs_code_path)
                continue

            # Read the file content
            with open(abs_code_path, "r", encoding="utf-8") as f:
                code_content = f.read()

            filename = os.path.basename(abs_code_path)
            logger.info("TESTING_AGENT: Requesting test generation from Gemini for %s", filename)

            # Formulate prompt including helper keywords for mock fallback matching
            test_target_name = f"test_{os.path.splitext(filename)[0]}.py"
            user_prompt = (
                f"Generate unit tests for {test_target_name} to test the following implementation file "
                f"containing authentication functions (task id: test_auth):\n\n"
                f"Filename: {filename}\n"
                f"File Path: {file_path}\n"
                f"Code:\n```python\n{code_content}\n```\n"
            )

            try:
                # Sleep briefly to throttle API requests
                await asyncio.sleep(2)
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
                
                # Support both filename and test_filename
                test_filename = payload.get("test_filename") or payload.get("filename")
                test_code = payload.get("code")

                if not test_filename or not test_code:
                    raise ValidationError.from_exception_data(
                        "TestGenerationResult validation error",
                        line_errors=[]
                    )

                # Validate filename starts with test_ and ends with .py
                if not test_filename.startswith("test_") or not test_filename.endswith(".py"):
                    test_filename = f"test_{os.path.splitext(filename)[0]}.py"

                resolved_test_path = os.path.abspath(os.path.join(self._config.test_dir, test_filename))
                
                # Verify bounds
                if not resolved_test_path.startswith(os.path.abspath(self._config.test_dir)):
                    raise TesterError(f"Generated test filename escapes test directory: {test_filename}")

                # Save code to file
                logger.info("TESTING_AGENT: Saving generated test to %s", resolved_test_path)
                with open(resolved_test_path, "w", encoding="utf-8") as tf:
                    tf.write(test_code)

                relative_test_path = os.path.relpath(resolved_test_path, start=backend_dir)
                generated_test_paths.append(relative_test_path)

            except Exception as exc:
                logger.error("TESTING_AGENT: Failed to generate tests for %s: %s", filename, exc)
                continue

        logger.info("TESTING_AGENT: tests saved")
        return generated_test_paths

    def execute_tests(self, workflow_id: str) -> TestSuite:
        """Run pytest automatically, capture stdout/stderr, parse results, and return TestSuite."""
        logger.info("TESTING_AGENT: tests executed")
        
        tests_dir = self._config.test_dir
        os.makedirs(tests_dir, exist_ok=True)
        xml_path = os.path.join(tests_dir, "report.xml")

        # Clean up existing report
        if os.path.exists(xml_path):
            try:
                os.remove(xml_path)
            except Exception:
                pass

        # Environment setup: add output_dir to PYTHONPATH
        env = os.environ.copy()
        env["PYTHONPATH"] = self._config.output_dir + os.pathsep + env.get("PYTHONPATH", "")

        cmd = [sys.executable, "-m", "pytest", tests_dir, f"--junitxml={xml_path}"]

        start_time = time.perf_counter()
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        duration = time.perf_counter() - start_time

        test_results = []
        passed_count = 0
        failed_count = 0

        # Parse JUnit XML
        if os.path.exists(xml_path):
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
                for testcase in root.iter("testcase"):
                    classname = testcase.get("classname", "")
                    name = testcase.get("name", "")
                    full_name = f"{classname}.{name}" if classname else name
                    time_val = float(testcase.get("time") or 0.0)

                    status = TestStatus.PASSED
                    error_message = None

                    failure = testcase.find("failure")
                    error = testcase.find("error")

                    if failure is not None:
                        status = TestStatus.FAILED
                        error_message = failure.get("message") or failure.text
                        failed_count += 1
                    elif error is not None:
                        status = TestStatus.ERROR
                        error_message = error.get("message") or error.text
                        failed_count += 1
                    else:
                        passed_count += 1

                    test_results.append(
                        TestResult(
                            test_name=full_name,
                            status=status,
                            execution_time=time_val,
                            error_message=error_message,
                        )
                    )
            except Exception as exc:
                logger.error("TESTING_AGENT: Failed to parse JUnit XML report: %s", exc)

        # Fallback if no tests were collected or parsed but pytest exited with error
        if not test_results:
            if result.returncode != 0:
                failed_count = 1
                test_results.append(
                    TestResult(
                        test_name="pytest_execution",
                        status=TestStatus.ERROR,
                        execution_time=duration,
                        error_message=result.stderr or result.stdout or f"Pytest execution failed with exit code {result.returncode}",
                    )
                )

        logger.info(
            "TESTING_AGENT: pass/fail summary: passed=%d, failed=%d",
            passed_count,
            failed_count,
        )

        # Generate structured feedback
        feedback = None
        if failed_count > 0:
            feedback_parts = ["The following test cases failed:"]
            for r in test_results:
                if r.status in (TestStatus.FAILED, TestStatus.ERROR):
                    feedback_parts.append(f"- Test: {r.test_name}")
                    feedback_parts.append(f"  Status: {r.status.value}")
                    if r.error_message:
                        feedback_parts.append(f"  Error:\n{r.error_message}")
            feedback = "\n".join(feedback_parts)

        return TestSuite(
            workflow_id=workflow_id,
            tests=test_results,
            passed_count=passed_count,
            failed_count=failed_count,
            stdout=result.stdout,
            stderr=result.stderr,
            total_duration=duration,
            feedback=feedback,
        )
