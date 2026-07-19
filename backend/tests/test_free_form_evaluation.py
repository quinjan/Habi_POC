from pathlib import Path
import subprocess
import sys

from backend.app.evaluation.free_form import (
    FIXTURE_ID,
    compare_domain_output,
    load_fixture_manifest,
    output_affecting_change,
    render_markdown_scorecard,
)


def test_poc_evaluation_loads_one_mixed_baseline_fixture():
    manifest = load_fixture_manifest(
        Path("backend/evals/free-form/fixtures"),
        require_approved=False,
    )

    assert manifest["fixture_id"] == FIXTURE_ID == "mixed-completed-project-baseline"


def test_poc_fixture_has_human_approval_for_its_current_version():
    manifest = load_fixture_manifest(
        Path("backend/evals/free-form/fixtures"),
        require_approved=True,
    )

    assert manifest["human_approval"] == {
        "status": "approved",
        "reviewer": "Quinjan",
        "approval_date": "2026-07-19",
        "fixture_version": 1,
        "rationale": "Approved as the single representative POC evaluation fixture for PRD #36.",
    }


def test_poc_evaluation_command_requires_named_human_approval():
    result = subprocess.run(
        [sys.executable, "backend/scripts/run_free_form_evaluation.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "--approved-by" in result.stderr


def test_poc_evaluation_renders_a_short_pr_scorecard():
    manifest = {
        "fixture_id": "mixed-completed-project-baseline",
        "fixture_version": 1,
        "expected_result": {
            "candidates": [{}, {}, {}, {}],
            "required_omissions": ["planned work"],
        },
    }
    actual = {
        "candidates": [{}, {}, {}, {}],
        "required_omissions": ["planned work"],
    }

    assert render_markdown_scorecard(
        prd_issue=36,
        manifest=manifest,
        model="gpt-5.5-2026-04-23",
        actual=actual,
        differences=[],
        model_call_count=1,
        paid_call_approved_by="Quinjan",
    ) == (
        "## Real-Model Evaluation\n\n"
        "- PRD: #36\n"
        "- Fixture: mixed-completed-project-baseline v1\n"
        "- Model: gpt-5.5-2026-04-23\n"
        "- Model calls: 1\n"
        "- Paid call approved by: Quinjan\n"
        "- Result: PASS\n"
        "- Purchase Lines: 4/4\n"
        "- Required exclusions: PASS\n"
        "- Human merge review: required"
    )


def test_comparator_is_order_strict_and_only_normalizes_documented_transport_fields():
    expected = {"candidates": [{"id": "fixture-a", "name": "Pipe", "price": "1.00"}]}
    equivalent = {"candidates": [{"id": 99, "name": "Pipe", "price": "1"}]}
    reordered = {
        "candidates": [
            {"id": 1, "name": "Service", "price": "1"},
            {"id": 2, "name": "Pipe", "price": "1"},
        ]
    }

    assert compare_domain_output(expected, equivalent) == []
    assert compare_domain_output(expected, reordered)


def test_output_affecting_change_detection_keeps_paid_suite_explicit():
    assert output_affecting_change(["backend/app/processing/openai_provider.py"])
    assert output_affecting_change(["backend/evals/free-form/fixtures/mixed.json"])
    assert not output_affecting_change(["frontend/src/styles.css", "docs/readme.md"])
