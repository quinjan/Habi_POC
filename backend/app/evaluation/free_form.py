from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from typing import Any


FIXTURE_ID = "mixed-completed-project-baseline"
IGNORED_COMPARISON_FIELDS = frozenset(
    {
        "id",
        "created_at",
        "updated_at",
        "request_id",
        "source_submission_id",
        "project_workspace_id",
        "review_batch_id",
        "proposal_id",
    }
)
class EvaluationContractError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_fixture_manifest(directory: Path, *, require_approved: bool = True) -> dict:
    paths = sorted(directory.glob("*.json"))
    if len(paths) != 1:
        raise EvaluationContractError("The POC evaluation must contain exactly one fixture")
    manifest = json.loads(paths[0].read_text(encoding="utf-8"))
    if manifest.get("fixture_id") != FIXTURE_ID:
        raise EvaluationContractError(f"The POC fixture must be {FIXTURE_ID}")
    validate_fixture_manifest(manifest, require_approved=require_approved)
    return manifest


def validate_fixture_manifest(manifest: dict, *, require_approved: bool = True) -> None:
    required = {
        "fixture_id",
        "fixture_version",
        "family",
        "source_text",
        "contractor_assigned",
        "project_memory",
        "taxonomy_vocabulary",
        "expected_result",
        "human_approval",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise EvaluationContractError(f"Fixture manifest is missing: {', '.join(missing)}")
    if manifest["fixture_id"] != FIXTURE_ID:
        raise EvaluationContractError(f"Fixture ID must be {FIXTURE_ID}")
    if not isinstance(manifest["source_text"], str) or not manifest["source_text"].strip():
        raise EvaluationContractError("Fixture source text must be preserved and non-empty")
    if not isinstance(manifest["project_memory"], list) or not isinstance(
        manifest["taxonomy_vocabulary"], list
    ):
        raise EvaluationContractError("Fixture memory and taxonomy must be explicit lists")
    approval = manifest["human_approval"]
    approval_fields = {"status", "reviewer", "approval_date", "fixture_version", "rationale"}
    if not isinstance(approval, dict) or approval_fields - set(approval):
        raise EvaluationContractError("Fixture requires complete Human-Approved Golden Result metadata")
    if approval["fixture_version"] != manifest["fixture_version"]:
        raise EvaluationContractError("Human approval must cover the current fixture version")
    if require_approved and approval["status"] != "approved":
        raise EvaluationContractError(f"Fixture {manifest['fixture_id']} still needs human approval")


def compare_domain_output(expected: Any, actual: Any) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    _compare(_normalize(expected), _normalize(actual), "$", differences)
    return differences


def render_markdown_scorecard(
    *,
    prd_issue: int,
    manifest: dict,
    model: str,
    actual: dict,
    differences: list[dict[str, Any]],
    model_call_count: int,
    paid_call_approved_by: str,
) -> str:
    expected = manifest["expected_result"]
    passed = not differences and model_call_count == 1
    actual_count = len(actual.get("candidates", []))
    expected_count = len(expected.get("candidates", []))
    exclusions_passed = actual.get("required_omissions") == expected.get("required_omissions")
    return "\n".join(
        (
            "## Real-Model Evaluation",
            "",
            f"- PRD: #{prd_issue}",
            f"- Fixture: {manifest['fixture_id']} v{manifest['fixture_version']}",
            f"- Model: {model}",
            f"- Model calls: {model_call_count}",
            f"- Paid call approved by: {paid_call_approved_by}",
            f"- Result: {'PASS' if passed else 'FAIL'}",
            f"- Purchase Lines: {actual_count}/{expected_count}",
            f"- Required exclusions: {'PASS' if exclusions_passed else 'FAIL'}",
            "- Human merge review: required",
        )
    )


def _compare(expected: Any, actual: Any, path: str, differences: list[dict[str, Any]]) -> None:
    if type(expected) is not type(actual):
        differences.append({"path": path, "expected": expected, "actual": actual})
        return
    if isinstance(expected, dict):
        expected_keys = set(expected)
        actual_keys = set(actual)
        if expected_keys != actual_keys:
            differences.append(
                {
                    "path": path,
                    "expected_keys": sorted(expected_keys),
                    "actual_keys": sorted(actual_keys),
                }
            )
        for key in sorted(expected_keys & actual_keys):
            _compare(expected[key], actual[key], f"{path}.{key}", differences)
        return
    if isinstance(expected, list):
        if len(expected) != len(actual):
            differences.append({"path": path, "expected_length": len(expected), "actual_length": len(actual)})
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            _compare(expected_item, actual_item, f"{path}[{index}]", differences)
        return
    if expected != actual:
        differences.append({"path": path, "expected": expected, "actual": actual})


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize(item)
            for key, item in value.items()
            if key not in IGNORED_COMPARISON_FIELDS
        }
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, str) and re.fullmatch(r"-?\d+(?:\.\d+)?", value.strip()):
        try:
            decimal = Decimal(value)
        except InvalidOperation:
            return value
        rendered = format(decimal, "f")
        return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
    return value
