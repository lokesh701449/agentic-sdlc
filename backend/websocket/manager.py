from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    """Manages WebSocket connections and subscription mapping for real-time workflow events."""

    def __init__(self) -> None:
        # Map workflow_id -> list of subscribed WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Global connection broadcast pool
        self.global_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, workflow_id: str | None = None) -> None:
        """Accept a new connection and subscribe it to a specific workflow_id or global channel."""
        await websocket.accept()
        if workflow_id and workflow_id != "all":
            if workflow_id not in self.active_connections:
                self.active_connections[workflow_id] = []
            self.active_connections[workflow_id].append(websocket)
        else:
            self.global_connections.append(websocket)

    def disconnect(self, websocket: WebSocket, workflow_id: str | None = None) -> None:
        """Remove a disconnected WebSocket client from active subscription mappings."""
        if workflow_id and workflow_id in self.active_connections:
            if websocket in self.active_connections[workflow_id]:
                self.active_connections[workflow_id].remove(websocket)
            if not self.active_connections[workflow_id]:
                del self.active_connections[workflow_id]
        if websocket in self.global_connections:
            self.global_connections.remove(websocket)

    async def send_workflow_update(self, workflow_id: str, event_data: dict) -> None:
        """Broadcast a structured JSON payload to all clients subscribed to the workflow or global channel."""
        # 1. Broadcast to workflow specific clients
        if workflow_id in self.active_connections:
            for connection in list(self.active_connections[workflow_id]):
                try:
                    await connection.send_json(event_data)
                except Exception:
                    # Clean up broken connection
                    self.disconnect(connection, workflow_id)

        # 2. Broadcast to global clients listening to all events
        for connection in list(self.global_connections):
            try:
                await connection.send_json(event_data)
            except Exception:
                # Clean up broken connection
                self.disconnect(connection, None)

manager = ConnectionManager()
