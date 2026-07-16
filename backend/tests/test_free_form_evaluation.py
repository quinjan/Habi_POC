import json

import pytest

from backend.app.evaluation.free_form import (
    EvaluationContractError,
    FIXTURE_ORDER,
    PROMOTION_ORDER,
    compare_domain_output,
    content_sha256,
    load_fixture_manifests,
    output_affecting_change,
    sanitized_artifact_digest,
    validate_promotion_record,
)


def test_exactly_eight_versioned_manifests_have_complete_draft_contracts():
    manifests = load_fixture_manifests(
        __import__("pathlib").Path("backend/evals/free-form/fixtures"),
        require_approved=False,
    )

    assert [manifest["fixture_id"] for manifest in manifests] == list(FIXTURE_ORDER)
    assert all(manifest["fixture_version"] >= 1 for manifest in manifests)
    assert all("candidates" in manifest["expected_result"] for manifest in manifests)
    assert len({content_sha256(manifest) for manifest in manifests}) == 8


def test_promotion_loader_refuses_a_manifest_pending_human_approval():
    with pytest.raises(EvaluationContractError, match="needs human approval"):
        load_fixture_manifests(
            __import__("pathlib").Path("backend/evals/free-form/fixtures"),
            require_approved=True,
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


def test_artifact_sanitization_removes_credentials_before_hashing():
    sanitized, digest = sanitized_artifact_digest(
        {"authorization": "Bearer dangerous", "metrics": {"tokens": 42}}
    )

    assert sanitized["authorization"] == "[REDACTED]"
    assert "dangerous" not in json.dumps(sanitized)
    assert len(digest) == 64


def test_promotion_record_requires_the_exact_ten_call_matrix():
    attempts = [
        {
            "fixture_id": fixture_id,
            "model_call_count": 1,
            "retry_enabled": False,
            "outcome": "pass",
            "strict_comparison_passed": True,
        }
        for fixture_id in PROMOTION_ORDER
    ]
    record = {
        "attempts": attempts,
        "fingerprints": {
            "prompt_template_sha256": "a" * 64,
            "response_schema_sha256": "b" * 64,
            "request_config_sha256": "c" * 64,
        },
    }

    validate_promotion_record(record)
    record["attempts"] = attempts[:-1]
    with pytest.raises(EvaluationContractError, match="exactly 10"):
        validate_promotion_record(record)


def test_output_affecting_change_detection_keeps_paid_suite_explicit():
    assert output_affecting_change(["backend/app/processing/openai_provider.py"])
    assert output_affecting_change(["backend/evals/free-form/fixtures/mixed.json"])
    assert not output_affecting_change(["frontend/src/styles.css", "docs/readme.md"])
