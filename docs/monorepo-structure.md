# Monorepo Structure

This document defines how the current Polio repository should be read.

## Canonical Structure

- `frontend/`: source of truth for the web client
- `backend/`: source of truth for Python services and backend packages
- `packages/shared-contracts/`: shared request and response contracts between frontend and backend
- `docs/`: canonical documentation
- `scripts/`: root wrappers for local setup and startup

## Archived Or Quarantined Paths

- `archive/legacy/backend/`: duplicated backend docs and root-level backend notes
- `archive/legacy/tests-root/`: tests that target missing `app/` and `services.admissions.*` scaffolds
- `archive/legacy/scripts/`: deprecated admissions-prefixed root scripts
- `archive/legacy/poli-images/`: unused mascot image source folder
- `archive/legacy/root-gemini-review.md`: historical planning note

Nothing under `archive/legacy/` should be used as a source of truth for new work.

## Paths Explicitly Not Present

The following paths were requested for analysis but do not exist in this checkout:

- `ai studio ui,ux design/`
- `codex-backend/polio-codex-polio-backend-bootstrap/`
- root `app/`, `db/`, `services/`, `pipelines/`

Any old docs or tests that mention those paths are describing a different or outdated structure.

## Temporary Holdouts

- `prompts/`: root prompt assets still waiting for explicit backend loader wiring
- `references/`: open-source reference index used by architecture notes, not runtime code

These are intentionally left outside `archive/legacy/` because they may still be needed in the next wiring phase.

## Development Rules

- New backend implementation work goes under `backend/`.
- New frontend implementation work goes under `frontend/`.
- New shared API contracts should be added under `packages/shared-contracts/`.
- New docs belong in `docs/`, not duplicated under `backend/`.
- Safety rules override convenience: if evidence is missing, the product should stop and guide the next action.

## Immediate Next Step

With this structure in place, the next implementation phase should start with:

- auth contract definitions in `packages/shared-contracts/`
- frontend auth and onboarding routes in `frontend/`
- backend auth and onboarding APIs in `backend/services/api/`
