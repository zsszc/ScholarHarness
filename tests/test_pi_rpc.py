import sys
from pathlib import Path

from scholar_harness.runtimes.pi_rpc import PiRpcClient, PiRuntime


def test_pi_extension_hides_and_forwards_memory_provenance() -> None:
    source = Path("pi-extension/index.ts").read_text()

    for field in (
        "source_session_id",
        "source_entry_id",
        "trace_run_id",
        "source_tool_call_id",
    ):
        assert field not in source
    assert "executionHeaders(toolCallId, ctx)" in source
    assert '"X-Scholar-Session-Id": ctx.sessionManager.getSessionId()' in source
    assert '"X-Scholar-Tool-Call-Id": toolCallId' in source


async def test_pi_runtime_streams_events_and_normalizes_entries() -> None:
    fake_pi = Path(__file__).parent / "fixtures" / "fake_pi.py"
    client = PiRpcClient((sys.executable, str(fake_pi)))
    runtime = PiRuntime(client)

    try:
        await runtime.start()
        events = [event async for event in runtime.stream("hello")]
        entries = await runtime.get_entries()
    finally:
        await runtime.close()

    assert [event.type for event in events] == [
        "agent_start",
        "message_update",
        "agent_end",
        "agent_settled",
    ]
    assert all(event.session_id == "fake-session" for event in events)
    assert entries[0].entry_id == "entry-1"
    assert entries[0].parent_id is None
    assert entries[0].session_id == "fake-session"
