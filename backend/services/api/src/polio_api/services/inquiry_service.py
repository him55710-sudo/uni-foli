from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from polio_api.db.models.inquiry import Inquiry
from polio_api.schemas.inquiry import InquiryCreate


def create_inquiry(db: Session, payload: InquiryCreate) -> Inquiry:
    inquiry = Inquiry(
        inquiry_type=payload.inquiry_type,
        status="received",
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        subject=payload.subject,
        message=payload.message,
        inquiry_category=payload.inquiry_category,
        institution_name=payload.institution_name,
        institution_type=payload.institution_type,
        source_path=payload.source_path,
        extra_fields=_build_extra_fields(payload),
    )
    db.add(inquiry)
    db.commit()
    db.refresh(inquiry)
    return inquiry


def _build_extra_fields(payload: InquiryCreate) -> dict[str, Any]:
    extra_fields: dict[str, Any] = {}
    if payload.metadata:
        extra_fields["metadata"] = payload.metadata
    if payload.context_location:
        extra_fields["context_location"] = payload.context_location
    return extra_fields
