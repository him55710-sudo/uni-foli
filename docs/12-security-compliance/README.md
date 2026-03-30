# 12 Security And Compliance

This backend handles educational records and minor-related data.
Security design must be explicit.

## Threat model

- stolen session tokens
- file upload abuse
- prompt injection through uploaded or retrieved content
- cross-tenant data leaks
- over-retention of sensitive records

## Required controls

- signed upload URLs
- storage isolation by tenant scope
- row-level authorization in the data layer
- prompt-sanitization and source-trust filtering
- append-only audit log for sensitive actions

## Data classes

- public source material
- user-private uploads
- masked working text
- raw high-sensitivity text

Each class needs a different access rule and retention rule.

## Secrets and keys

- keep provider keys out of prompts and logs
- rotate secrets
- separate production and staging credentials

## Production launch checks

- `APP_ENV` must stay `production` outside local development.
- `AUTH_ALLOW_LOCAL_DEV_BYPASS` must stay `false` outside local development.
- `APP_DEBUG` should stay `false`.
- interactive docs should stay disabled unless explicitly needed for a controlled environment.
- if social login is enabled, every redirect URI must target the real frontend origin, not localhost.
- if KCI search is enabled, `KCI_API_KEY` must be set explicitly.
- render artifacts must be served through authenticated owner-scoped routes, not exposed filesystem paths.
- workshop stream tokens must expire and be treated as temporary transport credentials only.

## Regression harness

Run the security-focused regression suite before launch-sensitive changes:

```powershell
.\scripts\security-regression.cmd
```

This suite covers:

- authn and authz rejection paths
- OAuth state tamper, replay, and client-binding checks
- upload type and size rejection
- hidden asset/storage path invariants
- render download path-root enforcement
- workshop stream token expiry
- production config safety invariants

## Compliance posture

- document lawful basis and consent events
- support delete and export requests
- minimize stored raw data
- do not build features that require illegal or ambiguous data acquisition

## Current hardening report

- `docs/reports/polio_security_hardening_20260330.md`
