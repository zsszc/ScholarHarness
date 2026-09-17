from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionNode:
    id: str
    parent_id: str | None
    entry: Mapping[str, Any]
    children: list[str] = field(default_factory=list)


class SessionTree:
    """Projection of append-only runtime entries into a navigable tree."""

    def __init__(self, entries: Iterable[Mapping[str, Any]] = ()) -> None:
        self.nodes: dict[str, SessionNode] = {}
        self.roots: list[str] = []
        for entry in entries:
            self.append(entry)

    def append(self, entry: Mapping[str, Any]) -> SessionNode:
        entry_id = str(entry["id"])
        if entry_id in self.nodes:
            raise ValueError(f"Duplicate session entry id: {entry_id}")
        parent_value = entry.get("parentId")
        parent_id = str(parent_value) if parent_value is not None else None
        if parent_id is not None and parent_id not in self.nodes:
            raise ValueError(f"Missing parent entry: {parent_id}")

        node = SessionNode(id=entry_id, parent_id=parent_id, entry=dict(entry))
        self.nodes[entry_id] = node
        if parent_id is None:
            self.roots.append(entry_id)
        else:
            self.nodes[parent_id].children.append(entry_id)
        return node

    def path_to(self, leaf_id: str) -> list[SessionNode]:
        if leaf_id not in self.nodes:
            raise KeyError(leaf_id)
        path: list[SessionNode] = []
        current: SessionNode | None = self.nodes[leaf_id]
        while current is not None:
            path.append(current)
            current = self.nodes.get(current.parent_id) if current.parent_id else None
        return list(reversed(path))
