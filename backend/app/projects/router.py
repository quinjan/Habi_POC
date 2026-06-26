from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import get_session
from backend.app.memory.models import PurchaseLine
from backend.app.projects.models import ProjectWorkspace
from backend.app.projects.schemas import (
    ProjectWorkspaceCreate,
    ProjectWorkspaceList,
    ProjectWorkspaceListItem,
    PurchaseLineRow,
    ProjectWorkspacePurchaseLinesView,
    ProjectWorkspaceRead,
)


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
        .where(PurchaseLine.project_workspace_id == project_workspace.id)
        .order_by(PurchaseLine.id)
    ).all()

    return ProjectWorkspacePurchaseLinesView(
        project_workspace=ProjectWorkspaceListItem(
            id=project_workspace.id,
            project_name=project_workspace.project_name,
        ),
        items=[
            PurchaseLineRow(
                id=purchase_line.id,
                item_or_service_name=purchase_line.item_or_service_name,
                line_type=purchase_line.line_type,
                provider_name=purchase_line.provider_name,
                provider_type=purchase_line.provider_type,
                provider_role=purchase_line.provider_role,
                quantity=purchase_line.quantity,
                unit=purchase_line.unit,
                unit_state=purchase_line.unit_state,
                price=purchase_line.price,
                currency=purchase_line.currency,
                price_state=purchase_line.price_state,
                purchase_date=purchase_line.purchase_date,
                date_state=purchase_line.date_state,
                category_path=purchase_line.category_path,
                has_evidence=True,
                source_label="Manual Source Entry",
            )
            for purchase_line in purchase_lines
        ],
    )
