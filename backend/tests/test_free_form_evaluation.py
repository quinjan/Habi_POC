from pathlib import Path
import os
import subprocess
import sys

from backend.app.evaluation.free_form import (
    FIXTURE_ID,
    compare_domain_output,
    load_fixture_manifest,
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
        "fixture_version": 6,
        "rationale": (
            "Approved fixture v6 separating commercial package wording from Material "
            "identity and naming delivery by its worked-on subject."
        ),
    }
    assert manifest["expected_result"]["candidates"] == [
        {
            "shape": "bundled",
            "concept_names": [
                "Daikin split-type air conditioner",
                "Air conditioning installation",
            ],
            "provider_state": "external",
            "provider_name": "CoolAir Mechanical Services",
            "price": "120000",
            "annotation_count": 8,
        },
        {
            "shape": "material",
            "concept_names": ["100 mm PVC pressure pipe"],
            "provider_state": "external",
            "provider_name": "BuildMart Trading",
            "price": "32500",
            "annotation_count": 2,
        },
        {
            "shape": "service",
            "concept_names": ["PVC pressure pipe delivery"],
            "provider_state": "external",
            "provider_name": "BuildMart Trading",
            "price": "1500",
            "annotation_count": 0,
        },
        {
            "shape": "service",
            "concept_names": ["Site cleanup"],
            "provider_state": "internal",
            "provider_name": None,
            "price": "18000",
            "annotation_count": 2,
        },
        {
            "shape": "material",
            "concept_names": ["Non-shrink grout"],
            "provider_state": "unknown",
            "provider_name": None,
            "price": "8500",
            "annotation_count": 2,
        },
        {
            "shape": "material",
            "concept_names": ["16 mm Grade 60 deformed reinforcing bar"],
            "provider_state": "external",
            "provider_name": "MetroSteel",
            "price": "28800",
            "annotation_count": 0,
        },
        {
            "shape": "service",
            "concept_names": ["Domestic water lines pressure testing"],
            "provider_state": "internal",
            "provider_name": None,
            "price": "9000",
            "annotation_count": 0,
        },
    ]


def test_poc_evaluation_command_requires_named_human_approval():
    result = subprocess.run(
        [sys.executable, "backend/scripts/run_free_form_evaluation.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "--approved-by" in result.stderr


def test_poc_evaluation_refuses_a_non_eval_database_name_before_connecting():
    environment = os.environ.copy()
    environment.update(
        {
            "HABI_EVAL_DATABASE_URL": (
                "postgresql+psycopg://test-user@127.0.0.1:1/production"
            ),
            "OPENAI_API_KEY": "test-only-placeholder",
            "OPENAI_FREE_FORM_MODEL": "gpt-5.4-2026-03-05",
            "OPENAI_FREE_FORM_REASONING_EFFORT": "medium",
            "OPENAI_FREE_FORM_RETRIES_ENABLED": "false",
            "OPENAI_CLIENT_MAX_RETRIES": "0",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "backend/scripts/run_free_form_evaluation.py",
            "--approved-by",
            "Quinjan",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    assert result.returncode != 0
    assert "database name must start with habi_eval_" in result.stderr


def test_poc_evaluation_renders_a_short_pr_scorecard():
    manifest = {
        "fixture_id": "mixed-completed-project-baseline",
        "fixture_version": 6,
        "expected_result": {
            "candidates": [{}, {}, {}, {}, {}, {}, {}],
            "required_omissions": ["planned work"],
        },
    }
    actual = {
        "candidates": [{}, {}, {}, {}, {}, {}, {}],
        "required_omissions": ["planned work"],
    }

    assert render_markdown_scorecard(
        prd_issue=36,
        manifest=manifest,
        model="gpt-5.4-2026-03-05",
        actual=actual,
        differences=[],
        model_call_count=1,
        paid_call_approved_by="Quinjan",
    ) == (
        "## Real-Model Evaluation\n\n"
        "- PRD: #36\n"
        "- Fixture: mixed-completed-project-baseline v6\n"
        "- Model: gpt-5.4-2026-03-05\n"
        "- Model calls: 1\n"
        "- Paid call approved by: Quinjan\n"
        "- Result: PASS\n"
        "- Purchase Lines: 7/7\n"
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


def test_comparator_treats_hyphens_as_spaces_only_in_concept_names():
    expected = {
        "candidates": [
            {
                "concept_names": [
                    "Air conditioning installation",
                    "Domestic water lines pressure testing",
                ]
            }
        ]
    }
    punctuation_variant = {
        "candidates": [
            {
                "concept_names": [
                    "Air-conditioning installation",
                    "Domestic water lines pressure testing",
                ]
            }
        ]
    }
    singular_variant = {
        "candidates": [
            {
                "concept_names": [
                    "Air-conditioning installation",
                    "Domestic water line pressure testing",
                ]
            }
        ]
    }

    assert compare_domain_output(expected, punctuation_variant) == []
    assert compare_domain_output(expected, singular_variant)
