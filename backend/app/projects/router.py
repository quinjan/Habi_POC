from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import get_session
from backend.app.evidence.inspection import (
    build_purchase_line_evidence_read,
    source_submitted_at,
)
from backend.app.evidence.models import EvidenceRecord, MemoryRecordEvidenceLink
from backend.app.memory.models import MemoryRecord, PurchaseLine, PurchaseLineConceptLink
from backend.app.projects.models import ProjectWorkspace
from backend.app.projects.schemas import (
    ProjectWorkspaceCreate,
    EntityMemoryListView,
    EntityMemoryRow,
    ProjectWorkspaceList,
    ProjectWorkspaceListItem,
    PurchaseLineConceptRead,
    PurchaseLineRow,
    ProviderMemoryListView,
    ProviderMemoryRow,
    ProjectWorkspacePurchaseLinesView,
    ProjectWorkspaceRead,
    PurchaseLineDetail,
    PurchaseLineProviderRead,
    PurchaseLineProviderRecordRead,
)
from backend.app.sources.models import ManualSourceEntry, SourceFile
from backend.app.taxonomy.models import TaxonomyNode


router = APIRouter(tags=["project-workspaces"])


@router.get("", response_model=ProjectWorkspaceList)
def list_project_workspaces(session: Session = Depends(get_session)) -> ProjectWorkspaceList:
    project_workspaces = session.scalars(
        select(ProjectWorkspace).order_by(ProjectWorkspace.id)
    ).all()
    return ProjectWorkspaceList(
        items=[
            ProjectWorkspaceListItem(id=workspace.id, project_name=workspace.project_name)
            for workspace in project_workspaces
        ]
    )


@router.post("", response_model=ProjectWorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_project_workspace(
    payload: ProjectWorkspaceCreate,
    session: Session = Depends(get_session),
) -> ProjectWorkspace:
    project_workspace = ProjectWorkspace(**payload.model_dump())
    session.add(project_workspace)
    session.commit()
    session.refresh(project_workspace)
    return project_workspace


@router.get("/{project_workspace_id}/purchase-lines", response_model=ProjectWorkspacePurchaseLinesView)
def get_project_workspace_purchase_lines(
    project_workspace_id: int,
    session: Session = Depends(get_session),
) -> ProjectWorkspacePurchaseLinesView:
    project_workspace = session.get(ProjectWorkspace, project_workspace_id)
    if project_workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project workspace not found")

    purchase_lines = session.scalars(
        select(PurchaseLine)
        .join(MemoryRecord, MemoryRecord.id == PurchaseLine.memory_record_id)
        .where(PurchaseLine.project_workspace_id == project_workspace.id)
        .where(MemoryRecord.status == "active")
        .order_by(PurchaseLine.id)
    ).all()

    return ProjectWorkspacePurchaseLinesView(
        project_workspace=ProjectWorkspaceListItem(
            id=project_workspace.id,
            project_name=project_workspace.project_name,
        ),
        items=[_purchase_line_row(session, purchase_line) for purchase_line in purchase_lines],
    )


@router.get(
    "/{project_workspace_id}/purchase-lines/{purchase_line_id}",
    response_model=PurchaseLineDetail,
)
def get_purchase_line_detail(
    project_workspace_id: int,
    purchase_line_id: int,
    session: Session = Depends(get_session),
) -> PurchaseLineDetail:
    _project_or_404(session, project_workspace_id)
    purchase_line = session.scalar(
        select(PurchaseLine).where(
            PurchaseLine.id == purchase_line_id,
            PurchaseLine.project_workspace_id == project_workspace_id,
        )
    )
    if purchase_line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase Line not found",
        )
    purchase_record = session.get(MemoryRecord, purchase_line.memory_record_id)
    if purchase_record is None or purchase_record.project_workspace_id != project_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase Line not found",
        )

    links = list(
        session.scalars(
            select(PurchaseLineConceptLink)
            .where(PurchaseLineConceptLink.purchase_line_id == purchase_line.id)
            .order_by(PurchaseLineConceptLink.id)
        )
    )
    linked_concepts = [
        _concept_read(session, link)
        for link in sorted(links, key=lambda item: 0 if item.concept_type == "material" else 1)
    ]
    provider_record = (
        session.get(MemoryRecord, purchase_line.provider_memory_record_id)
        if purchase_line.provider_memory_record_id is not None
        else None
    )
    evidence_records = list(
        session.scalars(
            select(EvidenceRecord)
            .join(
                MemoryRecordEvidenceLink,
                MemoryRecordEvidenceLink.evidence_record_id == EvidenceRecord.id,
            )
            .where(MemoryRecordEvidenceLink.memory_record_id == purchase_record.id)
            .order_by(EvidenceRecord.id)
        )
    )
    evidence_views = [
        build_purchase_line_evidence_read(
            session,
            project_workspace_id=project_workspace_id,
            evidence=evidence,
        )
        for evidence in evidence_records
    ]
    evidence_views.sort(key=lambda item: (source_submitted_at(session, item.source_submission_id), item.id))
    return PurchaseLineDetail(
        id=purchase_line.id,
        status=purchase_record.status,
        line_type="bundled" if len(linked_concepts) == 2 else linked_concepts[0].concept_type,
        linked_concepts=linked_concepts,
        provider=PurchaseLineProviderRead(
            state=purchase_line.provider_state,
            record=(
                PurchaseLineProviderRecordRead(
                    memory_record_id=provider_record.id,
                    name=provider_record.display_name,
                    category_path=_taxonomy_path(session, provider_record.taxonomy_node_id),
                )
                if provider_record is not None
                else None
            ),
            roles=_provider_roles(purchase_line.provider_state, linked_concepts),
        ),
        quantity=purchase_line.quantity,
        unit=purchase_line.unit,
        unit_state=purchase_line.unit_state,
        price=purchase_line.price,
        currency=purchase_line.currency,
        price_state=purchase_line.price_state,
        purchase_date=purchase_line.purchase_date,
        date_state=purchase_line.date_state,
        evidence_records=evidence_views,
        value_history_available=False,
    )


