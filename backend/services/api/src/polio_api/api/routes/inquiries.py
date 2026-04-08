from fastapi import APIRouter, Depends, status, BackgroundTasks
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> InquiryCreateResponse:
    inquiry = create_inquiry(db, payload, background_tasks)
    return InquiryCreateResponse(
        id=inquiry.id,
        inquiry_type=inquiry.inquiry_type,
        status=inquiry.status,
        created_at=inquiry.created_at,
        message="Inquiry received. We will review it and respond through the provided contact details.",
    )
