# Admin Access Rules Draft

## Roles

- `super_admin`
  - global access across tenants
  - can inspect all admin routes
- `tenant_admin`
  - admin access within own tenant only
- `reviewer`
  - admin-class role within own tenant for review and moderation tasks
- `member`
  - non-admin product user

## Protected Surfaces

- `/api/v1/admin/*`
- `/api/v1/student-files/*`
- `/api/v1/analysis/runs/*`

## Rules

- Admin routes require admin role.
- Tenant-bound admin listings default to caller tenant.
- `super_admin` can optionally inspect all tenants or a chosen tenant.
- Student file access requires same-tenant principal.
- Analysis run access requires same-tenant principal.

## Operational Expectations

- Do not export raw student text from admin APIs by default.
- Use `privacy_scans` and masked previews for first-pass inspection.
- Prefer deletion requests over direct destructive actions.

## TODO

- route-level RBAC policy map
- per-action permission set in `roles.permissions_json`
- reviewer-only moderation actions separate from tenant admin actions
