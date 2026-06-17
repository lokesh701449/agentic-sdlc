"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  History,
  Clock,
  Eye,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle
} from "lucide-react";
import { api } from "@/utils/api";
import { Workflow } from "@/utils/types";

export default function HistoryPage() {
  const { data: workflows, isLoading, error } = useQuery<Workflow[]>({
    queryKey: ["workflows"],
    queryFn: async () => {
      const response = await api.get("/workflows");
      return response.data;
    },
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "planning":
      case "in_progress":
      case "reviewing":
      case "correcting":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold text-amber-400 bg-amber-400/10 rounded-full border border-amber-400/20">
            {status.replace("_", " ").toUpperCase()}
          </span>
        );
      case "awaiting_approval":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold text-cyan-400 bg-cyan-400/10 rounded-full border border-cyan-400/20">
            AWAITING APPROVAL
          </span>
        );
      case "completed":
      case "validated":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold text-emerald-400 bg-emerald-400/10 rounded-full border border-emerald-400/20">
            COMPLETED
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold text-rose-400 bg-rose-400/10 rounded-full border border-rose-400/20">
            FAILED
          </span>
        );
      case "cancelled":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold text-zinc-400 bg-zinc-800 rounded-full border border-zinc-700">
            CANCELLED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold text-zinc-400 bg-zinc-800 rounded-full">
            {status?.toUpperCase() || "UNKNOWN"}
          </span>
        );
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex h-16 items-center justify-between border-b border-zinc-800 px-8 bg-zinc-900/50 backdrop-blur-sm shrink-0">
        <div className="flex items-center gap-3">
          <History className="h-6 w-6 text-indigo-400" />
          <h1 className="text-xl font-semibold tracking-tight text-zinc-100 font-sans">
            Workflow Execution History
          </h1>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-xl">
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-24 gap-3">
              <Loader2 className="h-8 w-8 text-indigo-500 animate-spin" />
              <span className="text-zinc-400 text-xs">Fetching execution history...</span>
            </div>
          )}

          {error && (
            <div className="flex flex-col items-center justify-center py-24 gap-2 text-center">
              <AlertCircle className="h-8 w-8 text-rose-500" />
              <span className="text-zinc-200 text-sm font-semibold">Failed to load history</span>
              <span className="text-zinc-500 text-xs">Could not connect to FastAPI server.</span>
            </div>
          )}

          {!isLoading && !error && workflows && (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-zinc-950/40 border-b border-zinc-800 text-xs font-bold text-zinc-400 uppercase tracking-wider">
                    <th className="px-6 py-4">Workflow ID</th>
                    <th className="px-6 py-4">Original Requirement</th>
                    <th className="px-6 py-4">Status</th>
                    <th className="px-6 py-4">Duration</th>
                    <th className="px-6 py-4">Created At</th>
                    <th className="px-6 py-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/80">
                  {workflows.length > 0 ? (
                    workflows.map((wf: Workflow) => {
                      // Determine execution duration
                      let durationStr = "N/A";
                      const totalDuration = typeof wf.total_duration === "number"
                        ? wf.total_duration
                        : (wf.planner_output && typeof wf.planner_output === "object"
                          ? wf.planner_output.total_duration
                          : null);
                      if (typeof totalDuration === "number") {
                        durationStr = `${totalDuration.toFixed(1)}s`;
                      }
                      
                      return (
                        <tr key={wf.workflow_id} className="hover:bg-zinc-800/30 transition-all">
                          <td className="px-6 py-4 font-mono font-bold text-sm text-indigo-400">
                            {wf.workflow_id}
                          </td>
                          <td className="px-6 py-4 text-sm text-zinc-300 max-w-sm truncate font-sans">
                            {wf.original_requirement}
                          </td>
                          <td className="px-6 py-4">{getStatusBadge(wf.status)}</td>
                          <td className="px-6 py-4 text-sm text-zinc-300 font-semibold font-mono">
                            <span className="flex items-center gap-1.5">
                              <Clock className="h-3.5 w-3.5 text-zinc-500" />
                              {durationStr}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-xs text-zinc-400 font-semibold">
                            {new Date(wf.created_at).toLocaleString()}
                          </td>
                          <td className="px-6 py-4 text-right">
                            <Link
                              href={`/?workflow_id=${wf.workflow_id}`}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-400 hover:text-indigo-300 hover:bg-indigo-500/10 rounded-md transition-all"
                            >
                              <Eye className="h-3.5 w-3.5" />
                              Track Page
                            </Link>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={6} className="px-6 py-16 text-center text-zinc-500 text-sm">
                        No previous workflows found. Launch your first pipeline on the homepage!
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
