from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

InquiryType = Literal["one_to_one", "partnership", "bug_report"]
InstitutionType = Literal["school", "academy", "other"]
InquiryCategory = Literal[
    "product_usage",
    "account_login",
    "record_upload",
    "partnership_request",
    "bug",
    "feature_request",
    "other",
]

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class InquiryCreate(BaseModel):
    inquiry_type: InquiryType
    name: str | None = Field(default=None, max_length=120)
    email: str = Field(min_length=5, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    subject: str | None = Field(default=None, max_length=200)
    message: str = Field(min_length=10, max_length=5000)
    inquiry_category: InquiryCategory | None = None
    institution_name: str | None = Field(default=None, max_length=200)
    institution_type: InstitutionType | None = None
    source_path: str | None = Field(default=None, max_length=255)
    context_location: str | None = Field(default=None, max_length=160)
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_for_type(self) -> "InquiryCreate":
        self.email = self.email.strip().lower()
        if not EMAIL_PATTERN.match(self.email):
            raise ValueError("A valid email address is required.")

        self.name = _normalize_optional(self.name)
        self.phone = _normalize_optional(self.phone)
        self.subject = _normalize_optional(self.subject)
        self.institution_name = _normalize_optional(self.institution_name)
        self.source_path = _normalize_optional(self.source_path)
        self.context_location = _normalize_optional(self.context_location)
        self.message = self.message.strip()

        if self.inquiry_type == "one_to_one":
            if not self.name:
                raise ValueError("Name is required for one-to-one inquiries.")
            if not self.subject:
                raise ValueError("Subject is required for one-to-one inquiries.")
            if self.inquiry_category not in {"product_usage", "account_login", "record_upload", "other"}:
                raise ValueError("Select a valid inquiry category for one-to-one inquiries.")

        if self.inquiry_type == "partnership":
            if not self.institution_name:
                raise ValueError("Institution name is required for partnership inquiries.")
            if not self.name:
                raise ValueError("Contact name is required for partnership inquiries.")
            if not self.phone:
                raise ValueError("Phone number is required for partnership inquiries.")
            if self.institution_type not in {"school", "academy", "other"}:
                raise ValueError("Select a valid institution type for partnership inquiries.")
            if self.inquiry_category not in {None, "partnership_request"}:
                raise ValueError("Partnership inquiries use the partnership request category.")
            self.inquiry_category = "partnership_request"

        if self.inquiry_type == "bug_report":
            if not self.name:
                raise ValueError("Name or nickname is required for bug reports.")
            if self.inquiry_category not in {"bug", "feature_request"}:
                raise ValueError("Select bug or feature request.")
            if not self.context_location:
                raise ValueError("Context location is required for bug reports.")

        return self


class InquiryCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    inquiry_type: InquiryType
    status: str
    delivery_status: str | None = None
    delivery_reason: str | None = None
    delivery_async_job_id: str | None = None
    delivery_retry_needed: bool | None = None
    created_at: datetime
    message: str


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