def _purchase_line_row(session: Session, purchase_line: PurchaseLine) -> PurchaseLineRow:
    evidence_records = _purchase_line_evidence_records(session, purchase_line)
    source_label = evidence_records[0].source_label if evidence_records else None
    links = list(
        session.scalars(
            select(PurchaseLineConceptLink)
            .where(PurchaseLineConceptLink.purchase_line_id == purchase_line.id)
            .order_by(PurchaseLineConceptLink.id)
        )
    )
    linked_concepts = [
        _concept_read(session, link)
        for link in sorted(links, key=lambda link: 0 if link.concept_type == "material" else 1)
    ]
    provider_record = (
        session.get(MemoryRecord, purchase_line.provider_memory_record_id)
        if purchase_line.provider_memory_record_id is not None
        else None
    )
    return PurchaseLineRow(
        id=purchase_line.id,
        line_type="bundled" if len(linked_concepts) == 2 else linked_concepts[0].concept_type,
        linked_concepts=linked_concepts,
        provider_state=purchase_line.provider_state,
        provider_name=(
            provider_record.display_name
            if provider_record is not None
            else "Internal" if purchase_line.provider_state == "internal" else None
        ),
        provider_category_path=(
            _taxonomy_path(session, provider_record.taxonomy_node_id)
            if provider_record is not None
            else None
        ),
        provider_roles=_provider_roles(purchase_line.provider_state, linked_concepts),
        quantity=purchase_line.quantity,
        unit=purchase_line.unit,
        unit_state=purchase_line.unit_state,
        price=purchase_line.price,
        currency=purchase_line.currency,
        price_state=purchase_line.price_state,
        purchase_date=purchase_line.purchase_date,
        date_state=purchase_line.date_state,
        has_evidence=source_label is not None,
        evidence_count=len(evidence_records),
        source_label=source_label or "No evidence",
    )


