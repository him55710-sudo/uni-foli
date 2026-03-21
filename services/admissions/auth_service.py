from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import pbkdf2_hmac, sha256
from secrets import token_bytes, token_urlsafe
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from db.models.security import Account, AuthSession, Role, Tenant
from domain.enums import AccountStatus, LifecycleStatus, PrivacyMaskingMode
from services.admissions.utils import ensure_uuid, slugify


DEFAULT_ROLES = [
    {
        "slug": "super_admin",
        "name": "Super Admin",
        "description": "Global operational access.",
        "is_admin": True,
        "global_access": True,
    },
    {
        "slug": "tenant_admin",
        "name": "Tenant Admin",
        "description": "Tenant-level operational admin.",
        "is_admin": True,
        "global_access": False,
    },
    {
        "slug": "reviewer",
        "name": "Reviewer",
        "description": "Reviewer and moderation access.",
        "is_admin": True,
        "global_access": False,
    },
    {
        "slug": "member",
        "name": "Member",
        "description": "Regular product user.",
        "is_admin": False,
        "global_access": False,
    },
]


@dataclass(slots=True)
class AuthenticatedPrincipal:
    account_id: UUID
    tenant_id: UUID
    role_slug: str
    email: str
    full_name: str
    is_admin: bool
    global_access: bool

    def can_access_tenant(self, tenant_id: UUID | None) -> bool:
        return self.global_access or tenant_id is None or tenant_id == self.tenant_id


