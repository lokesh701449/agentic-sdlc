"""MonitoringAgent — Tracks workflow lifecycle, agent execution times, and generates metrics/reports."""

from __future__ import annotations

import logging
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AgentMetrics(BaseModel):
    agent_name: str
    start_time: str
    end_time: str
    duration: float
    status: str
    retry_count: int = 0
    generated_files_count: int = 0


class WorkflowMetrics(BaseModel):
    workflow_id: str
    status: str
    total_duration: float
    start_time: str
    end_time: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    completion_rate: float = 0.0


class MonitoringAgentSummary(BaseModel):
    agent: str
    duration: float


class MonitoringReport(BaseModel):
    workflow_id: str
    status: str
    total_duration: float
    agents: list[MonitoringAgentSummary] = Field(default_factory=list)


class MonitoringAgent:
    """Monitors workflow execution, records metrics, and generates execution reports."""

    def __init__(self) -> None:
        logger.info("MONITORING: MonitoringAgent initialized.")

    def generate_report(
        self,
        workflow_id: str,
        status: str,
        total_duration: float,
        agent_metrics: list[AgentMetrics],
    ) -> MonitoringReport:
        """Create a MonitoringReport based on workflow execution details and agent metrics."""
        logger.info("MONITORING: Generating workflow execution report for %s", workflow_id)
        
        # Format the nested agent summaries specifically using keys "agent" and "duration"
        agents_summary = [
            MonitoringAgentSummary(
                agent=metric.agent_name,
                duration=metric.duration
            )
            for metric in agent_metrics
        ]
        
        report = MonitoringReport(
            workflow_id=workflow_id,
            status=status,
            total_duration=total_duration,
            agents=agents_summary
        )
        return report
