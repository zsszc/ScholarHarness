from scholar_harness.papers.models import Paper, Passage
from scholar_harness.papers.repository import InMemoryPaperRepository
from scholar_harness.workbench import WORKBENCH_HTML


def test_in_memory_catalog_is_deterministic_and_limited() -> None:
    repository = InMemoryPaperRepository()
    repository.add(Paper(id="z", title="beta"))
    repository.add(
        Paper(
            id="b",
            title="Alpha",
            authors=["Ada"],
            year=2026,
            passages=[Passage(id="p1", text="evidence")],
        )
    )
    repository.add(Paper(id="a", title="alpha"))

    catalog = repository.list(limit=2)

    assert [paper.id for paper in catalog] == ["a", "b"]
    assert catalog[1].authors == ["Ada"]
    assert catalog[1].passage_count == 1


def test_workbench_contains_all_areas_and_no_external_assets() -> None:
    for page in (
        "overview",
        "guide",
        "chat",
        "runs",
        "evaluations",
        "memories",
        "library",
    ):
        assert f'data-page="{page}"' in WORKBENCH_HTML
    assert "工作台导航" in WORKBENCH_HTML
    assert "Content-Security-Policy" in WORKBENCH_HTML
    assert '<script src=' not in WORKBENCH_HTML
    assert '<link rel="stylesheet"' not in WORKBENCH_HTML
    assert "http://" not in WORKBENCH_HTML
    assert "https://" not in WORKBENCH_HTML


def test_workbench_is_chinese_guided_and_keeps_technical_terms() -> None:
    for label in (
        "使用指南",
        "Agent 对话",
        "评测实验室",
        "本地服务已连接",
        "candidate（候选）",
        "confirmed（可信）",
        "Case / Suite",
        "Tool Calling",
    ):
        assert label in WORKBENCH_HTML
    assert 'guide:"使用指南"' in WORKBENCH_HTML
    assert 'connected:"已连接"' in WORKBENCH_HTML
    assert 'running:"运行中"' in WORKBENCH_HTML


def test_workbench_uses_safe_dom_and_explicit_panel_states() -> None:
    assert ".innerHTML" not in WORKBENCH_HTML
    assert ".textContent" in WORKBENCH_HTML
    assert ".replaceChildren" in WORKBENCH_HTML
    assert '"loading"' in WORKBENCH_HTML
    assert '"empty"' in WORKBENCH_HTML
    assert '"error"' in WORKBENCH_HTML
    assert "/memories/${encodeURIComponent(memoryId)}/${action}" in WORKBENCH_HTML
    assert "/internal/tools/search_papers" in WORKBENCH_HTML
    assert "lexical_rank" in WORKBENCH_HTML
    assert "vector_rank" in WORKBENCH_HTML
    assert "if(!target){const host=byId(panel);if(!host)return" in WORKBENCH_HTML
    assert "target.dataset.state=panel;host.prepend(target)" in WORKBENCH_HTML


def test_workbench_chat_uses_server_session_gateway() -> None:
    assert "/chat/sessions" in WORKBENCH_HTML
    assert "new WebSocket" in WORKBENCH_HTML
    assert "OPENAI_MODEL" in WORKBENCH_HTML
    for command in ("prompt", "abort", "compact", "fork", "entries"):
        assert f'type:"{command}"' in WORKBENCH_HTML
    assert "api_key" not in WORKBENCH_HTML
    assert "base_url" not in WORKBENCH_HTML
    assert 'make("div",`chat-message ${role}`,text)' in WORKBENCH_HTML
    assert 'event.type==="context_injection"' in WORKBENCH_HTML
    assert "Memory 上下文 · ${event.data.status}" in WORKBENCH_HTML
    assert "event.code===4403" in WORKBENCH_HTML
    assert "持久会话仍已保留" in WORKBENCH_HTML


