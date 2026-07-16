"""Run the explicit paid ten-call free-form promotion suite.

This command is intentionally outside pytest/ordinary CI. It refuses draft fixtures,
ambient databases, retries, and missing credentials before making a model request.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess
import time
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from backend.app.database import Base, create_sqlalchemy_engine
from backend.app.evaluation.free_form import (
    PROMOTION_ORDER,
    canonical_json,
    compare_domain_output,
    content_sha256,
    load_fixture_manifests,
    sanitized_artifact_digest,
    validate_promotion_record,
)
from backend.app.main import create_app
from backend.app.memory.models import Material, MemoryRecord, Provider, Service
from backend.app.processing.__main__ import create_openai_provider_from_env
from backend.app.processing.openai_provider import (
    EXTRACTION_SYSTEM_PROMPT,
    FREE_FORM_PURCHASE_LINE_EXTRACTION_SCHEMA,
)
from backend.app.processing.worker import run_once
from backend.app.taxonomy.models import TaxonomyNode


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "backend" / "evals" / "free-form" / "fixtures"
ARTIFACT_ROOT = ROOT / ".habi-evals" / "free-form"
PROMOTION_ROOT = ROOT / "docs" / "evals" / "promotions" / "free-form"
EVALUATOR_VERSION = "1"


class PromotionAttemptError(RuntimeError):
    def __init__(self, message: str, *, outcome: str, calls: int, rendered_input: str, usage: dict):
        super().__init__(message)
        self.outcome = outcome
        self.calls = calls
        self.rendered_input = rendered_input
        self.usage = usage


class CountingProvider:
    def __init__(self, provider):
        self.provider = provider
        self.calls = 0

    def __getattr__(self, name):
        return getattr(self.provider, name)

    def extract_purchase_lines(
        self,
        *,
        original_text: str,
        source_submission_id: int,
        memory_context: dict,
        reasoning_effort: str,
        repair_context: dict | None = None,
    ):
        self.calls += 1
        return self.provider.extract_purchase_lines(
            original_text=original_text,
            source_submission_id=source_submission_id,
            memory_context=memory_context,
            reasoning_effort=reasoning_effort,
            repair_context=repair_context,
        )


def main() -> int:
    manifests = load_fixture_manifests(FIXTURES, require_approved=True)
    by_id = {manifest["fixture_id"]: manifest for manifest in manifests}
    database_url = _required_eval_database_url()
    _require_primary_configuration()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifact_directory = ARTIFACT_ROOT / run_id
    artifact_directory.mkdir(parents=True, exist_ok=False)
    attempts: list[dict] = []

    for position, fixture_id in enumerate(PROMOTION_ORDER, start=1):
        manifest = by_id[fixture_id]
        started = time.perf_counter()
        try:
            actual, call_count, rendered_input, usage = _run_fixture(database_url, manifest)
            differences = compare_domain_output(manifest["expected_result"], actual)
            outcome = "pass" if not differences and call_count == 1 else "model_failure"
        except PromotionAttemptError as error:
            actual = None
            call_count = error.calls
            rendered_input = error.rendered_input
            usage = error.usage
            differences = [{"path": "$", "message": str(error)}]
            outcome = error.outcome
        except Exception as error:
            actual = None
            call_count = 0
            rendered_input = ""
            usage = {}
            differences = [{"path": "$", "error": type(error).__name__, "message": str(error)}]
            outcome = "infrastructure_error"
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        artifact, artifact_sha256 = sanitized_artifact_digest(
            {
                "fixture_id": fixture_id,
                "outcome": outcome,
                "differences": differences,
                "terminal_result": actual,
            }
        )
        (artifact_directory / f"{position:02d}-{fixture_id}.json").write_text(
            json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        attempt = {
            "position": position,
            "fixture_id": fixture_id,
            "fixture_version": manifest["fixture_version"],
            "manifest_sha256": content_sha256(manifest),
            "rendered_input_sha256": content_sha256(rendered_input),
            "model_call_count": call_count,
            "retry_enabled": False,
            "outcome": outcome,
            "strict_comparison_passed": not differences,
            "latency_ms": latency_ms,
            "usage": usage,
            "estimated_cost": _estimated_cost(usage),
            "artifact_sha256": artifact_sha256,
        }
        attempts.append(attempt)
        if outcome != "pass":
            (artifact_directory / "incomplete-run.json").write_text(
                json.dumps({"run_id": run_id, "attempts": attempts}, indent=2),
                encoding="utf-8",
            )
            raise SystemExit(
                f"Promotion run stopped at {fixture_id}: {outcome}. Start a new complete run."
            )

    request_config = {
        "model": os.environ["OPENAI_FREE_FORM_MODEL"],
        "reasoning_effort": os.environ["OPENAI_FREE_FORM_REASONING_EFFORT"],
        "application_retries_enabled": False,
        "client_max_retries": 0,
    }
    record = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "evaluator_version": EVALUATOR_VERSION,
        "repository_commit": _git_commit(),
        "configuration": request_config,
        "fingerprints": {
            "prompt_template_sha256": content_sha256(EXTRACTION_SYSTEM_PROMPT),
            "response_schema_sha256": content_sha256(FREE_FORM_PURCHASE_LINE_EXTRACTION_SCHEMA),
            "request_config_sha256": content_sha256(request_config),
        },
        "attempts": attempts,
        "metrics": _latency_metrics(attempts),
        "prior_attempt_summaries": [],
    }
    validate_promotion_record(record)
    PROMOTION_ROOT.mkdir(parents=True, exist_ok=True)
    output_path = PROMOTION_ROOT / f"{run_id}.json"
    output_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(output_path.relative_to(ROOT))
    return 0


def _run_fixture(database_url: str, manifest: dict) -> tuple[dict, int, str, dict]:
    engine = create_sqlalchemy_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, create_tables=False)
    with TestClient(app) as client:
        project = client.post(
            "/api/project-workspaces",
            json={
                "project_name": f"Evaluation: {manifest['fixture_id']}",
                "project_type": "Synthetic completed-project evaluation",
                "location": "Synthetic",
                "completion_year": 2026,
                "contractor_assigned": manifest["contractor_assigned"],
            },
        ).json()
        _seed_context(app.state.session_factory, project["id"], manifest)
        submission = client.post(
            f"/api/project-workspaces/{project['id']}/manual-source-entries",
            json={"entry_type": "free_form_text", "original_text": manifest["source_text"]},
        ).json()
        provider = CountingProvider(create_openai_provider_from_env())
        run_once(app.state.session_factory, ai_provider=provider)
        job = client.get(
            f"/api/project-workspaces/{project['id']}/processing-jobs/"
            f"{submission['processing_job']['id']}"
        ).json()["processing_job"]
        rendered_input = (
            provider.provider.rendered_free_form_inputs[-1]
            if provider.provider.rendered_free_form_inputs
            else ""
        )
        usage = (
            provider.provider.free_form_usage_events[-1]
            if provider.provider.free_form_usage_events
            else {}
        )
        if job["status"] != "review_ready":
            message = f"Production worker ended as {job['status']}: {job.get('error_message')}"
            diagnostics = job.get("diagnostics") or {}
            provider_failure = diagnostics.get("failure") == "provider_runtime_error"
            outcome = (
                "infrastructure_error"
                if provider_failure and _looks_like_infrastructure_error(message)
                else "model_failure"
            )
            raise PromotionAttemptError(
                message,
                outcome=outcome,
                calls=provider.calls,
                rendered_input=rendered_input,
                usage=usage,
            )
        review = client.get(
            f"/api/project-workspaces/{project['id']}/review-batches/{job['review_batch_id']}"
        ).json()
        actual = _scorecard_view(review["candidates"], manifest["expected_result"])
    engine.dispose()
    return actual, provider.calls, rendered_input, usage


def _seed_context(session_factory, project_id: int, manifest: dict) -> None:
    paths = set(manifest["taxonomy_vocabulary"])
    paths.update(record["category_path"] for record in manifest["project_memory"])
    with session_factory() as session, session.begin():
        leaves: dict[str, TaxonomyNode] = {}
        parents: dict[str, TaxonomyNode] = {}
        for path in sorted(paths):
            parent_name, leaf_name = path.split(" / ", 1)
            parent = parents.get(parent_name)
            if parent is None:
                parent = TaxonomyNode(project_workspace_id=project_id, parent_id=None, name=parent_name)
                session.add(parent)
                session.flush()
                parents[parent_name] = parent
            leaf = TaxonomyNode(project_workspace_id=project_id, parent_id=parent.id, name=leaf_name)
            session.add(leaf)
            session.flush()
            leaves[path] = leaf
        for fixture_record in manifest["project_memory"]:
            record = MemoryRecord(
                id=fixture_record["record_id"],
                project_workspace_id=project_id,
                record_type=fixture_record["record_type"],
                display_name=fixture_record["name"],
                normalized_name=" ".join(fixture_record["name"].casefold().split()),
                taxonomy_node_id=leaves[fixture_record["category_path"]].id,
                status="active",
            )
            session.add(record)
            session.flush()
            model = {"material": Material, "service": Service, "provider": Provider}[record.record_type]
            session.add(model(memory_record_id=record.id))


def _scorecard_view(candidates: list[dict], expected: dict) -> dict:
    scored: list[dict] = []
    for index, candidate in enumerate(candidates):
        expected_candidate = (
            expected["candidates"][index]
            if index < len(expected["candidates"])
            else {}
        )
        payload = candidate["proposed_payload"]
        concepts = payload.get("linked_concepts", [])
        relationships = payload.get("installation_relationships", [])
        view = {
            "shape": payload.get("line_type"),
            "concept_names": [concept.get("name") for concept in concepts],
            "provider_state": payload.get("provider_state"),
            "provider_name": payload.get("provider_name"),
            "price": payload.get("price"),
            "price_state": payload.get("price_state"),
            "bundle_quantity": payload.get("bundle_quantity"),
            "bundle_unit": payload.get("bundle_unit"),
            "provider_memory_record_id": payload.get("provider_memory_record_id"),
            "project_memory_record_id": concepts[0].get("project_memory_record_id") if len(concepts) == 1 else None,
            "installation_relationship_count": sum(
                len(relationship.get("material_concept_ids", [])) for relationship in relationships
            ),
            "annotation_count": len(payload.get("annotation_proposals", [])),
            "variance_warning": bool(payload.get("variance_warning")),
            "provider_roles": [
                *(["material_supplier"] if any(concept.get("concept_type") == "material" for concept in concepts) else []),
                *(["service_provider"] if any(concept.get("concept_type") == "service" for concept in concepts) else []),
                *(["supply_and_install_provider"] if relationships else []),
            ],
        }
        scored.append({key: view.get(key) for key in expected_candidate})
    actual = {"candidates": scored}
    if "required_omissions" in expected:
        serialized = canonical_json([candidate["proposed_payload"] for candidate in candidates]).casefold()
        actual["required_omissions"] = [
            omission for omission in expected["required_omissions"] if omission.casefold() not in serialized
        ]
    return actual


def _required_eval_database_url() -> str:
    value = os.getenv("HABI_EVAL_DATABASE_URL", "")
    if not value or not any(marker in value.casefold() for marker in ("eval", "test")):
        raise RuntimeError("HABI_EVAL_DATABASE_URL must name a dedicated eval/test database")
    return value


def _require_primary_configuration() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required; it is never written to artifacts")
    required = {
        "OPENAI_FREE_FORM_MODEL": "gpt-5.5-2026-04-23",
        "OPENAI_FREE_FORM_REASONING_EFFORT": "high",
        "OPENAI_FREE_FORM_RETRIES_ENABLED": "false",
        "OPENAI_CLIENT_MAX_RETRIES": "0",
    }
    for name, expected in required.items():
        if os.getenv(name, "").casefold() != expected.casefold():
            raise RuntimeError(f"Set {name}={expected} for a qualifying promotion run")
    for name in (
        "OPENAI_EVAL_INPUT_PRICE_PER_MILLION",
        "OPENAI_EVAL_CACHED_INPUT_PRICE_PER_MILLION",
        "OPENAI_EVAL_OUTPUT_PRICE_PER_MILLION",
        "OPENAI_EVAL_PRICING_SOURCE",
    ):
        if not os.getenv(name):
            raise RuntimeError(f"Set {name} to record cost with pricing provenance")


def _latency_metrics(attempts: list[dict]) -> dict:
    values = sorted(attempt["latency_ms"] for attempt in attempts)
    return {
        "latency_p50_ms": values[4],
        "latency_p95_ms": values[9],
        "usage_totals": {
            field: sum(int(attempt["usage"].get(field, 0)) for attempt in attempts)
            for field in (
                "input_tokens",
                "cached_input_tokens",
                "output_tokens",
                "reasoning_tokens",
            )
        },
        "estimated_cost_total": sum(attempt["estimated_cost"] for attempt in attempts),
        "pricing_provenance": os.environ["OPENAI_EVAL_PRICING_SOURCE"],
    }


def _estimated_cost(usage: dict) -> float:
    input_tokens = Decimal(int(usage.get("input_tokens", 0)))
    cached_tokens = Decimal(int(usage.get("cached_input_tokens", 0)))
    uncached_tokens = max(Decimal(0), input_tokens - cached_tokens)
    output_tokens = Decimal(int(usage.get("output_tokens", 0)))
    cost = (
        uncached_tokens * Decimal(os.environ["OPENAI_EVAL_INPUT_PRICE_PER_MILLION"])
        + cached_tokens * Decimal(os.environ["OPENAI_EVAL_CACHED_INPUT_PRICE_PER_MILLION"])
        + output_tokens * Decimal(os.environ["OPENAI_EVAL_OUTPUT_PRICE_PER_MILLION"])
    ) / Decimal(1_000_000)
    return float(cost)


def _looks_like_infrastructure_error(message: str) -> bool:
    normalized = message.casefold()
    return any(
        marker in normalized
        for marker in (
            "timeout",
            "timed out",
            "rate limit",
            "connection",
            "authentication",
            "authorization",
            "api key",
            "status code: 5",
        )
    )


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


if __name__ == "__main__":
    raise SystemExit(main())
