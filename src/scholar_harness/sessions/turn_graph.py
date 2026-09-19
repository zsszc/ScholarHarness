from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from scholar_harness.core.events import AgentEvent


def project_turn_graph(
    entries: Sequence[AgentEvent], active_leaf_id: str | None
) -> dict[str, Any]:
    """Project an append-only MiniPy entry tree into branch-aware user turns."""
    by_id = {entry.entry_id: entry for entry in entries if entry.entry_id is not None}

    def path_to(entry_id: str | None) -> list[AgentEvent]:
        path: list[AgentEvent] = []
        while entry_id is not None:
            entry = by_id[entry_id]
            path.append(entry)
            entry_id = entry.parent_id
        return list(reversed(path))

    def nearest_user(entry: AgentEvent) -> str | None:
        parent_id = entry.parent_id
        while parent_id is not None:
            parent = by_id[parent_id]
            if parent.type == "message" and parent.data.get("role") == "user":
                return parent_id
            parent_id = parent.parent_id
        return None

    users = [
        entry
        for entry in entries
        if entry.entry_id is not None
        and entry.type == "message"
        and entry.data.get("role") == "user"
    ]
    user_ids = {entry.entry_id for entry in users}
    turn_entries: dict[str, list[AgentEvent]] = {
        entry.entry_id: [entry] for entry in users if entry.entry_id is not None
    }
    for entry in entries:
        if entry.entry_id is None or entry.entry_id in user_ids:
            continue
        owner = nearest_user(entry)
        if owner is not None:
            turn_entries[owner].append(entry)

    active_ids = {entry.entry_id for entry in path_to(active_leaf_id)}
    nodes: list[dict[str, Any]] = []
    for user in users:
        assert user.entry_id is not None
        own_entries = turn_entries[user.entry_id]
        anchor = (
            by_id[active_leaf_id]
            if active_leaf_id in {entry.entry_id for entry in own_entries}
            else own_entries[-1]
        )
        path = path_to(anchor.entry_id)
        own_ids = {entry.entry_id for entry in own_entries}
        messages = [
            {
                "role": entry.data["role"],
                "content": str(entry.data.get("content") or ""),
                "entry_id": entry.entry_id,
            }
            for entry in path
            if entry.type == "message"
            and entry.data.get("role") in {"user", "assistant"}
        ]
        path_ids = {entry.entry_id for entry in path}
        tools = [
            {
                "name": str(entry.data.get("name") or ""),
                "content": str(entry.data.get("content") or ""),
                "is_error": bool(entry.data.get("isError")),
            }
            for entry in own_entries
            if entry.entry_id in path_ids
            and entry.type == "message"
            and entry.data.get("role") == "tool"
        ]
        nodes.append(
            {
                "id": user.entry_id,
                "parent_id": nearest_user(user),
                "continue_entry_id": anchor.entry_id,
                "prompt": str(user.data.get("content") or ""),
                "answer": "\n".join(
                    str(entry.data.get("content") or "")
                    for entry in path
                    if entry.entry_id in own_ids
                    and entry.type == "message"
                    and entry.data.get("role") == "assistant"
                    and entry.data.get("content")
                ),
                "messages": messages,
                "tools": tools,
                "other_answers": [
                    str(entry.data.get("content") or "")
                    for entry in own_entries
                    if entry.entry_id not in path_ids
                    and entry.type == "message"
                    and entry.data.get("role") == "assistant"
                    and entry.data.get("content")
                ],
                "active": user.entry_id in active_ids,
                "created_at": user.timestamp.isoformat(),
            }
        )
    return {"active_leaf_id": active_leaf_id, "nodes": nodes}
