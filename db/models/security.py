from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from db.types import JSONBType
from domain.enums import AccountStatus, DeletionMode, DeletionRequestStatus, LifecycleStatus, PrivacyMaskingMode, PrivacyScanStatus


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (UniqueConstraint("slug", name="uq_tenants_slug"),)

    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[LifecycleStatus] = mapped_column(
        Enum(LifecycleStatus, native_enum=False),
        nullable=False,
        default=LifecycleStatus.ACTIVE,
    )
    default_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    masking_mode: Mapped[PrivacyMaskingMode] = mapped_column(
        Enum(PrivacyMaskingMode, native_enum=False),
        nullable=False,
        default=PrivacyMaskingMode.MASK_FOR_INDEX,
    )
    pii_detection_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    accounts: Mapped[list["Account"]] = relationship(back_populates="tenant")
    auth_sessions: Mapped[list["AuthSession"]] = relationship(back_populates="tenant")
    student_files: Mapped[list["StudentFile"]] = relationship(back_populates="tenant")
    analysis_runs: Mapped[list["StudentAnalysisRun"]] = relationship(back_populates="tenant")
    review_tasks: Mapped[list["ReviewTask"]] = relationship(back_populates="tenant")
    response_traces: Mapped[list["ResponseTrace"]] = relationship(back_populates="tenant")
    citations: Mapped[list["Citation"]] = relationship(back_populates="tenant")
    policy_flags: Mapped[list["PolicyFlag"]] = relationship(back_populates="tenant")
    privacy_scans: Mapped[list["PrivacyScan"]] = relationship(back_populates="tenant")
    deletion_requests: Mapped[list["DeletionRequest"]] = relationship(back_populates="tenant")


class Role(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("slug", name="uq_roles_slug"),)

    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    global_access: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    permissions_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    accounts: Mapped[list["Account"]] = relationship(back_populates="role")


class Account(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("email", name="uq_accounts_email"),
        Index("ix_accounts_tenant_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, native_enum=False),
        nullable=False,
        default=AccountStatus.ACTIVE,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    tenant: Mapped["Tenant"] = relationship(back_populates="accounts")
    role: Mapped["Role"] = relationship(back_populates="accounts")
    auth_sessions: Mapped[list["AuthSession"]] = relationship(back_populates="account")
    created_student_files: Mapped[list["StudentFile"]] = relationship(back_populates="created_by_account")
    created_analysis_runs: Mapped[list["StudentAnalysisRun"]] = relationship(back_populates="created_by_account")
    deletion_requests: Mapped[list["DeletionRequest"]] = relationship(back_populates="requested_by_account")


class AuthSession(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
        Index("ix_auth_sessions_account_expires_at", "account_id", "expires_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    tenant: Mapped["Tenant"] = relationship(back_populates="auth_sessions")
    account: Mapped["Account"] = relationship(back_populates="auth_sessions")


class DeletionRequest(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "deletion_requests"
    __table_args__ = (Index("ix_deletion_requests_tenant_status", "tenant_id", "status"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    requested_by_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    deletion_mode: Mapped[DeletionMode] = mapped_column(
        Enum(DeletionMode, native_enum=False),
        nullable=False,
        default=DeletionMode.SOFT_DELETE,
    )
    status: Mapped[DeletionRequestStatus] = mapped_column(
        Enum(DeletionRequestStatus, native_enum=False),
        nullable=False,
        default=DeletionRequestStatus.PENDING,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    tenant: Mapped["Tenant"] = relationship(back_populates="deletion_requests")
    requested_by_account: Mapped["Account"] = relationship(back_populates="deletion_requests")
    events: Mapped[list["DeletionEvent"]] = relationship(back_populates="deletion_request", cascade="all, delete-orphan")


class DeletionEvent(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "deletion_events"
    __table_args__ = (Index("ix_deletion_events_request_created", "deletion_request_id", "created_at"),)

    deletion_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deletion_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    file_object_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("file_objects.id", ondelete="SET NULL"), nullable=True)
    action_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    deletion_request: Mapped["DeletionRequest"] = relationship(back_populates="events")


class PrivacyScan(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "privacy_scans"
    __table_args__ = (Index("ix_privacy_scans_tenant_created", "tenant_id", "created_at"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    student_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("student_files.id", ondelete="CASCADE"), nullable=True)
    student_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("student_artifacts.id", ondelete="CASCADE"),
        nullable=True,
    )
    route_name: Mapped[str] = mapped_column(String(120), nullable=False)
    masking_mode: Mapped[PrivacyMaskingMode] = mapped_column(
        Enum(PrivacyMaskingMode, native_enum=False),
        nullable=False,
    )
    status: Mapped[PrivacyScanStatus] = mapped_column(
        Enum(PrivacyScanStatus, native_enum=False),
        nullable=False,
        default=PrivacyScanStatus.SUCCEEDED,
    )
    pii_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    entity_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_text_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    masked_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    tenant: Mapped["Tenant"] = relationship(back_populates="privacy_scans")
