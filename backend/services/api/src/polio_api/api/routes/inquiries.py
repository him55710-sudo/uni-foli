from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from polio_api.api.deps import get_db
from polio_api.core.rate_limit import rate_limit
from polio_api.schemas.inquiry import InquiryCreate, InquiryCreateResponse
from polio_api.services.inquiry_service import create_inquiry

router = APIRouter()


@router.post(
    "",
    response_model=InquiryCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(bucket="public_inquiries", limit=12, window_seconds=3600, guest_limit=6))],
)
def create_inquiry_route(
    payload: InquiryCreate,
    db: Session = Depends(get_db),
) -> InquiryCreateResponse:
    inquiry = create_inquiry(db, payload)
    delivery = inquiry.extra_fields.get("delivery", {}) if isinstance(inquiry.extra_fields, dict) else {}
    return InquiryCreateResponse(
        id=inquiry.id,
        inquiry_type=inquiry.inquiry_type,
        status=inquiry.status,
        delivery_status=delivery.get("status") if isinstance(delivery, dict) else None,
        delivery_reason=delivery.get("reason") if isinstance(delivery, dict) else None,
        delivery_async_job_id=delivery.get("async_job_id") if isinstance(delivery, dict) else None,
        delivery_retry_needed=delivery.get("retry_needed") if isinstance(delivery, dict) else None,
        created_at=inquiry.created_at,
        message="Inquiry received. We will review it and respond through the provided contact details.",
    )
