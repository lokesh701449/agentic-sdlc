import { useState, useEffect, useRef } from "react";
import { API_BASE } from "@/utils/api";

export interface WorkflowEvent {
  event: string;
  workflow_id: string;
  timestamp: string;
  message: string;
  data: any;
}

export interface LogMessage {
  id: string;
  text: string;
  timestamp: string;
  type: "planner" | "coder" | "tester" | "reviewer" | "system";
}

export function useWorkflowSocket(workflowId: string | null) {
  const [logs, setLogs] = useState<LogMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");
  const [lastEvent, setLastEvent] = useState<WorkflowEvent | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<any>(null);
  const reconnectAttemptsRef = useRef(0);

  // Clear state when workflowId changes
  useEffect(() => {
    setLogs([]);
    setLastEvent(null);
    reconnectAttemptsRef.current = 0;
  }, [workflowId]);

  useEffect(() => {
    if (!workflowId) {
      if (wsRef.current) {
        wsRef.current.close();
      }
      setIsConnected(false);
      setConnectionStatus("disconnected");
      return;
    }

    const wsBase = API_BASE.replace(/^http/, "ws");
    const wsUrl = `${wsBase}/ws/workflows/${workflowId}`;

    function connect() {
      if (wsRef.current) {
        wsRef.current.close();
      }

      setConnectionStatus("connecting");
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setConnectionStatus("connected");
        reconnectAttemptsRef.current = 0;
        
        // Add a system log message
        const systemLog: LogMessage = {
          id: `sys-${Date.now()}`,
          text: `[System] Connected to real-time monitoring channel for ${workflowId}`,
          timestamp: new Date().toISOString(),
          type: "system",
        };
        setLogs((prev) => [...prev, systemLog]);
      };

      ws.onmessage = (event) => {
        try {
          const payload: WorkflowEvent = JSON.parse(event.data);
          setLastEvent(payload);
          
          if (payload.message) {
            let logType: LogMessage["type"] = "system";
            const msg = payload.message.toLowerCase();
            
            if (msg.includes("[planner]")) {
              logType = "planner";
            } else if (msg.includes("[coder]")) {
              logType = "coder";
            } else if (msg.includes("[tester]")) {
              logType = "tester";
            } else if (msg.includes("[reviewer]")) {
              logType = "reviewer";
            }

            const newLog: LogMessage = {
              id: `${payload.event}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              text: payload.message,
              timestamp: payload.timestamp || new Date().toISOString(),
              type: logType,
            };
            setLogs((prev) => [...prev, newLog]);
          }
        } catch (err) {
          console.error("Error parsing WebSocket message:", err);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        setConnectionStatus("disconnected");
        
        // Only try to reconnect if workflowId is still active and connection was not closed intentionally
        if (workflowId && reconnectAttemptsRef.current < 10) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 10000);
          reconnectAttemptsRef.current += 1;
          
          const systemLog: LogMessage = {
            id: `sys-reconnect-${Date.now()}`,
            text: `[System] Connection lost. Reconnecting in ${(delay / 1000).toFixed(0)}s (attempt ${reconnectAttemptsRef.current}/10)...`,
            timestamp: new Date().toISOString(),
            type: "system",
          };
          setLogs((prev) => [...prev, systemLog]);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };

      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
        ws.close();
      };
    }

    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [workflowId]);

  return {
    logs,
    isConnected,
    connectionStatus,
    lastEvent,
  };
}
