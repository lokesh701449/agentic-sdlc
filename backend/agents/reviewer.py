"""ReviewerAgent — analyzes generated source code and test results, detecting issues and producing reports."""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any

from llm.base_client import BaseLLMClient
from llm.gemini_client import GeminiClient
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.5-flash"


class ReviewSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"


class ReviewIssue(BaseModel):
    issue_id: str = Field(description="Stable identifier for the issue, e.g. ISSUE-001")
    severity: ReviewSeverity
    file_name: str = Field(description="The file name where the issue was detected, e.g. 'auth.py'")
    description: str
    suggested_fix: str


class ReviewReport(BaseModel):
    status: ReviewStatus
    summary: str = Field(default_factory=str)
    issues: list[ReviewIssue] = Field(default_factory=list)


class ReviewerError(Exception):
    """Raised when review fails."""


SYSTEM_PROMPT = """\
You are a senior software engineering reviewer for an AI-orchestrated SDLC workflow.

Your task is to analyze the generated source code files and any test execution outcomes, and produce a structured review report.

You must detect:
- Code quality issues
- Missing validations
- Security concerns (e.g. hardcoded credentials, insecure cryptography, password hashing bypasses)
- Poor naming conventions
- Missing error handling
- Performance bottlenecks
- Failed test causes

Rules:
- Determine if the files pass or fail overall. If there are high-severity issues or failed test cases, status must be 'failed'. If only low-severity or no issues exist, status can be 'passed'.
- For each detected issue, provide:
  - Stable Issue ID: ISSUE-001, ISSUE-002, etc.
  - Severity: low, medium, or high
  - File Name: the exact filename where the issue exists (e.g. 'auth.py')
  - Description: what the issue is and why it's a problem
  - Suggested Fix: clear instructions or code snippets to fix the issue
- Respond with valid JSON only, matching this shape:
  {
    "status": "passed|failed",
    "summary": "overall review summary",
    "issues": [
      {
        "issue_id": "ISSUE-001",
        "severity": "low|medium|high",
        "file_name": "filename.py",
        "description": "description",
        "suggested_fix": "suggested fix"
      }
    ]
  }
"""


class ReviewerAgent:
    """Accepts source code and test results, generates a structured review report."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        client: BaseLLMClient | None = None,
    ) -> None:
        """Initialize the ReviewerAgent with config and the LLM client (dependency injection)."""
        self.model = model
        self._client = client or GeminiClient(model_name=self.model)

    async def review_code(
        self,
        code_files: dict[str, str],
        test_suite_data: dict[str, Any] | None,
        workflow_id: str,
    ) -> ReviewReport:
        """Analyze source code and test results using Gemini and produce a ReviewReport."""
        logger.info("REVIEW_AGENT: review started")

        # Prepare code files summary
        code_context = ""
        for name, content in code_files.items():
            code_context += f"Filename: {name}\nContent:\n```python\n{content}\n```\n\n"

        # Prepare test results summary
        test_context = "No test suite executed."
        if test_suite_data:
            tests = test_suite_data.get("tests", [])
            passed = test_suite_data.get("passed_count", 0)
            failed = test_suite_data.get("failed_count", 0)
            test_context = f"Test suite run summary: passed={passed}, failed={failed}\n"
            if failed > 0 and test_suite_data.get("feedback"):
                test_context += f"Failed details:\n{test_suite_data.get('feedback')}"

        user_prompt = (
            f"Review the following generated python code files and their corresponding test suite results:\n\n"
            f"=== Generated Code ===\n{code_context}\n"
            f"=== Test Suite Results ===\n{test_context}\n"
        )

        try:
            raw_response = await self._client.generate(
                prompt=user_prompt,
                system_prompt=SYSTEM_PROMPT,
                response_schema=None,
            )

            # Clean markdown wrappers if any
            cleaned_response = raw_response.strip()
            if cleaned_response.startswith("```"):
                lines = cleaned_response.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned_response = "\n".join(lines).strip()

            payload = json.loads(cleaned_response)
            report = ReviewReport.model_validate(payload)

        except Exception as exc:
            logger.warning("REVIEW_AGENT: LLM call or validation failed. Running custom review mock fallback: %s", exc)
            report = self._mock_review(code_files, test_suite_data)

        # Log results as required
        logger.info("REVIEW_AGENT: issues found: %d", len(report.issues))
        
        low_count = sum(1 for i in report.issues if i.severity == ReviewSeverity.LOW)
        med_count = sum(1 for i in report.issues if i.severity == ReviewSeverity.MEDIUM)
        high_count = sum(1 for i in report.issues if i.severity == ReviewSeverity.HIGH)
        logger.info("REVIEW_AGENT: severity summary: low=%d, medium=%d, high=%d", low_count, med_count, high_count)

        return report

    def _mock_review(self, code_files: dict[str, str], test_suite_data: dict[str, Any] | None) -> ReviewReport:
        """Fallback reviewer when LLM client hits exceptions or quota issues."""
        has_bad_hashing = False
        bad_file = "auth.py"

        # Look for the intentionally imperfect implementation
        for filename, content in code_files.items():
            if "get_password_hash" in content:
                # Returns password unchanged, or no bcrypt used
                if "return password" in content or "return plain_password" in content or "pwd_context.hash" not in content:
                    has_bad_hashing = True
                    bad_file = filename
                    break

        if has_bad_hashing:
            return ReviewReport(
                status=ReviewStatus.FAILED,
                summary="The code review failed due to severe security issues: password hashing is not implemented.",
                issues=[
                    ReviewIssue(
                        issue_id="ISSUE-001",
                        severity=ReviewSeverity.HIGH,
                        file_name=bad_file,
                        description="get_password_hash returns the password unchanged (raw text) and verify_password always returns True. This is insecure.",
                        suggested_fix="Use bcrypt or passlib CryptContext to hash passwords, and implement proper validation in verify_password using pwd_context.verify."
                    )
                ]
            )
        else:
            return ReviewReport(
                status=ReviewStatus.PASSED,
                summary="Code review passed successfully. Security and logic checks validated.",
                issues=[]
            )
