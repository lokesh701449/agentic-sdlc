"use client";

import { useQuery } from "@tanstack/react-query";
import { X, Copy, Check, FileCode, Loader2 } from "lucide-react";
import { useState } from "react";
import { api } from "@/utils/api";

interface FileViewerProps {
  filePath: string;
  onClose: () => void;
}

export default function FileViewer({ filePath, onClose }: FileViewerProps) {
  const [copied, setCopied] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["fileContent", filePath],
    queryFn: async () => {
      const response = await api.get(`/file-content?path=${encodeURIComponent(filePath)}`);
      return response.data;
    },
    enabled: !!filePath,
  });

  const handleCopy = () => {
    if (data?.content) {
      navigator.clipboard.writeText(data.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-6">
      <div className="flex h-full max-h-[85vh] w-full max-w-4xl flex-col bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 bg-zinc-950/50 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <FileCode className="h-5 w-5 text-indigo-400" />
            <span className="font-semibold text-sm text-zinc-100">{data?.file_name || filePath}</span>
          </div>
          <div className="flex items-center gap-2">
            {data?.content && (
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-zinc-400 hover:text-zinc-100 bg-zinc-800 hover:bg-zinc-700 rounded-md transition-all"
              >
                {copied ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-500" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" />
                    Copy Code
                  </>
                )}
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 text-zinc-400 hover:text-zinc-100 bg-zinc-800 hover:bg-zinc-700 rounded-md transition-all"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-auto bg-zinc-950 p-6 font-mono text-sm leading-relaxed text-zinc-300">
          {isLoading && (
            <div className="flex h-full w-full items-center justify-center flex-col gap-3">
              <Loader2 className="h-8 w-8 text-indigo-500 animate-spin" />
              <span className="text-zinc-400 text-xs">Loading file contents...</span>
            </div>
          )}

          {error && (
            <div className="flex h-full w-full items-center justify-center flex-col gap-3 text-center">
              <span className="text-rose-500 font-semibold text-sm">Failed to load file</span>
              <span className="text-zinc-500 text-xs">{(error as any).response?.data?.detail || "An unexpected error occurred"}</span>
            </div>
          )}

          {!isLoading && !error && data?.content && (
            <pre className="whitespace-pre overflow-x-auto text-xs text-zinc-300">
              <code>
                {data.content.split("\n").map((line: string, i: number) => (
                  <div key={i} className="table-row">
                    <span className="table-cell pr-4 text-zinc-600 select-none text-right w-8">{i + 1}</span>
                    <span className="table-cell">{line}</span>
                  </div>
                ))}
              </code>
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
