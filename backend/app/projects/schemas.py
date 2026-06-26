from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectWorkspaceBase(BaseModel):
    project_name: str = Field(min_length=1, max_length=255)
    project_type: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=255)
    completion_date: date | None = None
    completion_year: int | None = Field(default=None, ge=1900, le=2100)
    floor_area: str | None = Field(default=None, max_length=100)
    trade_scopes: list[str] = Field(default_factory=list)
    client_or_owner: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_completion_date_or_year(self) -> "ProjectWorkspaceBase":
        if self.completion_date is None and self.completion_year is None:
            raise ValueError("completion_date or completion_year is required")
        return self


class ProjectWorkspaceCreate(ProjectWorkspaceBase):
    pass


class ProjectWorkspaceRead(ProjectWorkspaceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ProjectWorkspaceListItem(BaseModel):
    id: int
    project_name: str


class ProjectWorkspaceList(BaseModel):
    items: list[ProjectWorkspaceListItem]


class ProjectWorkspacePurchaseLinesView(BaseModel):
    project_workspace: ProjectWorkspaceListItem
    items: list[object]
