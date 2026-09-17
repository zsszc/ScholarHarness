import pytest

from scholar_harness.sessions.tree import SessionTree


def test_projects_branches_and_paths() -> None:
    tree = SessionTree(
        [
            {"id": "root", "parentId": None, "type": "message"},
            {"id": "a", "parentId": "root", "type": "message"},
            {"id": "b", "parentId": "root", "type": "message"},
            {"id": "a1", "parentId": "a", "type": "message"},
        ]
    )

    assert tree.roots == ["root"]
    assert tree.nodes["root"].children == ["a", "b"]
    assert [node.id for node in tree.path_to("a1")] == ["root", "a", "a1"]


def test_rejects_orphan_entry() -> None:
    with pytest.raises(ValueError, match="Missing parent"):
        SessionTree([{"id": "orphan", "parentId": "missing"}])
