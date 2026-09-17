import sys
from pathlib import Path

from scholar_harness.runtimes.pi_rpc import PiRpcClient, PiRuntime


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
