from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


LineType = Literal["material", "service"]


class ManualSourceEntryCreate(BaseModel):
    line_type: LineType
    name: str = Field(min_length=1, max_length=255)
    quantity: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=100)
    price: str | None = Field(default=None, max_length=100)
    currency: str | None = Field(default=None, max_length=10)
    provider_name: str | None = Field(default=None, max_length=255)
    purchase_date: date | None = None
    remarks_or_terms: str | None = Field(default=None, max_length=2000)


class ManualSourceEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_workspace_id: int
    structured_payload: dict
