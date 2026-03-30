# Polio Security Hardening Pass

Date: 2026-03-30
Repository: `him55710-sudo/polio`
Product: `uni folia`

## Scope

This pass reviewed the current monorepo as-is and hardened the highest-value production risks without changing the core product philosophy:

- evidence-grounded behavior stays intact
- provenance and authorship trails stay intact
- local development support stays available, but only behind explicit local-only gates

## Threat Model Summary

| Surface | Data exposed | Attacker goal | Likely abuse mode | Current protection level |
| --- | --- | --- | --- | --- |
| Authentication | user identity, project ownership | impersonate users or reach protected routes | invalid JWTs, local-bypass drift, social-login replay | moderate after existing JWT checks; hardened further for OAuth state and env separation |
| Authorization | projects, drafts, uploads, documents, jobs, workshops | cross-user data access | guessing IDs across routes | generally strong owner scoping already existed; verified and regression-tested |
| Public vs protected routes | research search, render/export endpoints | anonymous abuse or data harvesting | unprotected search or expensive route access | improved by requiring auth on research search and keeping render/export owner-scoped |
| Social login callback flow | account bootstrap, Firebase custom token minting | login CSRF or replay | reused OAuth `state`, cross-browser state reuse | previously weak; hardened with client binding and one-time-use replay rejection |
| File upload and parsing | student records, parsed text, ingest artifacts | upload abuse, parser-triggered leakage | oversized files, bad MIME, malformed content, persisted raw parser errors | upload validation already decent; hardened persisted error handling and regression coverage |
| Asset/file serving | render artifacts, upload storage paths | local path disclosure or file exfiltration | leaked `stored_path` / `output_path`, traversal through download routes | previously exposed internal paths; now replaced with owner-scoped download URLs and path-root checks |
| Render/export access | generated report files | steal another user's artifact or enumerate files | cross-user job access, direct file path leakage | owner scoping already present; hardened download handling and response shape |
| Workshop/chat flows | workshop transcripts, draft artifacts, stream tokens | hijack or replay live render streams | non-expiring stream tokens, repeated token reuse | previously weak; now TTL-bound and invalidated on expiry/completion |
| Research/reference flows | external search traffic, ingested source records | abuse paid/external provider quotas | anonymous paper search, unbounded ingestion payloads | improved by auth, rate limits, size limits, and KCI key enforcement |
| Worker/job state | failure reasons, retry metadata | enumerate jobs or harvest internal errors | cross-project job access, raw exception persistence | owner scoping already present; failure reason sanitization tightened |
| Logs and errors | internal paths, stack traces, provider behavior | learn filesystem or runtime layout | raw exception strings surfaced to users or stored in DB | user-visible leakage reduced; internal operational logs still require controlled access |
| Secrets/config | JWT keys, OAuth secrets, KCI key, redirect URIs | run prod with local or dummy settings | localhost callbacks, dummy provider config, env drift | improved by stricter validation and explicit required-env guidance |

## Severity-Ranked Gap Report

### Critical

- Internal storage path exposure in API responses.
  - Why it mattered: `stored_path`, `sha256`, and `output_path` disclosed filesystem layout and artifact locations that were not needed by the frontend.
  - Files: `backend/services/api/src/polio_api/schemas/document.py`, `backend/services/api/src/polio_api/schemas/upload_asset.py`, `backend/services/api/src/polio_api/schemas/render_job.py`, `backend/services/api/src/polio_api/services/render_job_service.py`
  - Exploit scenario: an authenticated user collects relative storage paths and probes download/file-serving behavior for traversal or bucket layout leakage.
  - Smallest safe fix: stop serializing internal file fields and expose only an owner-scoped `download_url`.
  - Launch blocker: yes.

- Workshop stream tokens never expired server-side.
  - Why it mattered: a stolen stream token could remain valid far beyond the advertised TTL.
  - Files: `backend/services/api/src/polio_api/api/routes/workshops.py`, `backend/services/api/src/polio_api/db/models/workshop.py`, `backend/services/api/src/polio_api/core/database.py`, `backend/alembic/versions/20260330_0011_add_workshop_stream_token_expiry.py`
  - Exploit scenario: anyone with an old SSE URL can reconnect and retrieve a rendered workshop artifact.
  - Smallest safe fix: persist `stream_token_expires_at`, enforce it on `/events`, and clear expired tokens.
  - Launch blocker: yes.

### High

