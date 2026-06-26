from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import get_session
from backend.app.projects.models import ProjectWorkspace
from backend.app.projects.schemas import (
    ProjectWorkspaceCreate,
    ProjectWorkspaceList,
    ProjectWorkspaceListItem,
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

    return ProjectWorkspacePurchaseLinesView(
        project_workspace=ProjectWorkspaceListItem(
            id=project_workspace.id,
            project_name=project_workspace.project_name,
        ),
        items=[],
    )