@router.get("/{project_workspace_id}/materials", response_model=EntityMemoryListView)
def get_project_workspace_materials(
    project_workspace_id: int,
    session: Session = Depends(get_session),
) -> EntityMemoryListView:
    return _entity_memory_list(session, project_workspace_id, "material")


@router.get("/{project_workspace_id}/services", response_model=EntityMemoryListView)
def get_project_workspace_services(
    project_workspace_id: int,
    session: Session = Depends(get_session),
) -> EntityMemoryListView:
    return _entity_memory_list(session, project_workspace_id, "service")


@router.get("/{project_workspace_id}/providers", response_model=ProviderMemoryListView)
def get_project_workspace_providers(
    project_workspace_id: int,
    roles: list[str] = Query(default=[]),
    session: Session = Depends(get_session),
) -> ProviderMemoryListView:
    project = _project_or_404(session, project_workspace_id)
    requested_roles = set(roles)
    rows: list[ProviderMemoryRow] = []
    for record in _active_memory_records(session, project_workspace_id, "provider"):
        purchase_lines = _provider_purchase_lines(session, record.id)
        observed_roles = _aggregate_provider_roles(session, purchase_lines)
        if requested_roles and requested_roles.isdisjoint(observed_roles):
            continue
        rows.append(
            ProviderMemoryRow(
                **_entity_row_values(session, record, purchase_lines),
                roles=observed_roles,
            )
        )
    return ProviderMemoryListView(
        project_workspace=_project_list_item(project),
        items=rows,
    )


def _entity_memory_list(
    session: Session,
    project_workspace_id: int,
    record_type: str,
) -> EntityMemoryListView:
    project = _project_or_404(session, project_workspace_id)
    rows = []
    for record in _active_memory_records(session, project_workspace_id, record_type):
        purchase_lines = _concept_purchase_lines(session, record.id)
        rows.append(EntityMemoryRow(**_entity_row_values(session, record, purchase_lines)))
    return EntityMemoryListView(
        project_workspace=_project_list_item(project),
        items=rows,
    )


def _entity_row_values(
    session: Session,
    record: MemoryRecord,
    purchase_lines: list[PurchaseLine],
) -> dict:
    return {
        "memory_record_id": record.id,
        "name": record.display_name,
        "category_path": _taxonomy_path(session, record.taxonomy_node_id),
        "linked_purchase_line_count": len({line.id for line in purchase_lines}),
        "source_submission_count": _source_submission_count(session, record.id),
    }


