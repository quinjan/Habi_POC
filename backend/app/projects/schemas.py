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
    contractor_assigned: str = Field(min_length=1, max_length=255)
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


class PurchaseLineConceptRead(BaseModel):
    memory_record_id: int
    concept_type: str
    name: str
    category_path: str
    concept_key: str | None = None
    quantity: str | None = None
    unit: str | None = None
    component_unit_price: str | None = None


class InstallationRelationshipRead(BaseModel):
    service_concept_key: str
    material_concept_key: str
    source_excerpt: str
    source_locator: dict


class PurchaseLineRow(BaseModel):
    id: int
    line_type: str
    linked_concepts: list[PurchaseLineConceptRead]
    installation_relationships: list[InstallationRelationshipRead] = Field(default_factory=list)
    provider_state: str
    provider_name: str | None
    provider_category_path: str | None
    provider_roles: list[str]
    quantity: str | None
    unit: str | None
    unit_state: str
    price: str | None
    currency: str | None
    price_state: str
    purchase_date: date | None
    date_state: str
    has_evidence: bool
    evidence_count: int
    source_label: str


class ProjectWorkspacePurchaseLinesView(BaseModel):
    project_workspace: ProjectWorkspaceListItem
    items: list[PurchaseLineRow]


class PurchaseLineProviderRecordRead(BaseModel):
    memory_record_id: int
    name: str
    category_path: str


class PurchaseLineProviderRead(BaseModel):
    state: str
    record: PurchaseLineProviderRecordRead | None
    roles: list[str]


class EvidenceAnnotationTargetRead(BaseModel):
    memory_record_id: int
    record_type: str
    name: str


class EvidenceAnnotationRead(BaseModel):
    id: int
    proposal_id: str
    text: str
    annotation_type: str
    target: EvidenceAnnotationTargetRead
    source_excerpt: str
    source_locator: dict | None
    provenance: str


class PurchaseLineEvidenceRead(BaseModel):
    id: int
    source_submission_id: int
    source_label: str
    source_type: str
    source_submission_href: str
    locator: dict | None
    supporting_content: dict
    annotations: list[EvidenceAnnotationRead]
    annotation_omitted_count: int = 0
    annotation_detected_count: int = 0


class PurchaseLineDetail(BaseModel):
    id: int
    status: str
    line_type: str
    linked_concepts: list[PurchaseLineConceptRead]
    installation_relationships: list[InstallationRelationshipRead] = Field(default_factory=list)
    provider: PurchaseLineProviderRead
    quantity: str | None
    unit: str | None
    unit_state: str
    price: str | None
    currency: str | None
    price_state: str
    purchase_date: date | None
    date_state: str
    evidence_records: list[PurchaseLineEvidenceRead]
    value_history_available: bool = False


class EntityMemoryRow(BaseModel):
    memory_record_id: int
    name: str
    category_path: str
    linked_purchase_line_count: int
    source_submission_count: int


class ProviderMemoryRow(EntityMemoryRow):
    roles: list[str]


class EntityMemoryListView(BaseModel):
    project_workspace: ProjectWorkspaceListItem
    items: list[EntityMemoryRow]


class ProviderMemoryListView(BaseModel):
    project_workspace: ProjectWorkspaceListItem
    items: list[ProviderMemoryRow]
