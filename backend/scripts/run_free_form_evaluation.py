"""Run Habi's explicit one-call free-form POC evaluation.

The command is intentionally outside pytest and ordinary CI. It requires a named
human approval before it makes the paid model call and prints a short Markdown
scorecard for the pull request.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from backend.app.database import Base, create_sqlalchemy_engine
from backend.app.evaluation.free_form import (
    canonical_json,
    compare_domain_output,
    load_fixture_manifest,
    render_markdown_scorecard,
)
from backend.app.main import create_app
from backend.app.memory.models import Material, MemoryRecord, Provider, Service
from backend.app.processing.__main__ import create_openai_provider_from_env
from backend.app.processing.worker import run_once
from backend.app.taxonomy.models import TaxonomyNode

FIXTURES = ROOT / "backend" / "evals" / "free-form" / "fixtures"


class EvaluationRunError(RuntimeError):
    def __init__(self, message: str, *, calls: int):
        super().__init__(message)
        self.calls = calls


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


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    manifest = load_fixture_manifest(FIXTURES, require_approved=True)
    database_url = _required_eval_database_url()
    _load_openai_key_from_repo_env()
    _require_one_call_configuration()

    actual = {"candidates": [], "required_omissions": []}
    differences: list[dict] = []
    model_call_count = 0
    try:
        actual, model_call_count = _run_fixture(database_url, manifest)
        differences = compare_domain_output(manifest["expected_result"], actual)
    except EvaluationRunError as error:
        model_call_count = error.calls
        differences = [{"path": "$", "message": str(error)}]
    except Exception as error:
        differences = [
            {
                "path": "$",
                "message": f"Evaluation could not complete ({type(error).__name__})",
            }
        ]

    print(
        render_markdown_scorecard(
            prd_issue=args.prd_issue,
            manifest=manifest,
            model=os.environ["OPENAI_FREE_FORM_MODEL"],
            actual=actual,
            differences=differences,
            model_call_count=model_call_count,
            paid_call_approved_by=args.approved_by,
        )
    )
    if differences:
        print("\n### Evaluation differences")
        for difference in differences:
            print(f"- `{json.dumps(difference, ensure_ascii=False, sort_keys=True)}`")
    return 0 if not differences and model_call_count == 1 else 1


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--approved-by",
        required=True,
        help="Human who explicitly approved this paid model call",
    )
    parser.add_argument(
        "--prd-issue",
        type=int,
        default=36,
        help="PRD issue recorded in the Markdown scorecard (default: 36)",
    )
    args = parser.parse_args(argv)
    if not args.approved_by.strip():
        parser.error("--approved-by must name the approving human")
    args.approved_by = args.approved_by.strip()
    return args


def _run_fixture(database_url: str, manifest: dict) -> tuple[dict, int]:
    engine = create_sqlalchemy_engine(database_url)
    try:
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
                json={
                    "entry_type": "free_form_text",
                    "original_text": manifest["source_text"],
                },
            ).json()
            provider = CountingProvider(create_openai_provider_from_env())
            run_once(app.state.session_factory, ai_provider=provider)
            job = client.get(
                f"/api/project-workspaces/{project['id']}/processing-jobs/"
                f"{submission['processing_job']['id']}"
            ).json()["processing_job"]
            if job["status"] != "review_ready":
                raise EvaluationRunError(
                    f"Production worker ended as {job['status']}",
                    calls=provider.calls,
                )
            review = client.get(
                f"/api/project-workspaces/{project['id']}/review-batches/"
                f"{job['review_batch_id']}"
            ).json()
            return _scorecard_view(review["candidates"], manifest["expected_result"]), provider.calls
    finally:
        engine.dispose()


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
                parent = TaxonomyNode(
                    project_workspace_id=project_id,
                    parent_id=None,
                    name=parent_name,
                )
                session.add(parent)
                session.flush()
                parents[parent_name] = parent
            leaf = TaxonomyNode(
                project_workspace_id=project_id,
                parent_id=parent.id,
                name=leaf_name,
            )
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
            model = {
                "material": Material,
                "service": Service,
                "provider": Provider,
            }[record.record_type]
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
        view = {
            "shape": payload.get("line_type"),
            "concept_names": [concept.get("name") for concept in concepts],
            "provider_state": payload.get("provider_state"),
            "provider_name": payload.get("provider_name"),
            "price": payload.get("price"),
            "annotation_count": len(payload.get("annotation_proposals", [])),
        }
        scored.append({key: view.get(key) for key in expected_candidate})
    actual = {"candidates": scored}
    if "required_omissions" in expected:
        serialized = canonical_json(
            [candidate["proposed_payload"] for candidate in candidates]
        ).casefold()
        actual["required_omissions"] = [
            omission
            for omission in expected["required_omissions"]
            if omission.casefold() not in serialized
        ]
    return actual


def _required_eval_database_url() -> str:
    value = os.getenv("HABI_EVAL_DATABASE_URL", "")
    if not value:
        raise RuntimeError("HABI_EVAL_DATABASE_URL is required")
    parsed = make_url(value)
    if parsed.get_backend_name() != "postgresql":
        raise RuntimeError("HABI_EVAL_DATABASE_URL must use Postgres")
    database_name = parsed.database or ""
    if not database_name.casefold().startswith("habi_eval_"):
        raise RuntimeError("HABI_EVAL_DATABASE_URL database name must start with habi_eval_")
    return value


def _load_openai_key_from_repo_env() -> None:
    if os.getenv("OPENAI_API_KEY"):
        return
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() == "OPENAI_API_KEY":
            os.environ["OPENAI_API_KEY"] = value.strip().strip('"').strip("'")
            return


def _require_one_call_configuration() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required and is never printed")
    required = {
        "OPENAI_FREE_FORM_MODEL": "gpt-5.4-2026-03-05",
        "OPENAI_FREE_FORM_REASONING_EFFORT": "medium",
        "OPENAI_FREE_FORM_RETRIES_ENABLED": "false",
        "OPENAI_CLIENT_MAX_RETRIES": "0",
    }
    for name, expected in required.items():
        if os.getenv(name, "").casefold() != expected.casefold():
            raise RuntimeError(f"Set {name}={expected} for the one-call POC evaluation")


if __name__ == "__main__":
    raise SystemExit(main())
