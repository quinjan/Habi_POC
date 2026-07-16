import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.memory.models import MemoryRecord, PurchaseLine, PurchaseLineConceptLink
from backend.app.projects.models import ProjectWorkspace
from backend.app.taxonomy.models import TaxonomyNode


ENTITY_CONTEXT_LIMIT = 100
ROLE_ORDER = [
    "material_supplier",
    "service_provider",
    "supply_and_install_provider",
]


def build_project_memory_context(
    *,
    session: Session,
    project_workspace_id: int,
    source_text: str,
) -> tuple[dict, dict[str, int]]:
    project = session.get(ProjectWorkspace, project_workspace_id)
    if project is None:
        raise ValueError("Project workspace not found")

    source_tokens = _tokens(source_text)
    materials, material_omitted = _ranked_entity_context(
        session=session,
        project_workspace_id=project_workspace_id,
        record_type="material",
        source_tokens=source_tokens,
    )
    services, service_omitted = _ranked_entity_context(
        session=session,
        project_workspace_id=project_workspace_id,
        record_type="service",
        source_tokens=source_tokens,
    )
    providers, provider_omitted = _ranked_entity_context(
        session=session,
        project_workspace_id=project_workspace_id,
        record_type="provider",
        source_tokens=source_tokens,
    )
    return (
        {
            "contractor_assigned": project.contractor_assigned,
            "taxonomy_paths": _taxonomy_paths(session, project_workspace_id),
            "materials": materials,
            "services": services,
            "providers": providers,
        },
        {
            "materials": material_omitted,
            "services": service_omitted,
            "providers": provider_omitted,
        },
    )


def _ranked_entity_context(
    *,
    session: Session,
    project_workspace_id: int,
    record_type: str,
    source_tokens: set[str],
) -> tuple[list[dict], int]:
    records = list(
        session.scalars(
            select(MemoryRecord).where(
                MemoryRecord.project_workspace_id == project_workspace_id,
                MemoryRecord.record_type == record_type,
                MemoryRecord.status == "active",
            )
        )
    )
    records.sort(
        key=lambda record: (
            -len(_tokens(record.display_name).intersection(source_tokens)),
            record.normalized_name,
            record.id,
        )
    )
    selected = records[:ENTITY_CONTEXT_LIMIT]
    items = []
    for record in selected:
        item = {
            "name": record.display_name,
            "category_path": _taxonomy_path(session, record.taxonomy_node_id),
        }
        if record_type == "provider":
            item["roles"] = _provider_roles(session, record.id)
        items.append(item)
    return items, max(0, len(records) - len(selected))


def _provider_roles(session: Session, provider_memory_record_id: int) -> list[str]:
    roles: set[str] = set()
    purchase_lines = session.scalars(
        select(PurchaseLine).where(
            PurchaseLine.provider_memory_record_id == provider_memory_record_id
        )
    )
    for purchase_line in purchase_lines:
        purchase_record = session.get(MemoryRecord, purchase_line.memory_record_id)
        if purchase_record is None or purchase_record.status != "active":
            continue
        concept_types = set(
            session.scalars(
                select(PurchaseLineConceptLink.concept_type).where(
                    PurchaseLineConceptLink.purchase_line_id == purchase_line.id
                )
            )
        )
        if "material" in concept_types:
            roles.add("material_supplier")
        if "service" in concept_types:
            roles.add("service_provider")
        if concept_types == {"material", "service"}:
            roles.add("supply_and_install_provider")
    return [role for role in ROLE_ORDER if role in roles]


def _taxonomy_paths(session: Session, project_workspace_id: int) -> list[str]:
    paths = [
        _taxonomy_path(session, node.id)
        for node in session.scalars(
            select(TaxonomyNode).where(
                TaxonomyNode.project_workspace_id == project_workspace_id,
                TaxonomyNode.parent_id.is_not(None),
            )
        )
    ]
    return sorted(set(paths), key=lambda path: (path.casefold(), path))


def _taxonomy_path(session: Session, taxonomy_node_id: int) -> str:
    node = session.get(TaxonomyNode, taxonomy_node_id)
    if node is None:
        raise ValueError("Memory Record references missing taxonomy")
    if node.parent_id is None:
        return node.name
    parent = session.get(TaxonomyNode, node.parent_id)
    return f"{parent.name} / {node.name}" if parent is not None else node.name


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"\w+", value.casefold(), flags=re.UNICODE))
