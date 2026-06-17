"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Terminal, Activity, History, BarChart3 } from "lucide-react";

export default function Sidebar() {
  const pathname = usePathname();

  const navigation = [
    { name: "Active Workflow", href: "/", icon: Activity },
    { name: "Workflow History", href: "/history", icon: History },
    { name: "Monitoring metrics", href: "/monitoring", icon: BarChart3 },
  ];

  return (
    <div className="flex h-full w-64 flex-col bg-zinc-900 border-r border-zinc-800">
      <div className="flex h-16 items-center gap-2 px-6 border-b border-zinc-800">
        <Terminal className="h-6 w-6 text-indigo-500" />
        <span className="text-lg font-bold bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">
          Agentic SDLC
        </span>
      </div>
      <nav className="flex-1 space-y-1 px-4 py-6">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-3 text-sm font-medium rounded-lg transition-all duration-200 ${
                isActive
                  ? "bg-indigo-600/10 text-indigo-400 border-l-2 border-indigo-500"
                  : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
              }`}
            >
              <Icon className={`h-5 w-5 ${isActive ? "text-indigo-400" : "text-zinc-400"}`} />
              {item.name}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t border-zinc-800">
        <div className="flex items-center gap-3 px-2 py-2">
          <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs font-semibold text-zinc-400">System Connected</span>
        </div>
      </div>
    </div>
  );
}
