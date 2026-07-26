from __future__ import annotations

import json
import shutil
from pathlib import Path


FIXTURE_FILENAME = "habi_issue_53_varied_completed_project.xlsx"
CONTEXT_FILENAME = "project_context.json"
CHECKED_IN_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "outputs"
    / "issue-53-intelligent-xlsx-prototype"
    / FIXTURE_FILENAME
)

EXPECTED_CANDIDATES = (
    {
        "shape": "bundle",
        "concept_names": {
            "Daikin split-type air conditioner",
            "Air conditioning installation",
        },
        "provider_state": "external",
        "provider_name": "CoolAir Mechanical Services",
        "total_price": "120000",
    },
    {
        "shape": "material",
        "concept_names": {"100 mm PVC pressure pipe"},
        "provider_state": "external",
        "provider_name": "BuildMart Trading",
        "total_price": "32500",
    },
    {
        "shape": "material",
        "concept_names": {"16 mm Grade 60 deformed reinforcing bar"},
        "provider_state": "external",
        "provider_name": "MetroSteel",
        "total_price": "28800",
    },
    {
        "shape": "service",
        "concept_names": {"Site cleanup"},
        "provider_state": "internal",
        "provider_name": None,
        "total_price": "18000",
    },
    {
        "shape": "material",
        "concept_names": {"Non-shrink grout"},
        "provider_state": "unknown",
        "provider_name": None,
        "total_price": "8500",
    },
    {
        "shape": "service",
        "concept_names": {"Domestic water lines pressure testing"},
        "provider_state": "internal",
        "provider_name": None,
        "total_price": "9000",
    },
)

REQUIRED_OMISSIONS = (
    "Ceiling installation",
    "preliminary quote",
    "For approval",
    "Follow up with Mario",
    "TBD",
)


def create_fixture(output_dir: Path) -> tuple[Path, Path]:
    if not CHECKED_IN_FIXTURE.is_file():
        raise RuntimeError(f"Prototype fixture is missing: {CHECKED_IN_FIXTURE}")
    output_dir.mkdir(parents=True, exist_ok=True)
    workbook_path = output_dir / FIXTURE_FILENAME
    context_path = output_dir / CONTEXT_FILENAME
    if workbook_path.resolve() != CHECKED_IN_FIXTURE.resolve():
        shutil.copyfile(CHECKED_IN_FIXTURE, workbook_path)
    context_path.write_text(
        json.dumps(_project_context(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return workbook_path, context_path


def _project_context() -> dict:
    return {
        "project_workspace": {
            "project_name": "Arnaiz Residence",
            "contractor_assigned": "Arnaiz Builders",
            "currency_default": "PHP",
        },
        "project_memory": [
            {
                "record_id": 101,
                "record_type": "material",
                "name": "Daikin split-type air conditioner",
                "category_path": [
                    "Electrical",
                    "Air Conditioning Equipment",
                ],
            },
            {
                "record_id": 102,
                "record_type": "provider",
                "name": "CoolAir Mechanical Services",
                "category_path": ["Providers", "HVAC Contractors"],
            },
        ],
        "taxonomy_vocabulary": [
            ["Electrical", "Air Conditioning Equipment"],
            ["Services", "Air Conditioning Installation"],
            ["Providers", "HVAC Contractors"],
            ["Plumbing", "Pipes"],
            ["Providers", "Construction Material Suppliers"],
            ["Services", "Site Cleanup"],
            ["Civil", "Grouting Materials"],
            ["Civil", "Reinforcing Steel"],
            ["Services", "Testing and Commissioning"],
        ],
        "prototype_rules": {
            "source_file_is_final_as_used_by_default": True,
            "candidate_local_non_final_wording_overrides_default": True,
            "bid_and_proposal_workbooks_are_ineligible": True,
            "every_candidate_requires_source_evidence": True,
            "reviewer_approval_is_required_before_import": True,
        },
    }
