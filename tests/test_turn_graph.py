from scholar_harness.core.events import AgentEvent
from scholar_harness.sessions.turn_graph import project_turn_graph


def entry(entry_id, parent_id, role, content, **data):
    return AgentEvent(
        type="message",
        session_id="graph-session",
        entry_id=entry_id,
        parent_id=parent_id,
        data={"role": role, "content": content, **data},
    )


def test_project_turn_graph_keeps_sibling_paths_separate() -> None:
    entries = [
        entry("u1", None, "user", "Question"),
        entry("a1", "u1", "assistant", "First answer"),
        entry("t1", "a1", "tool", "evidence", name="search_papers"),
        entry("u2", "t1", "user", "Continue"),
        entry("a2", "u2", "assistant", "Second answer"),
        entry("u3", "u1", "user", "Try another route"),
        entry("a3", "u3", "assistant", "Alternative answer"),
    ]

    graph = project_turn_graph(entries, "a3")
    first, second, alternative = graph["nodes"]

    assert [node["parent_id"] for node in graph["nodes"]] == [None, "u1", "u1"]
    assert [node["active"] for node in graph["nodes"]] == [True, False, True]
    assert first["continue_entry_id"] == "t1"
    assert first["tools"] == [
        {"name": "search_papers", "content": "evidence", "is_error": False}
    ]
    assert [message["content"] for message in second["messages"]] == [
        "Question", "First answer", "Continue", "Second answer"
    ]
    assert [message["content"] for message in alternative["messages"]] == [
        "Question", "Try another route", "Alternative answer"
    ]


def test_retry_from_user_hides_old_answer_on_active_path() -> None:
    entries = [entry("u1", None, "user", "Question"), entry("a1", "u1", "assistant", "Old")]
    graph = project_turn_graph(entries, "u1")

    assert graph["nodes"][0]["continue_entry_id"] == "u1"
    assert [message["content"] for message in graph["nodes"][0]["messages"]] == [
        "Question"
    ]
    assert graph["nodes"][0]["other_answers"] == ["Old"]


def test_empty_graph() -> None:
    assert project_turn_graph([], None) == {"active_leaf_id": None, "nodes": []}
