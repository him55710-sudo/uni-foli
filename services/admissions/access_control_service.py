from __future__ import annotations

from services.admissions.auth_service import AuthenticatedPrincipal


class AccessControlError(PermissionError):
    pass


class AccessControlService:
    def require_admin(self, principal: AuthenticatedPrincipal) -> None:
        if principal.is_admin:
            return
        raise AccessControlError("Admin access is required.")

    def require_tenant_access(self, principal: AuthenticatedPrincipal, tenant_id) -> None:
        if principal.can_access_tenant(tenant_id):
            return
        raise AccessControlError("Tenant boundary violation.")

    def require_same_tenant_student_file(self, principal: AuthenticatedPrincipal, student_file) -> None:
        self.require_tenant_access(principal, getattr(student_file, "tenant_id", None))

    def require_same_tenant_analysis_run(self, principal: AuthenticatedPrincipal, analysis_run) -> None:
        self.require_tenant_access(principal, getattr(analysis_run, "tenant_id", None))


access_control_service = AccessControlService()
