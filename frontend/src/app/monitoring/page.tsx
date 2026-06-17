"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  TrendingUp,
  Percent,
  CheckCircle,
  XCircle,
  RotateCw,
  Loader2,
  Clock,
  Layers,
  AlertCircle
} from "lucide-react";
import { api } from "@/utils/api";
import { Workflow, AggregatedMetrics } from "@/utils/types";

export default function MonitoringPage() {
  const { data: workflows, isLoading, error } = useQuery<Workflow[]>({
    queryKey: ["workflows"],
    queryFn: async () => {
      const response = await api.get("/workflows");
      return response.data;
    },
  });

  // Calculate aggregate metrics from history
  const calculateMetrics = (): AggregatedMetrics => {
    if (!workflows || workflows.length === 0) {
      return {
        total: 0,
        success: 0,
        failed: 0,
        cancelled: 0,
        successRate: 0,
        totalRetries: 0,
        avgDurations: { planner: 0, coder: 0, tester: 0, total: 0 },
      };
    }

    const total = workflows.length;
    const finishedWorkflows = workflows.filter(
      (w: Workflow) => w.status === "completed" || w.status === "validated" || w.status === "failed"
    );
    const success = workflows.filter(
      (w: Workflow) => w.status === "completed" || w.status === "validated"
    ).length;
    const failed = workflows.filter((w: Workflow) => w.status === "failed").length;
    const cancelled = workflows.filter((w: Workflow) => w.status === "cancelled").length;

    const successRate = finishedWorkflows.length > 0 ? (success / finishedWorkflows.length) * 100 : 0;

    let totalRetries = 0;
    let totalPlannerDuration = 0;
    let totalCoderDuration = 0;
    let totalTesterDuration = 0;
    let totalWorkflowDuration = 0;
    let countPlanner = 0;
    let countCoder = 0;
    let countTester = 0;
    let countTotal = 0;

    workflows.forEach((w: Workflow) => {
      // Aggregate durations from workflow details
      if (typeof w.planning_duration === "number") {
        totalPlannerDuration += w.planning_duration;
        countPlanner++;
      }
      if (typeof w.coding_duration === "number") {
        totalCoderDuration += w.coding_duration;
        countCoder++;
      }
      if (typeof w.total_duration === "number") {
        totalWorkflowDuration += w.total_duration;
        countTotal++;
      }

      // Check monitoring metrics if available in w
      if (w.planner_output && typeof w.planner_output === "object") {
        const report = w.planner_output.monitoring_report;
        if (report && report.agents) {
          const testAgent = report.agents.find((a: any) => a.agent === "TestingAgent");
          if (testAgent && typeof testAgent.duration === "number") {
            totalTesterDuration += testAgent.duration;
            countTester++;
          }
        }
      }
    });

    return {
      total,
      success,
      failed,
      cancelled,
      successRate,
      totalRetries,
      avgDurations: {
        planner: countPlanner > 0 ? totalPlannerDuration / countPlanner : 0,
        coder: countCoder > 0 ? totalCoderDuration / countCoder : 0,
        tester: countTester > 0 ? totalTesterDuration / countTester : 0,
        total: countTotal > 0 ? totalWorkflowDuration / countTotal : 0,
      },
    };
  };

  const metrics = calculateMetrics();

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex h-16 items-center justify-between border-b border-zinc-800 px-8 bg-zinc-900/50 backdrop-blur-sm shrink-0">
        <div className="flex items-center gap-3">
          <BarChart3 className="h-6 w-6 text-indigo-400" />
          <h1 className="text-xl font-semibold tracking-tight text-zinc-100 font-sans">
            Monitoring & System Metrics
          </h1>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8 space-y-8">
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-32 gap-3">
            <Loader2 className="h-8 w-8 text-indigo-500 animate-spin" />
            <span className="text-zinc-400 text-xs">Aggregating system logs...</span>
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center py-32 gap-2 text-center">
            <AlertCircle className="h-8 w-8 text-rose-500" />
            <span className="text-zinc-200 text-sm font-semibold">Failed to load metrics</span>
            <span className="text-zinc-500 text-xs">Could not connect to FastAPI server.</span>
          </div>
        )}

        {!isLoading && !error && (!workflows || workflows.length === 0) && (
          <div className="flex flex-col items-center justify-center py-24 gap-4 text-center max-w-md mx-auto">
            <div className="p-4 bg-zinc-800/50 rounded-full border border-zinc-700">
              <BarChart3 className="h-10 w-10 text-zinc-400" />
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-bold text-zinc-200">No Metrics Available</h3>
              <p className="text-zinc-400 text-sm">
                No workflows have been executed yet. Run a workflow to start aggregating performance and execution duration metrics.
              </p>
            </div>
          </div>
        )}

        {!isLoading && !error && workflows && workflows.length > 0 && (
          <div className="space-y-8">
            {/* KPI Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {/* Success Rate Card */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-md flex items-start justify-between">
                <div className="space-y-1">
                  <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Success Rate</span>
                  <div className="text-2xl font-bold text-zinc-100">
                    {typeof metrics?.successRate === "number" && !isNaN(metrics.successRate)
                      ? `${metrics.successRate.toFixed(1)}%`
                      : "N/A"}
                  </div>
                </div>
                <div className="p-3 bg-emerald-500/10 rounded-lg">
                  <Percent className="h-5 w-5 text-emerald-400" />
                </div>
              </div>

              {/* Total Executions Card */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-md flex items-start justify-between">
                <div className="space-y-1">
                  <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Total Runs</span>
                  <div className="text-2xl font-bold text-zinc-100">{metrics?.total ?? 0}</div>
                </div>
                <div className="p-3 bg-indigo-500/10 rounded-lg">
                  <TrendingUp className="h-5 w-5 text-indigo-400" />
                </div>
              </div>

              {/* Failures Card */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-md flex items-start justify-between">
                <div className="space-y-1">
                  <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Failed Runs</span>
                  <div className="text-2xl font-bold text-zinc-100">{metrics?.failed ?? 0}</div>
                </div>
                <div className="p-3 bg-rose-500/10 rounded-lg">
                  <XCircle className="h-5 w-5 text-rose-400" />
                </div>
              </div>

              {/* Cancelled/Rejected Card */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-md flex items-start justify-between">
                <div className="space-y-1">
                  <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Cancelled Runs</span>
                  <div className="text-2xl font-bold text-zinc-100">{metrics?.cancelled ?? 0}</div>
                </div>
                <div className="p-3 bg-zinc-800 rounded-lg">
                  <RotateCw className="h-5 w-5 text-zinc-400" />
                </div>
              </div>
            </div>

            {/* Performance Visual Bars */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-md">
              <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-wider mb-6">Average Agent Execution Durations</h3>
              <div className="space-y-6">
                {/* Planner Agent Duration Bar */}
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="font-semibold text-zinc-200">Planner Agent</span>
                    <span className="text-zinc-400 font-semibold">
                      {typeof metrics?.avgDurations?.planner === "number" && !isNaN(metrics.avgDurations.planner)
                        ? `${metrics.avgDurations.planner.toFixed(1)}s`
                        : "--"}
                    </span>
                  </div>
                  <div className="h-2 w-full bg-zinc-850 rounded-full overflow-hidden">
                    <div
                      style={{ width: `${Math.min(((metrics?.avgDurations?.planner || 0) / 60) * 100, 100)}%` }}
                      className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                    />
                  </div>
                </div>

                {/* Coding Agent Duration Bar */}
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="font-semibold text-zinc-200">Coding Agent</span>
                    <span className="text-zinc-400 font-semibold">
                      {typeof metrics?.avgDurations?.coder === "number" && !isNaN(metrics.avgDurations.coder)
                        ? `${metrics.avgDurations.coder.toFixed(1)}s`
                        : "--"}
                    </span>
                  </div>
                  <div className="h-2 w-full bg-zinc-850 rounded-full overflow-hidden">
                    <div
                      style={{ width: `${Math.min(((metrics?.avgDurations?.coder || 0) / 60) * 100, 100)}%` }}
                      className="h-full bg-cyan-500 rounded-full transition-all duration-500"
                    />
                  </div>
                </div>

                {/* Testing Agent Duration Bar */}
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="font-semibold text-zinc-200">Testing & Self-Correction Agent</span>
                    <span className="text-zinc-400 font-semibold">
                      {typeof metrics?.avgDurations?.tester === "number" && !isNaN(metrics.avgDurations.tester)
                        ? `${metrics.avgDurations.tester.toFixed(1)}s`
                        : "--"}
                    </span>
                  </div>
                  <div className="h-2 w-full bg-zinc-850 rounded-full overflow-hidden">
                    <div
                      style={{ width: `${Math.min(((metrics?.avgDurations?.tester || 0) / 60) * 100, 100)}%` }}
                      className="h-full bg-purple-500 rounded-full transition-all duration-500"
                    />
                  </div>
                </div>

                {/* Total Workflow Duration Bar */}
                <div className="space-y-2 pt-2 border-t border-zinc-800">
                  <div className="flex justify-between text-sm">
                    <span className="font-bold text-zinc-100">Total Workflow Duration (Average)</span>
                    <span className="text-zinc-300 font-bold">
                      {typeof metrics?.avgDurations?.total === "number" && !isNaN(metrics.avgDurations.total)
                        ? `${metrics.avgDurations.total.toFixed(1)}s`
                        : "--"}
                    </span>
                  </div>
                  <div className="h-2.5 w-full bg-zinc-850 rounded-full overflow-hidden">
                    <div
                      style={{ width: `${Math.min(((metrics?.avgDurations?.total || 0) / 120) * 100, 100)}%` }}
                      className="h-full bg-gradient-to-r from-indigo-500 to-cyan-500 rounded-full transition-all duration-500"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