- OAuth `state` was signed but not client-bound and not replay-resistant.
  - Why it mattered: it allowed practical login CSRF or replay within the state TTL window.
  - Files: `backend/services/api/src/polio_api/core/oauth_state.py`, `backend/services/api/src/polio_api/api/routes/auth.py`
  - Exploit scenario: an attacker reuses a valid state in another browser session and races the callback flow.
  - Smallest safe fix: bind state to request fingerprint material and reject replayed nonces.
  - Launch blocker: yes.

- Public, unthrottled research paper search proxied third-party providers.
  - Why it mattered: it exposed provider quota and backend bandwidth to anonymous abuse.
  - Files: `backend/services/api/src/polio_api/api/routes/research.py`
  - Exploit scenario: scripted anonymous traffic burns Semantic Scholar or KCI quota and degrades launch reliability.
  - Smallest safe fix: require auth and add rate limiting.
  - Launch blocker: yes.

- Hardcoded KCI fallback API key.
  - Why it mattered: production could silently depend on a shared or placeholder credential.
  - Files: `backend/services/api/src/polio_api/core/config.py`, `backend/services/api/src/polio_api/services/scholar_service.py`
  - Exploit scenario: staging/prod deploys appear healthy while using an unintended shared key, then fail or violate provider expectations.
  - Smallest safe fix: require `KCI_API_KEY` explicitly and fail closed when missing.
  - Launch blocker: yes for KCI-enabled launch.

- Raw ingest/job failure strings could be stored and later returned through user-visible APIs.
  - Why it mattered: parser or worker exceptions can contain paths, URLs, and backend details.
  - Files: `backend/services/api/src/polio_api/core/security.py`, `backend/services/api/src/polio_api/services/document_service.py`, `backend/services/api/src/polio_api/services/research_service.py`, `backend/services/api/src/polio_api/services/async_job_service.py`, `backend/services/api/src/polio_api/schemas/document.py`, `backend/services/api/src/polio_api/schemas/research.py`, `backend/services/api/src/polio_api/schemas/upload_asset.py`
  - Exploit scenario: a malformed upload or provider failure returns internal path material to end users.
  - Smallest safe fix: sanitize before persistence and re-sanitize on serialization.
  - Launch blocker: yes.

### Medium

- High-risk route payloads lacked size boundaries.
  - Why it mattered: authenticated abuse could still create memory/CPU pressure on draft, workshop, export, and research ingestion flows.
  - Files: `backend/services/api/src/polio_api/schemas/project.py`, `backend/services/api/src/polio_api/schemas/draft.py`, `backend/services/api/src/polio_api/schemas/user.py`, `backend/services/api/src/polio_api/schemas/workshop.py`, `backend/services/api/src/polio_api/schemas/research.py`, `backend/services/api/src/polio_api/schemas/render_job.py`, `backend/services/api/src/polio_api/api/routes/projects.py`
  - Exploit scenario: very large authenticated payloads slow parsing, storage, or render preparation.
  - Smallest safe fix: add field-level max lengths and export body limits.
  - Launch blocker: not by itself, but should be fixed before public launch.

- Expensive retry/process endpoints lacked throttling.
  - Why it mattered: users could repeatedly trigger inline processing on jobs and render routes.
  - Files: `backend/services/api/src/polio_api/api/routes/jobs.py`, `backend/services/api/src/polio_api/api/routes/render_jobs.py`, `backend/services/api/src/polio_api/api/routes/workshops.py`
  - Exploit scenario: repeated retries/process requests create avoidable backend load spikes.
  - Smallest safe fix: add route-level rate limiting.
  - Launch blocker: not alone, but worth fixing pre-launch.

- Non-local production could still be configured with localhost OAuth redirect URIs.
  - Why it mattered: this is a classic environment-drift failure that breaks auth and can mask rollout mistakes.
  - Files: `backend/services/api/src/polio_api/core/config.py`
  - Exploit scenario: staging or production is deployed with live credentials and a localhost callback target.
  - Smallest safe fix: reject localhost redirect URIs outside `APP_ENV=local`.
  - Launch blocker: yes if social login is enabled.

### Low

- Internal operational logs still rely on standard stack traces for some worker/render failures.
  - Why it mattered: not public, but log retention and access control must stay tight.
  - Files: `backend/services/api/src/polio_api/main.py`, `backend/services/api/src/polio_api/services/render_job_service.py`, `backend/services/api/src/polio_api/api/routes/workshops.py`, `backend/services/api/src/polio_api/api/routes/projects.py`
  - Exploit scenario: overly broad log access reveals filesystem or dependency details.
  - Smallest safe fix: keep logs restricted and review retention/redaction policies at deploy time.
  - Launch blocker: no, but manual ops review is required.

