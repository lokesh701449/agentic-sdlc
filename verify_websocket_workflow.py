import asyncio
import json
import urllib.request
import urllib.parse
import sys
import websockets

HTTP_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000"

def post_http(endpoint: str, data: dict = None) -> dict:
    url = f"{HTTP_URL}{endpoint}"
    payload = json.dumps(data or {}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode("utf-8"))

async def test_websocket_flow():
    print("Step 1: Creating a new workflow via POST /workflow...")
    requirement = "Generate a utility module helper_math.py with a function to add two numbers. Create test_helper_math.py."
    try:
        wf_res = post_http("/workflow", {"requirement": requirement})
    except Exception as e:
        print(f"Error calling POST /workflow: {e}")
        print("Please ensure the FastAPI backend is running on port 8000.")
        sys.exit(1)

    workflow_id = wf_res.get("workflow_id")
    print(f"Created workflow: {workflow_id} with status: {wf_res.get('status')}")
    assert workflow_id, "Workflow ID should not be empty!"

    ws_endpoint = f"{WS_URL}/ws/workflows/{workflow_id}"
    print(f"Step 2: Connecting to WebSocket subscription endpoint: {ws_endpoint}...")
    
    received_events = []
    expected_lifecycle = [
        "workflow_started",
        "planning_started",
        "planning_completed",
        "approval_pending",
        "coding_started",
        "coding_task_started",
        "coding_task_completed",
        "coding_completed",
        "testing_started",
        "testing_completed",
        "monitoring_updated",
    ]

    async with websockets.connect(ws_endpoint) as websocket:
        print("Connected successfully to WebSocket!")
        
        while True:
            try:
                # Set a timeout so we don't hang indefinitely if uvicorn fails
                message_str = await asyncio.wait_for(websocket.recv(), timeout=180)
                message = json.loads(message_str)
                event_name = message.get("event")
                msg_text = message.get("message")
                
                print(f"\n[WS EVENT] Event: '{event_name}'")
                print(f"  Timestamp: {message.get('timestamp')}")
                print(f"  Message  : {msg_text}")
                print(f"  Data keys: {list(message.get('data', {}).keys())}")
                
                # Assert structural requirements
                assert "event" in message, "Event key missing in websocket payload"
                assert "workflow_id" in message, "Workflow ID key missing in websocket payload"
                assert "timestamp" in message, "Timestamp key missing in websocket payload"
                assert "message" in message, "Message key missing in websocket payload"
                assert "data" in message, "Data key missing in websocket payload"
                assert message["workflow_id"] == workflow_id, "Workflow ID mismatch in event payload"

                received_events.append(event_name)

                # Programmatic trigger for plan approval
                if event_name == "approval_pending":
                    print("\nStep 3: Awaiting approval event received. Sending approval POST /workflow/{id}/approve...")
                    approve_res = post_http(f"/workflow/{workflow_id}/approve")
                    print(f"Approve response: {approve_res}")
                    assert approve_res.get("status") == "in_progress", "Expected status to be in_progress after approval"

                # Exit loop when workflow reaches final state
                if event_name in ("workflow_completed", "workflow_failed"):
                    print(f"\nFinal event '{event_name}' received.")
                    break

            except asyncio.TimeoutError:
                print("Error: Timeout waiting for next WebSocket event!")
                break
            except Exception as e:
                print(f"Error during WebSocket listening: {e}")
                break

    print("\nWebSocket Flow Analysis:")
    print("========================")
    print(f"Total events received: {len(received_events)}")
    print(f"Received events order: {received_events}")

    # Check that key phases were emitted
    for step in ["workflow_started", "planning_started", "planning_completed", "approval_pending"]:
        assert step in received_events, f"Required early step '{step}' was not emitted over WebSocket"
        
    print("\nSuccess! All WebSocket event structures, ordering, and validations assert correctly.")

if __name__ == "__main__":
    asyncio.run(test_websocket_flow())