def _project_or_404(session: Session, project_workspace_id: int) -> ProjectWorkspace:
    project = session.get(ProjectWorkspace, project_workspace_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project workspace not found")
    return project


def _project_list_item(project: ProjectWorkspace) -> ProjectWorkspaceListItem:
    return ProjectWorkspaceListItem(id=project.id, project_name=project.project_name)


def _active_memory_records(
    session: Session,
    project_workspace_id: int,
    record_type: str,
) -> list[MemoryRecord]:
    return list(
        session.scalars(
            select(MemoryRecord)
            .where(
                MemoryRecord.project_workspace_id == project_workspace_id,
                MemoryRecord.record_type == record_type,
                MemoryRecord.status == "active",
            )
            .order_by(MemoryRecord.normalized_name, MemoryRecord.id)
        )
    )


def _concept_purchase_lines(session: Session, memory_record_id: int) -> list[PurchaseLine]:
    line_ids = session.scalars(
        select(PurchaseLineConceptLink.purchase_line_id).where(
            PurchaseLineConceptLink.concept_memory_record_id == memory_record_id
        )
    )
    return _active_purchase_lines(session, line_ids)


def _provider_purchase_lines(session: Session, memory_record_id: int) -> list[PurchaseLine]:
    lines = session.scalars(
        select(PurchaseLine).where(PurchaseLine.provider_memory_record_id == memory_record_id)
    )
    return [line for line in lines if _purchase_line_is_active(session, line)]


def _active_purchase_lines(session: Session, line_ids) -> list[PurchaseLine]:
    lines = [session.get(PurchaseLine, line_id) for line_id in set(line_ids)]
    return [
        line
        for line in lines
        if line is not None and _purchase_line_is_active(session, line)
    ]


def _purchase_line_is_active(session: Session, line: PurchaseLine) -> bool:
    record = session.get(MemoryRecord, line.memory_record_id)
    return record is not None and record.status == "active"


def _aggregate_provider_roles(
    session: Session,
    purchase_lines: list[PurchaseLine],
) -> list[str]:
    role_order = [
        "material_supplier",
        "service_provider",
        "supply_and_install_provider",
    ]
    roles: set[str] = set()
    for line in purchase_lines:
        links = session.scalars(
            select(PurchaseLineConceptLink).where(
                PurchaseLineConceptLink.purchase_line_id == line.id
            )
        )
        concept_types = {link.concept_type for link in links}
        if "material" in concept_types:
            roles.add("material_supplier")
        if "service" in concept_types:
            roles.add("service_provider")
        if concept_types == {"material", "service"}:
            roles.add("supply_and_install_provider")
    return [role for role in role_order if role in roles]


def _source_submission_count(session: Session, memory_record_id: int) -> int:
    evidence_records = session.scalars(
        select(EvidenceRecord)
        .join(
            MemoryRecordEvidenceLink,
            MemoryRecordEvidenceLink.evidence_record_id == EvidenceRecord.id,
        )
        .where(MemoryRecordEvidenceLink.memory_record_id == memory_record_id)
    )
    source_submission_ids: set[int] = set()
    for evidence in evidence_records:
        if evidence.manual_source_entry_id is not None:
            manual_entry = session.get(ManualSourceEntry, evidence.manual_source_entry_id)
            if manual_entry is not None:
                source_submission_ids.add(manual_entry.source_submission_id)
        elif evidence.source_file_id is not None:
            source_file = session.get(SourceFile, evidence.source_file_id)
            if source_file is not None:
                source_submission_ids.add(source_file.source_submission_id)
    return len(source_submission_ids)


def _concept_read(
    session: Session,
    link: PurchaseLineConceptLink,
) -> PurchaseLineConceptRead:
    memory_record = session.get(MemoryRecord, link.concept_memory_record_id)
    if memory_record is None:
        raise RuntimeError("Purchase Line Concept Link references missing memory")
    return PurchaseLineConceptRead(
        memory_record_id=memory_record.id,
        concept_type=link.concept_type,
        name=memory_record.display_name,
        category_path=_taxonomy_path(session, memory_record.taxonomy_node_id),
    )


def _provider_roles(
    provider_state: str,
    linked_concepts: list[PurchaseLineConceptRead],
) -> list[str]:
    if provider_state == "unknown":
        return []
    concept_types = {concept.concept_type for concept in linked_concepts}
    roles: list[str] = []
    if "material" in concept_types:
        roles.append("material_supplier")
    if "service" in concept_types:
        roles.append("service_provider")
    if concept_types == {"material", "service"}:
        roles.append("supply_and_install_provider")
    return roles


def _taxonomy_path(session: Session, taxonomy_node_id: int) -> str:
    node = session.get(TaxonomyNode, taxonomy_node_id)
    if node is None:
        raise RuntimeError("Memory Record references missing taxonomy")
    if node.parent_id is None:
        return node.name
    parent = session.get(TaxonomyNode, node.parent_id)
    return f"{parent.name} / {node.name}" if parent is not None else node.name


def _source_label(session: Session, purchase_line: PurchaseLine) -> str | None:
    records = _purchase_line_evidence_records(session, purchase_line)
    return records[0].source_label if records else None


def _purchase_line_evidence_records(
    session: Session,
    purchase_line: PurchaseLine,
) -> list[EvidenceRecord]:
    return list(
        session.scalars(
            select(EvidenceRecord)
        .join(
            MemoryRecordEvidenceLink,
            MemoryRecordEvidenceLink.evidence_record_id == EvidenceRecord.id,
        )
        .where(MemoryRecordEvidenceLink.memory_record_id == purchase_line.memory_record_id)
        .order_by(EvidenceRecord.id)
        )
    )
