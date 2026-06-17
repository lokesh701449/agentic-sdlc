export interface Workflow {
  workflow_id: string;
  status: string;
  original_requirement: string;
  created_at: string;
  updated_at?: string;
  total_duration?: number | null;
  planning_duration?: number | null;
  coding_duration?: number | null;
  testing_duration?: number | null;
  monitoring_duration?: number | null;
  planner_output?: {
    total_duration?: number | null;
    [key: string]: any;
  } | null;
}

export interface Task {
  task_id: string;
  title: string;
  status: string;
  description?: string;
  priority?: string;
  estimated_effort?: string;
  dependencies?: string[];
}

export interface AgentMetric {
  agent_name: string;
  status: string;
  execution_duration?: number | null;
  timestamp?: string | null;
  [key: string]: any;
}

export interface WorkflowMetrics {
  monitoring_metrics?: AgentMetric[] | null;
  test_results?: Array<{
    status: string;
    [key: string]: any;
  }> | null;
  [key: string]: any;
}

export interface GeneratedFile {
  file_path: string;
  generation_time_seconds?: number | null;
  timestamp?: string;
}

export interface AggregatedAvgDurations {
  planner: number;
  coder: number;
  tester: number;
  total: number;
}

export interface AggregatedMetrics {
  total: number;
  success: number;
  failed: number;
  cancelled: number;
  successRate: number;
  totalRetries: number;
  avgDurations: AggregatedAvgDurations;
}