def test_branch_graph_selects_without_mutation_and_forks_explicitly() -> None:
    assert '"研究会话图"' in WORKBENCH_HTML
    assert "MiniPy · 非 Pi 原生会话" in WORKBENCH_HTML
    assert "/chat/sessions/${encodeURIComponent(sessionId)}/graph" in WORKBENCH_HTML
    assert (
        'button.addEventListener("click",()=>{state.selectedTurnId=node.id;renderTurnGraph()})'
        in WORKBENCH_HTML
    )
    assert 'sendChatCommand({type:"fork",entry_id:anchor})' in WORKBENCH_HTML
    assert 'anchor=retry?node.id:node.continue_entry_id' in WORKBENCH_HTML
    assert "selected.messages.forEach" in WORKBENCH_HTML
    assert 'make("pre","",tool.content)' in WORKBENCH_HTML


def test_workbench_evaluation_lab_uses_public_contracts_and_safe_evidence() -> None:
    assert "评测实验室" in WORKBENCH_HTML
    assert 'request("/evaluations/cases?limit=500")' in WORKBENCH_HTML
    assert 'request("/evaluations/results?limit=500")' in WORKBENCH_HTML
    assert "/evaluations/cases/${encodeURIComponent(state.selectedCase.id)}/runs/" in WORKBENCH_HTML
    assert (
        "/evaluations/cases/${encodeURIComponent(state.selectedCase.id)}/execute"
        in WORKBENCH_HTML
    )
    assert 'id="execute-eval-case"' in WORKBENCH_HTML
    assert "execution.event_count" in WORKBENCH_HTML
    assert 'make("pre","",pretty(check.expected))' in WORKBENCH_HTML
    assert 'make("pre","",pretty(check.observed))' in WORKBENCH_HTML
    assert 'value.split(",").map(item=>item.trim()).filter(Boolean)' in WORKBENCH_HTML
    for field in (
        "eval-required-memories",
        "eval-forbidden-memories",
        "eval-context-status",
        "eval-max-context-items",
    ):
        assert f'id="{field}"' in WORKBENCH_HTML
    assert "expected.required_memory_ids||[]" in WORKBENCH_HTML
    assert "expectations.context_status" in WORKBENCH_HTML
    assert 'state.evaluationRuns.filter(run=>run.status!=="running")' in WORKBENCH_HTML
    for metric in ("metric-evals", "metric-eval-passed", "metric-regressions"):
        assert f'id="{metric}"' in WORKBENCH_HTML


def test_workbench_suite_workspace_uses_ordered_public_contracts() -> None:
    assert 'data-page="evaluation-suites"' in WORKBENCH_HTML
    assert 'data-state="evaluation-suites"' in WORKBENCH_HTML
    assert 'id="eval-suite-form"' in WORKBENCH_HTML
    assert 'id="eval-suite-members"' in WORKBENCH_HTML
    assert 'id="execute-eval-suite"' in WORKBENCH_HTML
    assert 'request("/evaluations/suites?limit=500")' in WORKBENCH_HTML
    assert 'request("/evaluations/suite-runs?limit=500")' in WORKBENCH_HTML
    assert (
        "/evaluations/suites/${encodeURIComponent(state.selectedSuite.id)}/execute"
        in WORKBENCH_HTML
    )
    assert "case_ids:[...state.suiteDraftCaseIds]" in WORKBENCH_HTML
    assert "suiteDraftName" in WORKBENCH_HTML
    assert 'byId("eval-suite-name").addEventListener("input"' in WORKBENCH_HTML
    assert "moveSuiteCase(index,offset)" in WORKBENCH_HTML
    assert "removeSuiteCase(index)" in WORKBENCH_HTML
    assert "item.runtime_error||\"—\"" in WORKBENCH_HTML
    assert "item.error||\"—\"" in WORKBENCH_HTML
    assert '"metric-suite-runs"' in WORKBENCH_HTML
    assert '"metric-suite-passed"' in WORKBENCH_HTML
    assert "runs.filter(run=>run.passed).length" in WORKBENCH_HTML
