"""Small JSONL process used to verify the Pi RPC transport."""

import json
import sys


def emit(message: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    command = json.loads(line)
    command_type = command["type"]
    request_id = command["id"]

    if command_type == "get_state":
        emit(
            {
                "id": request_id,
                "type": "response",
                "command": "get_state",
                "success": True,
                "data": {"sessionId": "fake-session"},
            }
        )
    elif command_type == "prompt":
        emit(
            {
                "id": request_id,
                "type": "response",
                "command": "prompt",
                "success": True,
            }
        )
        emit({"type": "agent_start"})
        emit({"type": "message_update", "text": "hello"})
        emit({"type": "agent_end"})
        emit({"type": "agent_settled"})
    elif command_type == "get_entries":
        emit(
            {
                "id": request_id,
                "type": "response",
                "command": "get_entries",
                "success": True,
                "data": {
                    "entries": [
                        {
                            "id": "entry-1",
                            "parentId": None,
                            "type": "message",
                            "timestamp": "2026-09-17T00:00:00Z",
                            "message": {"role": "user", "content": "hello"},
                        }
                    ],
                    "leafId": "entry-1",
                },
            }
        )
    else:
        emit(
            {
                "id": request_id,
                "type": "response",
                "command": command_type,
                "success": False,
                "error": "unsupported command",
            }
        )
