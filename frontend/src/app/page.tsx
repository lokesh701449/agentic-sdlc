"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useWorkflowSocket } from "@/hooks/useWorkflowSocket";
import { Workflow, Task, WorkflowMetrics, GeneratedFile, AgentMetric } from "@/utils/types";
import {
  Play,
  Loader2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  FileCode,
  Clock,
  Layers,
  ChevronRight,
  UserCheck,
  Eye,
  Plus,
  ArrowRight,
  Database,
  Activity
} from "lucide-react";
import { api } from "@/utils/api";
import FileViewer from "@/components/FileViewer";

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const [requirement, setRequirement] = useState("");
  const [activeWorkflowId, setActiveWorkflowId] = useState<string | null>(null);
  const [viewingFile, setViewingFile] = useState<string | null>(null);

  const { logs, isConnected, connectionStatus, lastEvent } = useWorkflowSocket(activeWorkflowId);
  const terminalEndRef = useRef<HTMLDivElement | null>(null);

  const [toasts, setToasts] = useState<any[]>([]);

  const addToast = (message: string, type: "success" | "error" | "info" = "info") => {
    const id = Math.random().toString(36).substr(2, 9);
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const wfId = params.get("workflow_id");
      if (wfId) {
        setActiveWorkflowId(wfId);
      }
    }
  }, []);

  // Mutation to create a new workflow
  const createWorkflowMutation = useMutation({
    mutationFn: async (reqText: string) => {
      const response = await api.post("/workflow", { requirement: reqText });
      return response.data;
    },
    onSuccess: (data) => {
      setActiveWorkflowId(data.workflow_id);
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
    },
  });

  // Mutation to approve a workflow plan
  const approveMutation = useMutation({
    mutationFn: async (wfId: string) => {
      const response = await api.post(`/workflow/${wfId}/approve`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflow", activeWorkflowId] });
      queryClient.invalidateQueries({ queryKey: ["workflowTasks", activeWorkflowId] });
      queryClient.invalidateQueries({ queryKey: ["workflowMetrics", activeWorkflowId] });
    },
  });

  // Mutation to reject a workflow plan
  const rejectMutation = useMutation({
    mutationFn: async (wfId: string) => {
      const response = await api.post(`/workflow/${wfId}/reject`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflow", activeWorkflowId] });
    },
  });

  // Query workflow details
  const { data: workflow, isLoading: isLoadingWorkflow, isError: isWorkflowError } = useQuery<Workflow | null>({
    queryKey: ["workflow", activeWorkflowId],
    queryFn: async () => {
      try {
        const response = await api.get(`/workflow/${activeWorkflowId}`);
        return response.data;
      } catch (err: any) {
        if (err.response && err.response.status === 404) {
          return null; // Return null so we can check it explicitly
        }
        throw err;
      }
    },
    enabled: !!activeWorkflowId,
    refetchInterval: isConnected ? false : 3000,
    retry: false,
  });

  // Query workflow tasks
  const { data: tasks } = useQuery<Task[]>({
    queryKey: ["workflowTasks", activeWorkflowId],
    queryFn: async () => {
      const response = await api.get(`/workflow/${activeWorkflowId}/tasks`);
      return response.data;
    },
    enabled: !!activeWorkflowId && !!workflow && workflow?.status !== "planning",
    refetchInterval: isConnected ? false : 3000,
  });

  // Query workflow metrics (test results, review issues, monitoring metrics)
  const { data: metrics } = useQuery<WorkflowMetrics>({
    queryKey: ["workflowMetrics", activeWorkflowId],
    queryFn: async () => {
      const response = await api.get(`/workflow/${activeWorkflowId}/metrics`);
      return response.data;
    },
    enabled: !!activeWorkflowId && !!workflow && workflow?.status !== "planning" && workflow?.status !== "awaiting_approval",
    refetchInterval: isConnected ? false : 3000,
  });

  // Query generated files
  const { data: generatedFiles } = useQuery<GeneratedFile[]>({
    queryKey: ["workflowFiles", activeWorkflowId],
    queryFn: async () => {
      const response = await api.get(`/workflow/${activeWorkflowId}/files`);
      return response.data;
    },
    enabled: !!activeWorkflowId && !!workflow && workflow?.status !== "planning" && workflow?.status !== "awaiting_approval",
    refetchInterval: isConnected ? false : 3000,
  });

  const uniqueFiles = generatedFiles
    ? Array.from(
        new Map(generatedFiles.map((file: GeneratedFile) => [file.file_path, file])).values()
      )
    : [];

  // Live WebSocket Invalidation Side Effects
  useEffect(() => {
    if (lastEvent) {
      queryClient.invalidateQueries({ queryKey: ["workflow", activeWorkflowId] });
      queryClient.invalidateQueries({ queryKey: ["workflowTasks", activeWorkflowId] });
      queryClient.invalidateQueries({ queryKey: ["workflowMetrics", activeWorkflowId] });
      queryClient.invalidateQueries({ queryKey: ["workflowFiles", activeWorkflowId] });
    }
  }, [lastEvent, activeWorkflowId, queryClient]);

  // Live Toast Side Effects
  useEffect(() => {
    if (lastEvent) {
      if (lastEvent.event === "workflow_failed") {
        addToast(lastEvent.message || "Workflow failed during execution.", "error");
      } else if (lastEvent.event === "coding_task_failed") {
        addToast(lastEvent.message || "A task failed code generation or validation.", "error");
      } else if (lastEvent.event === "workflow_completed") {
        addToast(lastEvent.message || "Workflow completed successfully!", "success");
      }
    }
  }, [lastEvent]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!requirement.trim()) return;
    createWorkflowMutation.mutate(requirement);
    setRequirement("");
  };

  const calculateProgress = () => {
    if (!workflow) return 0;
    const status = workflow.status;
    if (status === "planning") return 10;
    if (status === "awaiting_approval") return 20;
    if (status === "approved" || status === "in_progress") {
      if (tasks && tasks.length > 0) {
        const completedTasks = tasks.filter((t: any) => t.status === "completed").length;
        return Math.round(20 + (completedTasks / tasks.length) * 30);
      }
      return 30;
    }
    if (status === "reviewing") return 65;
    if (status === "correcting") return 75;
    if (status === "validated") return 90;
    if (status === "completed" || status === "failed" || status === "cancelled") return 100;
    return 0;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "planning":
      case "in_progress":
      case "reviewing":
      case "correcting":
        return (
          <span className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-amber-400 bg-amber-400/10 rounded-full animate-pulse border border-amber-400/20">
            <Loader2 className="h-3 w-3 animate-spin" />
            {status.replace("_", " ").toUpperCase()}
          </span>
        );
      case "awaiting_approval":
        return (
          <span className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-cyan-400 bg-cyan-400/10 rounded-full border border-cyan-400/20">
            <UserCheck className="h-3 w-3" />
            AWAITING APPROVAL
          </span>
        );
      case "completed":
      case "validated":
        return (
          <span className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-emerald-400 bg-emerald-400/10 rounded-full border border-emerald-400/20">
            <CheckCircle className="h-3 w-3" />
            COMPLETED
          </span>
        );
      case "failed":
        return (
          <span className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-rose-400 bg-rose-400/10 rounded-full border border-rose-400/20">
            <XCircle className="h-3 w-3" />
            FAILED
          </span>
        );
      case "cancelled":
        return (
          <span className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-zinc-400 bg-zinc-800 rounded-full border border-zinc-700">
            <XCircle className="h-3 w-3" />
            CANCELLED
          </span>
        );
      default:
        return (
          <span className="px-3 py-1 text-xs font-semibold text-zinc-400 bg-zinc-800 rounded-full border border-zinc-700">
            {status?.toUpperCase() || "UNKNOWN"}
          </span>
        );
    }
  };

  // Extract metrics durations
  const getAgentMetric = (agentName: string): AgentMetric | null => {
    if (!metrics?.monitoring_metrics) return null;
    return metrics.monitoring_metrics.find((m: AgentMetric) => m.agent_name === agentName) || null;
  };

  const plannerMetric = getAgentMetric("PlannerAgent");
  const codingMetric = getAgentMetric("CodingAgent");
  const testingMetric = getAgentMetric("TestingAgent");
  const workflowMetric = getAgentMetric("WorkflowOrchestrator");

  // Determine stage details for timeline visualization
  const getStageStatus = (stage: string) => {
    if (!workflow) return { status: "pending", duration: null, timestamp: null };

    const status = workflow.status;

    if (stage === "Requirement") {
      return { status: "completed", duration: 0, timestamp: workflow?.created_at };
    }

    if (stage === "Planner") {
      if (status === "planning") return { status: "running", duration: null, timestamp: null };
      const metric = plannerMetric || (status !== "planning" ? { execution_duration: workflow?.planning_duration || 0, timestamp: workflow?.created_at } : null);
      return {
        status: metric ? "completed" : "pending",
        duration: metric?.execution_duration ?? null,
        timestamp: metric?.timestamp ?? null,
      };
    }

    if (stage === "Approval") {
      if (status === "awaiting_approval") return { status: "running", duration: null, timestamp: null };
      if (status === "cancelled") return { status: "failed", duration: null, timestamp: null };
      if (status === "planning") return { status: "pending", duration: null, timestamp: null };
      return { status: "completed", duration: 0, timestamp: null };
    }

    if (stage === "Coding") {
      if (status === "planning" || status === "awaiting_approval" || status === "cancelled") {
        return { status: "pending", duration: null, timestamp: null };
      }
      if (status === "in_progress" && !codingMetric) return { status: "running", duration: null, timestamp: null };
      return {
        status: codingMetric ? (codingMetric.status === "failed" ? "failed" : "completed") : "pending",
        duration: codingMetric?.execution_duration ?? null,
        timestamp: codingMetric?.timestamp ?? null,
      };
    }

    if (stage === "Testing") {
      if (status === "planning" || status === "awaiting_approval" || status === "cancelled" || (status === "in_progress" && !codingMetric)) {
        return { status: "pending", duration: null, timestamp: null };
      }
      if (status === "reviewing" || status === "correcting" || (status === "in_progress" && codingMetric && !testingMetric)) {
        return { status: "running", duration: null, timestamp: null };
      }
      return {
        status: testingMetric ? (testingMetric.status === "failed" ? "failed" : "completed") : "pending",
        duration: testingMetric?.execution_duration ?? null,
        timestamp: testingMetric?.timestamp ?? null,
      };
    }

    if (stage === "Monitoring") {
      if (!testingMetric || status === "planning" || status === "awaiting_approval" || status === "cancelled") {
        return { status: "pending", duration: null, timestamp: null };
      }
      return { status: "completed", duration: 0.1, timestamp: testingMetric?.timestamp ?? null };
    }

    if (stage === "Runtime Validation") {
      if (!testingMetric || status === "planning" || status === "awaiting_approval" || status === "cancelled") {
        return { status: "pending", duration: null, timestamp: null };
      }
      const filesFailed = tasks?.some((t: Task) => t.status === "failed") || (metrics?.test_results?.some((t: any) => t.status === "error" || t.status === "failed"));
      return {
        status: filesFailed ? "failed" : "completed",
        duration: 0.2,
        timestamp: testingMetric?.timestamp ?? null,
      };
    }

    if (stage === "Completed") {
      if (status === "completed" || status === "validated") {
        return { status: "completed", duration: workflowMetric?.execution_duration ?? workflow?.total_duration, timestamp: workflowMetric?.timestamp ?? null };
      }
      if (status === "failed") {
        return { status: "failed", duration: workflowMetric?.execution_duration ?? workflow?.total_duration, timestamp: workflowMetric?.timestamp ?? null };
      }
      return { status: "pending", duration: null, timestamp: null };
    }

    return { status: "pending", duration: null, timestamp: null };
  };

  const getTimelineIcon = (stageStatus: string) => {
    switch (stageStatus) {
      case "completed":
        return <CheckCircle className="h-6 w-6 text-emerald-500 fill-zinc-950" />;
      case "running":
        return <Loader2 className="h-6 w-6 text-amber-500 animate-spin" />;
      case "failed":
        return <XCircle className="h-6 w-6 text-rose-500 fill-zinc-950" />;
      default:
        return <div className="h-6 w-6 rounded-full border-2 border-zinc-700 bg-zinc-900" />;
    }
  };

  const stages = [
    "Requirement",
    "Planner",
    "Approval",
    "Coding",
    "Testing",
    "Monitoring",
    "Runtime Validation",
    "Completed",
  ];

  return (
    <div className="flex-1 flex flex-col overflow-hidden relative">
      {/* Toast Notifications */}
      <div className="fixed top-6 right-6 z-50 flex flex-col gap-3 max-w-sm">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`p-4 rounded-lg border shadow-lg flex items-start gap-3 animate-slide-in backdrop-blur-md ${
              toast.type === "error"
                ? "bg-rose-950/80 border-rose-500/30 text-rose-200"
                : toast.type === "success"
                ? "bg-emerald-950/80 border-emerald-500/30 text-emerald-200"
                : "bg-zinc-900/80 border-zinc-700 text-zinc-200"
            }`}
          >
            {toast.type === "error" ? (
              <XCircle className="h-5 w-5 shrink-0 text-rose-400" />
            ) : toast.type === "success" ? (
              <CheckCircle className="h-5 w-5 shrink-0 text-emerald-400" />
            ) : (
              <Activity className="h-5 w-5 shrink-0 text-indigo-400" />
            )}
            <div className="text-xs font-semibold">{toast.message}</div>
          </div>
        ))}
      </div>

      {/* Top Bar */}
      <header className="flex h-16 items-center justify-between border-b border-zinc-800 px-8 bg-zinc-900/50 backdrop-blur-sm shrink-0">
        <h1 className="text-xl font-semibold tracking-tight text-zinc-100">Workflow Execution Dashboard</h1>
        {activeWorkflowId && (
          <button
            onClick={() => {
              if (typeof window !== "undefined") {
                window.history.pushState({}, "", "/");
              }
              setActiveWorkflowId(null);
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-zinc-400 hover:text-zinc-100 bg-zinc-800 hover:bg-zinc-700 rounded-md transition-all"
          >
            <Plus className="h-3.5 w-3.5" />
            New Workflow
          </button>
        )}
      </header>

      {/* Main Panel Content */}
      <div className="flex-1 overflow-y-auto p-8 space-y-8">
        {!activeWorkflowId ? (
          /* New Workflow Submission Page */
          <div className="max-w-2xl mx-auto py-12 space-y-6">
            <div className="text-center space-y-2">
              <h2 className="text-2xl font-bold tracking-tight text-zinc-100">Execute New Software Task</h2>
              <p className="text-zinc-400 text-sm">
                Describe requirements clearly. The AI Agents will formulate planning, code, verify unit tests, perform security validation, and monitor performance.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4 bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-xl">
              <div className="space-y-2">
                <label htmlFor="requirement" className="text-sm font-semibold text-zinc-300">
                  Engineering Requirements Description
                </label>
                <textarea
                  id="requirement"
                  rows={6}
                  placeholder="e.g. Generate a simple auth module in auth.py with get_password_hash and verify_password. Create test_auth.py tests."
                  className="w-full bg-zinc-950 border border-zinc-800 hover:border-zinc-700 focus:border-indigo-500 rounded-lg p-4 text-sm font-mono text-zinc-200 focus:ring-1 focus:ring-indigo-500 focus:outline-none transition-all resize-none"
                  value={requirement}
                  onChange={(e) => setRequirement(e.target.value)}
                />
              </div>

              <button
                type="submit"
                disabled={!requirement.trim() || createWorkflowMutation.isPending}
                className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-sm font-semibold text-white rounded-lg transition-all shadow-md shadow-indigo-600/20"
              >
                {createWorkflowMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Initializing workflow state...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    Launch SDLC Pipeline
                  </>
                )}
              </button>
            </form>
          </div>
        ) : isLoadingWorkflow ? (
          /* Premium Loading Screen */
          <div className="flex flex-col items-center justify-center py-24 space-y-4">
            <Loader2 className="h-8 w-8 text-indigo-500 animate-spin" />
            <p className="text-zinc-400 text-sm font-semibold tracking-wide animate-pulse">Loading workflow execution data...</p>
          </div>
        ) : isWorkflowError || !workflow ? (
          /* Error Screen */
          <div className="flex flex-col items-center justify-center py-20 space-y-6 max-w-md mx-auto text-center animate-fade-in">
            <div className="p-4 bg-rose-500/10 rounded-full border border-rose-500/20">
              <AlertTriangle className="h-10 w-10 text-rose-400" />
            </div>
            <div className="space-y-2">
              <h3 className="text-xl font-bold text-zinc-100">Workflow Not Found</h3>
              <p className="text-sm text-zinc-400 leading-relaxed">
                The workflow with ID <span className="font-mono text-rose-400 font-bold bg-rose-500/10 px-1.5 py-0.5 rounded">{activeWorkflowId}</span> could not be found or has not been initialized.
              </p>
            </div>
            <button
              onClick={() => {
                if (typeof window !== "undefined") {
                  window.history.pushState({}, "", "/");
                }
                setActiveWorkflowId(null);
              }}
              className="py-2.5 px-6 bg-zinc-800 hover:bg-zinc-700 hover:text-zinc-100 text-zinc-300 font-semibold text-sm rounded-lg border border-zinc-700 hover:border-zinc-600 transition-all shadow-md"
            >
              Go to Homepage
            </button>
          </div>
        ) : (
          /* Live Tracking Dashboard View */
          <div className="space-y-8">
            {/* Workflow Header Data Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-6">
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-md flex flex-col justify-between h-28">
                <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Workflow ID</span>
                <span className="text-lg font-bold text-indigo-400 font-mono">{activeWorkflowId}</span>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-md flex flex-col justify-between h-28">
                <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Current Status</span>
                <div className="flex shrink-0">{getStatusBadge(workflow?.status || "loading")}</div>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-md flex flex-col justify-between h-28">
                <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Total Duration</span>
                <div className="flex items-center gap-1 text-zinc-100 font-bold">
                  <Clock className="h-4 w-4 text-indigo-400" />
                  <span>
                    {typeof workflow?.total_duration === "number" ? `${workflow.total_duration.toFixed(1)}s` : "Calculating..."}
                  </span>
                </div>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-md flex flex-col justify-between h-28">
                <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Tasks Planned</span>
                <div className="flex items-center gap-1 text-zinc-100 font-bold">
                  <Layers className="h-4 w-4 text-indigo-400" />
                  <span>{tasks?.length || 0} tasks</span>
                </div>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-md flex flex-col justify-between h-28">
                <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Generated Files</span>
                <div className="flex items-center gap-1 text-zinc-100 font-bold">
                  <FileCode className="h-4 w-4 text-indigo-400" />
                  <span>{generatedFiles?.length || 0} files</span>
                </div>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-md flex flex-col justify-between h-28">
                <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Created At</span>
                <span className="text-sm font-semibold text-zinc-300">
                  {workflow?.created_at ? new Date(workflow.created_at).toLocaleTimeString() : "Loading..."}
                </span>
              </div>
            </div>

            {/* Requirement Display Box */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-md">
              <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-wider mb-2">Original Requirement</h3>
              <p className="text-zinc-200 font-mono text-sm leading-relaxed whitespace-pre-wrap">
                {workflow?.original_requirement || "Retrieving original requirements..."}
              </p>
            </div>

            {/* Stage Timeline Grid */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-md">
              <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-wider mb-6">Workflow Stages Timeline</h3>
              <div className="relative flex flex-col md:flex-row justify-between gap-4">
                {/* Horizontal line for desktop layout */}
                <div className="absolute top-3 left-0 right-0 hidden md:block h-0.5 bg-zinc-800 z-0" />

                {stages.map((stage, idx) => {
                  const info = getStageStatus(stage);
                  return (
                    <div key={stage} className="relative z-10 flex flex-col items-center text-center flex-1 space-y-2">
                      <div className="flex items-center justify-center shrink-0">
                        {getTimelineIcon(info.status)}
                      </div>
                      <div className="space-y-0.5">
                        <div className="text-sm font-semibold text-zinc-100">{stage}</div>
                        {typeof info.duration === "number" && (
                          <div className="text-xs text-zinc-400 font-semibold">{info.duration.toFixed(1)}s</div>
                        )}
                        {info.status === "running" && (
                          <div className="text-[10px] font-semibold text-amber-500 uppercase tracking-wider animate-pulse">Running</div>
                        )}
                        {info.status === "pending" && (
                          <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Pending</div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Live Execution Console & Progress Bar */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-md space-y-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
                <div className="space-y-1">
                  <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-wider">Live Execution Console</h3>
                  <div className="flex items-center gap-2">
                    <span className={`inline-block h-2 w-2 rounded-full ${isConnected ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`} />
                    <span className="text-xs text-zinc-400 font-semibold">
                      WebSocket: {connectionStatus.toUpperCase()}
                      {!isConnected && " (Falling back to HTTP polling)"}
                    </span>
                  </div>
                </div>

                {/* Progress Bar */}
                <div className="flex items-center gap-3 w-full md:w-80 font-semibold">
                  <div className="flex-1 bg-zinc-800 h-2 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-500 rounded-full ${
                        workflow?.status === "failed" ? "bg-rose-500" : workflow?.status === "cancelled" ? "bg-zinc-500" : "bg-indigo-500"
                      }`}
                      style={{ width: `${calculateProgress()}%` }}
                    />
                  </div>
                  <span className="text-xs font-bold text-zinc-300 w-10 text-right">
                    {calculateProgress()}%
                  </span>
                </div>
              </div>

              {/* Scrolling Terminal Viewer */}
              <div className="bg-zinc-950 border border-zinc-850 rounded-lg p-4 font-mono text-xs text-zinc-300 h-72 overflow-y-auto space-y-1.5 shadow-inner select-text">
                {logs.length === 0 ? (
                  <div className="text-zinc-600 italic select-none">
                    No execution events received yet. Launch or approve a workflow to see live logs.
                  </div>
                ) : (
                  logs.map((log) => {
                    const tagColors = {
                      planner: "text-purple-400 font-bold",
                      coder: "text-blue-400 font-bold",
                      tester: "text-amber-400 font-bold",
                      reviewer: "text-pink-400 font-bold",
                      system: "text-zinc-500 font-semibold",
                    };
                    const timestampStr = new Date(log.timestamp).toLocaleTimeString();
                    return (
                      <div key={log.id} className="leading-relaxed hover:bg-zinc-900/40 px-1 py-0.5 rounded transition-all">
                        <span className="text-zinc-600 mr-2 shrink-0 select-none">[{timestampStr}]</span>
                        <span className={tagColors[log.type] || "text-zinc-300"}>
                          {log.text}
                        </span>
                      </div>
                    );
                  })
                )}
                <div ref={terminalEndRef} />
              </div>
            </div>

            {/* Plan Approvals Bar */}
            {workflow?.status === "awaiting_approval" && (
              <div className="bg-gradient-to-r from-indigo-950/40 to-cyan-950/40 border border-indigo-500/30 rounded-xl p-6 shadow-lg flex flex-col md:flex-row items-center justify-between gap-4">
                <div className="space-y-1 text-center md:text-left">
                  <h4 className="font-bold text-zinc-100">Workflow plan is generated and ready for approval</h4>
                  <p className="text-xs text-zinc-400">
                    Review generated tasks below. Clicking Approve triggers code generation and verification testing.
                  </p>
                </div>
                <div className="flex items-center gap-3 w-full md:w-auto">
                  <button
                    onClick={() => rejectMutation.mutate(activeWorkflowId!)}
                    disabled={rejectMutation.isPending}
                    className="flex-1 md:flex-none py-2.5 px-5 text-sm font-semibold bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg transition-all"
                  >
                    Reject Plan
                  </button>
                  <button
                    onClick={() => approveMutation.mutate(activeWorkflowId!)}
                    disabled={approveMutation.isPending}
                    className="flex-1 md:flex-none py-2.5 px-6 text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-all shadow-md shadow-indigo-600/20"
                  >
                    {approveMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      "Approve & Execute"
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* Agent Status Cards Section */}
            {workflow && workflow?.status !== "planning" && (
              <div className="space-y-4">
                <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-wider">Agent Performance Status</h3>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                  {/* Planner Agent Card */}
                  <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-md flex items-start gap-4">
                    <div className="p-3 bg-indigo-500/10 rounded-lg">
                      <Database className="h-6 w-6 text-indigo-400" />
                    </div>
                    <div className="space-y-1">
                      <h4 className="font-bold text-zinc-100 text-sm">Planner Agent</h4>
                      <div className="text-xs text-zinc-400">
                        Status: <span className="font-semibold text-emerald-400">Completed</span>
                      </div>
                      <div className="text-xs text-zinc-400">
                        Execution: <span className="font-semibold text-zinc-200">{typeof workflow?.planning_duration === "number" ? `${workflow.planning_duration.toFixed(1)}s` : "N/A"}</span>
                      </div>
                    </div>
                  </div>

                  {/* Coding Agent Card */}
                  <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-md flex items-start gap-4">
                    <div className="p-3 bg-indigo-500/10 rounded-lg">
                      <FileCode className="h-6 w-6 text-indigo-400" />
                    </div>
                    <div className="space-y-1">
                      <h4 className="font-bold text-zinc-100 text-sm">Coding Agent</h4>
                      <div className="text-xs text-zinc-400">
                        Status:{" "}
                        {codingMetric ? (
                          <span className={`font-semibold ${codingMetric.status === "failed" ? "text-rose-400" : "text-emerald-400"}`}>
                            {codingMetric.status.toUpperCase()}
                          </span>
                        ) : workflow?.status === "in_progress" ? (
                          <span className="font-semibold text-amber-500 animate-pulse">Running</span>
                        ) : (
                          <span className="font-semibold text-zinc-500">Pending</span>
                        )}
                      </div>
                      <div className="text-xs text-zinc-400">
                        Execution:{" "}
                        <span className="font-semibold text-zinc-200">
                          {typeof codingMetric?.execution_duration === "number" ? `${codingMetric.execution_duration.toFixed(1)}s` : "--"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Testing Agent Card */}
                  <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-md flex items-start gap-4">
                    <div className="p-3 bg-indigo-500/10 rounded-lg">
                      <Clock className="h-6 w-6 text-indigo-400" />
                    </div>
                    <div className="space-y-1">
                      <h4 className="font-bold text-zinc-100 text-sm">Testing Agent</h4>
                      <div className="text-xs text-zinc-400">
                        Status:{" "}
                        {testingMetric ? (
                          <span className={`font-semibold ${testingMetric.status === "failed" ? "text-rose-400" : "text-emerald-400"}`}>
                            {testingMetric.status.toUpperCase()}
                          </span>
                        ) : (workflow?.status === "reviewing" || workflow?.status === "correcting" || (workflow?.status === "in_progress" && codingMetric)) ? (
                          <span className="font-semibold text-amber-500 animate-pulse">Running</span>
                        ) : (
                          <span className="font-semibold text-zinc-500">Pending</span>
                        )}
                      </div>
                      <div className="text-xs text-zinc-400">
                        Execution:{" "}
                        <span className="font-semibold text-zinc-200">
                          {typeof testingMetric?.execution_duration === "number" ? `${testingMetric.execution_duration.toFixed(1)}s` : "--"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Monitoring Agent Card */}
                  <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 shadow-md flex items-start gap-4">
                    <div className="p-3 bg-indigo-500/10 rounded-lg">
                      <Activity className="h-6 w-6 text-indigo-400" />
                    </div>
                    <div className="space-y-1">
                      <h4 className="font-bold text-zinc-100 text-sm">Monitoring Agent</h4>
                      <div className="text-xs text-zinc-400">
                        Status:{" "}
                        {testingMetric ? (
                          <span className="font-semibold text-emerald-400">Completed</span>
                        ) : (
                          <span className="font-semibold text-zinc-500">Pending</span>
                        )}
                      </div>
                      <div className="text-xs text-zinc-400">
                        Execution: <span className="font-semibold text-zinc-200">{testingMetric ? "0.1s" : "--"}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Split Grid for Tasks & Files */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Tasks List Panel */}
              {workflow && workflow?.status !== "planning" && (
                <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-md flex flex-col h-[400px]">
                  <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-wider mb-4 shrink-0">Planned Tasks</h3>
                  <div className="flex-1 overflow-y-auto space-y-3 pr-2">
                    {tasks && tasks.length > 0 ? (
                      tasks.map((task: Task) => (
                        <div key={task.task_id} className="bg-zinc-950/50 border border-zinc-800/80 rounded-lg p-4 space-y-2">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <span className="text-[10px] font-bold text-indigo-400 font-mono px-1.5 py-0.5 bg-indigo-500/10 rounded shrink-0 mr-2">
                                {task.task_id}
                              </span>
                              <span className="text-sm font-bold text-zinc-100">{task.title}</span>
                            </div>
                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ${
                              task.status === "completed"
                                ? "text-emerald-400 bg-emerald-400/10 border border-emerald-400/20"
                                : task.status === "in_progress"
                                ? "text-amber-400 bg-amber-400/10 border border-amber-400/20 animate-pulse"
                                : task.status === "failed"
                                ? "text-rose-400 bg-rose-400/10 border border-rose-400/20"
                                : "text-zinc-400 bg-zinc-800 border border-zinc-700"
                            }`}>
                              {task.status.toUpperCase()}
                            </span>
                          </div>
                          <p className="text-xs text-zinc-400 leading-normal">{task.description}</p>
                          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 pt-1 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
                            <span>Priority: <span className="text-zinc-300">{task.priority}</span></span>
                            {task.estimated_effort && (
                              <span>Effort: <span className="text-zinc-300">{task.estimated_effort}</span></span>
                            )}
                            {task.dependencies && task.dependencies.length > 0 && (
                              <span>Deps: <span className="text-zinc-300 font-mono text-[9px]">{task.dependencies.join(", ")}</span></span>
                            )}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-center text-zinc-500 text-xs py-8">
                        No tasks planned yet. Formulating strategy...
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Generated Files & Validation metrics panel */}
              {workflow && workflow?.status !== "planning" && workflow?.status !== "awaiting_approval" && (
                <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 shadow-md flex flex-col h-[400px]">
                  <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-wider mb-4 shrink-0">Generated Project Files</h3>
                  <div className="flex-1 overflow-y-auto space-y-3 pr-2">
                    {uniqueFiles && uniqueFiles.length > 0 ? (
                      uniqueFiles.map((file: any, index: number) => (
                        <div key={`${file.file_path}-${index}`} className="flex items-center justify-between p-4 bg-zinc-950/50 border border-zinc-800/80 rounded-lg hover:border-zinc-700/80 transition-all">
                          <div className="flex items-center gap-3">
                            <FileCode className="h-5 w-5 text-indigo-400" />
                            <div className="space-y-0.5">
                              <div className="text-sm font-bold text-zinc-200 font-mono text-ellipsis overflow-hidden max-w-[200px] md:max-w-[280px]">
                                {file.file_path}
                              </div>
                              <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
                                Gen Time: {typeof file.generation_time_seconds === "number" ? `${file.generation_time_seconds.toFixed(1)}s` : "Cached/0s"}
                              </div>
                            </div>
                          </div>
                          <button
                            onClick={() => setViewingFile(file.file_path)}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-400 hover:text-indigo-300 hover:bg-indigo-500/10 rounded-md transition-all"
                          >
                            <Eye className="h-3.5 w-3.5" />
                            View Code
                          </button>
                        </div>
                      ))
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-center text-zinc-500 text-xs py-8">
                        No files generated yet. Waiting for coding phase.
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Code Viewer Modal */}
      {viewingFile && (
        <FileViewer filePath={viewingFile} onClose={() => setViewingFile(null)} />
      )}
    </div>
  );
}