## Priority Classification

### Must Fix Now

- internal path exposure in uploads/documents/render jobs
- workshop stream token expiry enforcement
- OAuth state client binding and replay rejection
- authenticated plus rate-limited research search
- fail-closed KCI API key handling
- persisted user-visible error sanitization

### Should Fix Before Public Launch

- payload size caps across draft, workshop, research, export, and profile flows
- rate limits on retry/process/render trigger endpoints
- localhost redirect rejection outside local development

### Post-Launch Hardening

- stronger shared replay storage for OAuth state across multiple API instances
- broader log redaction strategy if production logs are widely accessible
- per-route abuse telemetry and alerts on repeated 401/429 patterns

### Acceptable Risk For Now

- in-process rate limiting rather than shared external rate-limit state
- in-process OAuth replay cache rather than distributed nonce storage

These are acceptable only because the current repo does not yet maintain a shared cache or gateway policy layer.

## Exact Fixes Applied

- Removed internal file fields from upload, document, and render-job API responses.
- Replaced render-job `output_path` exposure with owner-scoped `download_url`.
- Added secure render artifact download route with export-root path validation.
- Added `stream_token_expires_at` persistence and enforcement for workshop SSE tokens.
- Added OAuth state client binding plus one-time-use nonce rejection.
- Sanitized persisted document, research, and async-job failure reasons before storage and on serialization.
- Required authentication and added rate limits on research paper search.
- Added rate limits for job retry/process, render job create/process, and workshop render/token endpoints.
- Required an explicit `KCI_API_KEY` instead of falling back to a hardcoded key.
- Added production validation for localhost OAuth redirect URIs.
- Added request-size limits across project, draft, workshop, research, render, export, and user-profile payloads.

## Security Regression Harness

Primary harness:

- `.\scripts\security-regression.cmd`

It runs:

- `backend/tests/test_security_hardening.py`
- `backend/tests/test_auth_and_diagnosis_runtime.py`
- `backend/tests/test_ingest_and_render.py`

Coverage focus:

- auth and authz rejection paths
- OAuth state tamper, binding mismatch, and replay
- upload type/size rejection
- hidden storage-path invariants
- render download path-root enforcement
- workshop stream token expiry
- non-local config safety invariants

## Operational Hardening Notes

- Required for production auth:
  - `APP_ENV=production`
  - `AUTH_JWT_SECRET` or `AUTH_JWT_PUBLIC_KEY`
  - `AUTH_ALLOW_LOCAL_DEV_BYPASS=false`
- Required when social login is enabled:
  - `AUTH_SOCIAL_LOGIN_ENABLED=true`
  - `AUTH_SOCIAL_STATE_SECRET`
  - real provider credentials
  - non-localhost provider redirect URIs outside local
- Required when KCI search is exposed:
  - `KCI_API_KEY`
- Recommended production defaults:
  - keep `API_DOCS_ENABLED=false`
  - keep `APP_DEBUG=false`
  - keep `CORS_ALLOW_CREDENTIALS=true` only with explicit trusted origins
  - keep guest mode disabled on the frontend except explicit local/dev use
- Deploy-time checks:
  - run `.\scripts\security-regression.cmd`
  - verify `/api/v1/research/papers` rejects anonymous calls
  - verify render responses expose `download_url`, not filesystem paths
  - verify workshop SSE tokens expire in about five minutes
  - verify production env fails fast on localhost OAuth callback settings

## Residual Risks

- OAuth replay rejection is process-local, not distributed across multiple API instances.
- Rate limiting is process-local and should eventually move to shared infrastructure if traffic grows.
- Internal logs can still contain stack traces; this now affects operators only, not end users, but access control and retention must be reviewed.
- This pass did not introduce antivirus scanning, sandboxed document conversion, or external WAF controls because the current repo does not maintain that infrastructure yet.

## Manual Launch Review Still Required

- verify production JWT issuer/audience settings against the real identity provider
- verify every enabled OAuth provider callback URL in the deployed environment
- verify log sink permissions and retention for stack traces
- verify staging and production do not share secrets or third-party API keys
- verify external provider quotas, especially Semantic Scholar and KCI
- verify frontend build disables guest mode unless explicitly intended for the launch environment
