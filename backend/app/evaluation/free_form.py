from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable


FIXTURE_ORDER = (
    "mixed-completed-project-baseline",
    "multi-concept-installation",
    "partial-multiple-relationships",
    "provider-boundary",
    "price-attribution-package-override",
    "finality-workflow-noise",
    "annotation-targeting-ambiguity",
    "project-memory-collision-resistance",
)
PROMOTION_ORDER = (*FIXTURE_ORDER, FIXTURE_ORDER[0], FIXTURE_ORDER[1])
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
SENSITIVE_KEY_PARTS = ("api_key", "authorization", "credential", "password", "secret")
OUTPUT_AFFECTING_PREFIXES = (
    "backend/app/processing/",
    "backend/app/evaluation/",
    "backend/evals/free-form/fixtures/",
    "backend/requirements.txt",
)


class EvaluationContractError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_sha256(value: Any) -> str:
    content = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_fixture_manifests(directory: Path, *, require_approved: bool = True) -> list[dict]:
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))]
    by_id = {manifest.get("fixture_id"): manifest for manifest in manifests}
    if len(manifests) != len(FIXTURE_ORDER) or set(by_id) != set(FIXTURE_ORDER):
        raise EvaluationContractError("The suite must contain exactly the eight required fixtures")
    ordered = [by_id[fixture_id] for fixture_id in FIXTURE_ORDER]
    for manifest in ordered:
        validate_fixture_manifest(manifest, require_approved=require_approved)
    return ordered


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
    if manifest["fixture_id"] not in FIXTURE_ORDER:
        raise EvaluationContractError("Fixture ID is not part of the eight-fixture contract")
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
    _reject_sensitive_values(manifest)


def compare_domain_output(expected: Any, actual: Any) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    _compare(_normalize(expected), _normalize(actual), "$", differences)
    return differences


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


def sanitized_artifact_digest(value: Any) -> tuple[Any, str]:
    sanitized = _sanitize(deepcopy(value))
    return sanitized, content_sha256(sanitized)


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _is_sensitive_key(key) else _sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _reject_sensitive_values(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _is_sensitive_key(key):
                raise EvaluationContractError(f"Sensitive field is forbidden at {path}.{key}")
            _reject_sensitive_values(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_sensitive_values(item, f"{path}[{index}]")


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).casefold()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def validate_promotion_record(record: dict) -> None:
    _reject_sensitive_values(record)
    attempts = record.get("attempts")
    if not isinstance(attempts, list) or len(attempts) != 10:
        raise EvaluationContractError("A qualifying promotion record requires exactly 10 attempts")
    if [attempt.get("fixture_id") for attempt in attempts] != list(PROMOTION_ORDER):
        raise EvaluationContractError("Promotion attempts are not in the required fixture/sentinel order")
    for attempt in attempts:
        if attempt.get("model_call_count") != 1 or attempt.get("retry_enabled") is not False:
            raise EvaluationContractError("Every promotion attempt must be one retry-disabled model call")
        if attempt.get("outcome") != "pass" or attempt.get("strict_comparison_passed") is not True:
            raise EvaluationContractError("All 10 promotion attempts must pass strict comparison")
    fingerprints = record.get("fingerprints", {})
    for field in ("prompt_template_sha256", "response_schema_sha256", "request_config_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(fingerprints.get(field, ""))):
            raise EvaluationContractError(f"Promotion fingerprint {field} is invalid")


def output_affecting_change(paths: Iterable[str]) -> bool:
    normalized_paths = [path.replace("\\", "/").lstrip("./") for path in paths]
    return any(
        path.startswith(prefix)
        for path in normalized_paths
        for prefix in OUTPUT_AFFECTING_PREFIXES
    )
