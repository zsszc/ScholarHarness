from __future__ import annotations

import os
import tempfile
from pathlib import Path
from xml.etree import ElementTree

from scholar_harness.evaluations.models import EvaluationSuiteItem, EvaluationSuiteRun


def suite_run_json(run: EvaluationSuiteRun) -> str:
    return f"{run.model_dump_json(indent=2)}\n"


def suite_run_junit(run: EvaluationSuiteRun) -> str:
    duration = max(0.0, (run.ended_at - run.started_at).total_seconds())
    root = ElementTree.Element("testsuites")
    suite = ElementTree.SubElement(
        root,
        "testsuite",
        {
            "name": run.suite_name,
            "tests": str(run.total_count),
            "failures": str(run.failed_count),
            "errors": str(run.error_count),
            "time": f"{duration:.6f}",
            "timestamp": run.started_at.isoformat(),
        },
    )
    properties = ElementTree.SubElement(suite, "properties")
    for name, value in (
        ("suite_id", run.suite_id),
        ("suite_run_id", run.id),
        ("passed", str(run.passed).lower()),
        ("passed_count", run.passed_count),
        ("failed_count", run.failed_count),
        ("error_count", run.error_count),
    ):
        ElementTree.SubElement(
            properties, "property", {"name": name, "value": str(value)}
        )
    for item in run.items:
        _append_testcase(suite, run, item)
    payload = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
    return f"{payload.decode('utf-8')}\n"


def _append_testcase(
    suite: ElementTree.Element,
    run: EvaluationSuiteRun,
    item: EvaluationSuiteItem,
) -> None:
    case = ElementTree.SubElement(
        suite,
        "testcase",
        {"name": item.case_name, "classname": run.suite_name},
    )
    properties = ElementTree.SubElement(case, "properties")
    for name, value in (
        ("position", item.position),
        ("case_id", item.case_id),
        ("run_id", item.run_id or ""),
        ("result_id", item.result_id or ""),
        ("score", "" if item.score is None else item.score),
        ("event_count", item.event_count),
        ("runtime_error", item.runtime_error or ""),
    ):
        ElementTree.SubElement(
            properties, "property", {"name": name, "value": str(value)}
        )
    if item.error is not None:
        error = ElementTree.SubElement(
            case, "error", {"message": item.error, "type": item.error}
        )
        error.text = f"Suite item ended with {item.error}"
    elif not item.passed:
        message = (
            f"Evaluation score {item.score if item.score is not None else 'unavailable'} "
            f"did not meet threshold {item.pass_threshold}"
        )
        failure = ElementTree.SubElement(
            case, "failure", {"message": message, "type": "evaluation_failure"}
        )
        failure.text = message


def write_text_atomic(path: Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
