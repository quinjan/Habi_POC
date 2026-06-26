from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


LineType = Literal["material", "service"]
ManualSourceEntryType = Literal["structured_row", "free_form_text"]


class StructuredManualSourcePayload(BaseModel):
    line_type: LineType
    name: str = Field(min_length=1, max_length=255)
    quantity: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=100)
    price: str | None = Field(default=None, max_length=100)
    currency: str | None = Field(default=None, max_length=10)
    provider_name: str | None = Field(default=None, max_length=255)
    purchase_date: date | None = None
    remarks_or_terms: str | None = Field(default=None, max_length=2000)


class ManualSourceEntryCreate(BaseModel):
    entry_type: ManualSourceEntryType
    structured_payload: StructuredManualSourcePayload | None = None
    original_text: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def validate_entry_content(self) -> "ManualSourceEntryCreate":
        if self.entry_type == "structured_row" and self.structured_payload is None:
            raise ValueError("Structured manual source entries require structured_payload")
        if self.entry_type == "free_form_text":
            if self.original_text is None or self.original_text.strip() == "":
                raise ValueError("Free-form manual source entries require non-empty original_text")
        return self


class SourceSubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_workspace_id: int
    submission_type: str
    submitted_at: datetime
    entered_by: dict | None


class ManualSourceEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_workspace_id: int
    source_submission_id: int
    entry_type: str
    structured_payload: dict | None
    original_text: str | None