class AuthService:
    def bootstrap_defaults(self, session: Session) -> None:
        settings = get_settings()
        if not settings.auth_bootstrap_default_accounts:
            return

        roles = {role.slug: role for role in self._ensure_roles(session)}
        tenant = self._ensure_tenant(
            session,
            slug=settings.auth_default_tenant_slug,
            name=settings.auth_default_tenant_name,
            masking_mode=settings.privacy_default_masking_mode,
            retention_days=settings.student_data_retention_days,
        )
        self._ensure_account(
            session,
            tenant=tenant,
            role=roles["super_admin"],
            email=settings.auth_default_admin_email,
            full_name="Local Admin",
            password=settings.auth_default_admin_password,
        )
        self._ensure_account(
            session,
            tenant=tenant,
            role=roles["reviewer"],
            email=settings.auth_default_reviewer_email,
            full_name="Local Reviewer",
            password=settings.auth_default_reviewer_password,
        )
        self._ensure_account(
            session,
            tenant=tenant,
            role=roles["member"],
            email=settings.auth_default_member_email,
            full_name="Local Member",
            password=settings.auth_default_member_password,
        )
        session.flush()

    def authenticate(self, session: Session, *, email: str, password: str) -> Account | None:
        stmt = (
            select(Account)
            .where(Account.email == email.strip().lower())
            .options(joinedload(Account.role), joinedload(Account.tenant))
        )
        account = session.scalar(stmt)
        if account is None or account.status != AccountStatus.ACTIVE:
            return None
        if not self.verify_password(password, account.password_hash):
            return None
        account.last_login_at = datetime.now(UTC)
        session.flush()
        return account

    def create_session_token(self, session: Session, *, account: Account) -> tuple[str, AuthSession]:
        token = f"plio_{token_urlsafe(32)}"
        expires_at = datetime.now(UTC) + timedelta(minutes=get_settings().auth_session_ttl_minutes)
        auth_session = AuthSession(
            tenant_id=account.tenant_id,
            account_id=account.id,
            token_hash=self.hash_token(token),
            token_prefix=token[:12],
            expires_at=expires_at,
            metadata_json={},
        )
        session.add(auth_session)
        session.flush()
        session.refresh(auth_session)
        return token, auth_session

    def revoke_session(self, session: Session, *, raw_token: str) -> None:
        auth_session = session.scalar(select(AuthSession).where(AuthSession.token_hash == self.hash_token(raw_token)))
        if auth_session is None:
            return
        auth_session.revoked_at = datetime.now(UTC)
        session.flush()

    def resolve_principal(self, session: Session, *, raw_token: str) -> AuthenticatedPrincipal | None:
        stmt = (
            select(AuthSession)
            .where(AuthSession.token_hash == self.hash_token(raw_token))
            .options(
                joinedload(AuthSession.account).joinedload(Account.role),
                joinedload(AuthSession.account).joinedload(Account.tenant),
            )
        )
        auth_session = session.scalar(stmt)
        if auth_session is None or auth_session.revoked_at is not None:
            return None
        expires_at = auth_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            return None
        auth_session.last_seen_at = datetime.now(UTC)
        account = auth_session.account
        if account.status != AccountStatus.ACTIVE:
            return None
        session.flush()
        return AuthenticatedPrincipal(
            account_id=account.id,
            tenant_id=account.tenant_id,
            role_slug=account.role.slug,
            email=account.email,
            full_name=account.full_name,
            is_admin=account.role.is_admin,
            global_access=account.role.global_access,
        )

    def create_account(
        self,
        session: Session,
        *,
        tenant_id: str | UUID,
        role_slug: str,
        email: str,
        full_name: str,
        password: str,
    ) -> Account:
        tenant = session.get(Tenant, ensure_uuid(tenant_id))
        role = session.scalar(select(Role).where(Role.slug == role_slug))
        if tenant is None or role is None:
            raise ValueError("Tenant or role not found.")
        return self._ensure_account(session, tenant=tenant, role=role, email=email, full_name=full_name, password=password)

    def get_account_by_email(self, session: Session, email: str) -> Account | None:
        return session.scalar(select(Account).where(Account.email == email.strip().lower()))

    def _ensure_roles(self, session: Session) -> list[Role]:
        roles: list[Role] = []
        for row in DEFAULT_ROLES:
            role = session.scalar(select(Role).where(Role.slug == row["slug"]))
            if role is None:
                role = Role(
                    slug=row["slug"],
                    name=row["name"],
                    description=row["description"],
                    is_admin=row["is_admin"],
                    global_access=row["global_access"],
                    permissions_json={},
                )
                session.add(role)
                session.flush()
            roles.append(role)
        return roles

    def _ensure_tenant(
        self,
        session: Session,
        *,
        slug: str,
        name: str,
        masking_mode: PrivacyMaskingMode,
        retention_days: int,
    ) -> Tenant:
        tenant = session.scalar(select(Tenant).where(Tenant.slug == slugify(slug)))
        if tenant is not None:
            return tenant
        tenant = Tenant(
            slug=slugify(slug),
            name=name,
            status=LifecycleStatus.ACTIVE,
            default_retention_days=retention_days,
            masking_mode=masking_mode,
            pii_detection_enabled=True,
            metadata_json={},
        )
        session.add(tenant)
        session.flush()
        return tenant

    def _ensure_account(
        self,
        session: Session,
        *,
        tenant: Tenant,
        role: Role,
        email: str,
        full_name: str,
        password: str,
    ) -> Account:
        normalized_email = email.strip().lower()
        account = session.scalar(select(Account).where(Account.email == normalized_email))
        if account is not None:
            return account
        account = Account(
            tenant_id=tenant.id,
            role_id=role.id,
            email=normalized_email,
            full_name=full_name,
            password_hash=self.hash_password(password),
            status=AccountStatus.ACTIVE,
            metadata_json={},
        )
        session.add(account)
        session.flush()
        return account

    def hash_password(self, password: str) -> str:
        salt = token_bytes(16)
        iterations = 600_000
        digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return "pbkdf2_sha256${}${}${}".format(iterations, salt.hex(), digest.hex())

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            algorithm, iterations, salt_hex, digest_hex = password_hash.split("$", 3)
        except ValueError:
            return False
        if algorithm != "pbkdf2_sha256":
            return False
        digest = pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return digest.hex() == digest_hex

    def hash_token(self, raw_token: str) -> str:
        return sha256(raw_token.encode("utf-8")).hexdigest()


auth_service = AuthService()
