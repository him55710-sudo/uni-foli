# Shared Contracts

This package is reserved for schemas shared by `frontend/` and `backend/`.

## Put Here

- auth request and response contracts
- onboarding payloads
- diagnosis request and response schemas
- project and draft DTOs that must match on both sides

## Do Not Put Here

- backend-only ORM models
- frontend-only view models
- prompt text or business logic

The package is intentionally light right now so auth and onboarding work can start on a clean path.
