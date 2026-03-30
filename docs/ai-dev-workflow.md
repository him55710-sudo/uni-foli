# AI Dev Workflow

## Why this exists

Polio uses AI agents to help with planning, implementation, review, QA, and release, but the workflow must stay grounded in this product's guardrails:

- execution-oriented support for students
- reduced anxiety, not anxiety marketing
- evidence-grounded drafting
- no fabricated activities
- no admissions guarantees
- next safe action when evidence is missing

gstack is installed repo-locally so the workflow can live with the repository instead of a single developer machine.

For daily execution order, review gates, QA scope, and release decisions, use `docs/gstack-playbook.md` as the primary operating document. This file remains the setup and repo-local usage reference.

## Repo-local layout

- gstack source snapshot: `.agents/skills/gstack`
- repo-local bun runtime: `.agents/tools/bun/bin/bun.exe`
- published Codex-oriented skills: `.agents/skills/gstack-*`
- gstack's internal generated cache: `.agents/skills/gstack/.agents/skills/`
- Windows refresh path: `scripts/gstack-refresh.ps1` invokes Git Bash, then republishes the Codex-facing skills into repo root `.agents/skills/`
- refresh generated Codex skills: `.\scripts\gstack-refresh.cmd`
- verify local install: `.\scripts\gstack-doctor.cmd`

Note:
Some managed Codex environments do not hot-reload repo-local skills inside an already running session. The safe default is:

1. refresh the generated skills
2. start a new agent session
3. invoke the generated skill name, for example `gstack-office-hours`

If your agent shell already exposes slash aliases, treat these as the same:

- `/office-hours` = `gstack-office-hours`
- `/plan-ceo-review` = `gstack-plan-ceo-review`
- `/plan-eng-review` = `gstack-plan-eng-review`
- `/plan-design-review` = `gstack-plan-design-review`
- `/review` = `gstack-review`
- `/qa` = `gstack-qa`
- `/ship` = `gstack-ship`
- `/retro` = `gstack-retro`
- `/codex` = `gstack-codex`

## One-time setup already applied in this repo

- cloned the official gstack repository into `.agents/skills/gstack`
- installed bun locally into `.agents/tools/bun`
- generated Codex-targeted skill files into `.agents/skills/gstack-*`

To refresh after a gstack pull or local edits:

```powershell
.\scripts\gstack-refresh.cmd
.\scripts\gstack-doctor.cmd
```

`gstack-refresh` regenerates skills inside the vendored gstack checkout and then publishes the Codex-facing skill folders back into the repo root `.agents/skills/` so future agents can discover them from the project workspace.

## Standard Polio development loop

### 1. Idea refinement

Use when:

- a new public page or app workflow is being proposed
- an AI behavior change affects trust, provenance, or safety
- a feature is only half-formed and the user need is still vague

Skill:

- `/office-hours`

Polio-specific goal:

- clarify the user problem before touching code
- verify the feature reduces anxiety
- make sure the flow ends in a clear next safe action

Recommended output:

- a short plan in `docs/plans/<date>-<slug>.md`

Example prompt:

```text
/office-hours
We want to improve the record upload -> diagnosis -> workshop handoff for Uni Folia.
The outcome should make the next safe action clearer and preserve grounded drafting.
```

### 2. Feature spec and product shaping

Use when:

- a plan exists, but scope, ambition, or user value still feel unclear

Skills:

- `/plan-ceo-review`
- `/plan-design-review` when UI or conversion changes are involved

Polio-specific goal:

- avoid building a generic AI chatbot surface
- keep the product clearly record-first
- preserve the soft, premium, low-anxiety visual language

Example prompt:

```text
/plan-ceo-review
Review docs/plans/2026-03-30-record-workflow.md.
Push on whether this actually improves student preparation rather than adding features.
```

### 3. Architecture and risk review

Use when:

- the plan touches `backend/`
- the plan changes auth, uploads, provenance, rendering, diagnosis, or workshop logic
- shared contracts or route structure may change

Skill:

- `/plan-eng-review`

Polio-specific goal:

- keep canonical paths intact
- protect trust boundaries between records, diagnosis, and drafting
- require tests and rollback-safe changes for risky backend work

Review against these docs when relevant:

- `docs/07-diagnosis-engine/README.md`
- `docs/08-chat-orchestration/README.md`
- `docs/09-drafting-provenance/README.md`

### 4. Implementation

Implement only after the plan is clear.

Primary local commands:

```powershell
.\scripts\start-api.cmd
.\scripts\start-frontend.cmd
```

Direct checks:

```powershell
cd frontend
npm run build
```

```powershell
python -m pytest tests/smoke -q
```

Run this when auth, upload, workshop, or security-sensitive paths changed:

```powershell
.\scripts\security-regression.cmd
```

Implementation rules:

- frontend changes only under `frontend/`
- backend changes only under `backend/`
- contracts under `packages/shared-contracts/`
- docs under `docs/`

### 5. Code review

Use when:

- the branch is feature-complete and should be reviewed before merge

Skill:

- `/review`

Polio-specific review lens:

- any trust-boundary leak between records and generated content
- any UI copy implying guarantees or fabricated experience
- any route/auth regression between public and protected layers
- any backend path that can silently degrade provenance

Example prompt:

```text
/review
Review this branch against main. Focus on auth boundaries, inquiry handling, public/app route separation, and grounded drafting safeguards.
```

### 6. Browser QA

Use when:

- a user-facing flow changed
- a regression is likely to be visual, interaction, or copy related

Skill:

- `/qa`

Always test these surfaces when relevant:

- public: `/`, `/faq`, `/contact`, `/auth`, `/terms`, `/privacy`
- app: `/app`, `/app/record`, `/app/diagnosis`, `/app/workshop`, `/app/archive`, `/app/trends`, `/app/settings`, `/onboarding`

Polio-specific QA checklist:

- does the UI make the next action obvious
- does any copy overpromise outcomes
- does any state hide uncertainty instead of showing it
- do empty states guide the user safely
- do public -> auth -> app transitions stay clear

### 7. PR / release

Use when:

- review and QA are complete
- the branch is ready for PR or release prep

Skill:

- `/ship`

Polio-specific expectation:

- include test/build results
- mention user-facing risk areas
- mention safety-sensitive behavior changes
- keep release notes honest and specific

### 8. Retrospective

Use when:

- the feature lands
- the sprint ends
- the team wants to compare shipped work against the original intent

Skill:

- `/retro`

Polio-specific retro questions:

- did the work reduce confusion or add it
- did we preserve grounded drafting and provenance
- did QA catch the right regressions
- what should become a default checklist item next sprint

### 9. Independent second opinion

Use when:

- a plan feels plausible but risky
- review findings are inconclusive
- you want an adversarial challenge before merge

Skill:

- `/codex`

Good uses in Polio:

- challenge record-to-drafting trust assumptions
- challenge auth and onboarding flows
- challenge whether a UX change actually reduces anxiety

## Recommended operating sequence

For a typical feature:

1. write the brief in `docs/plans/`
2. run `/office-hours`
3. run `/plan-ceo-review`
4. run `/plan-design-review` for UI scope
5. run `/plan-eng-review`
6. implement
7. run builds/tests
8. run `/review`
9. run `/qa`
10. run `/ship`
11. run `/retro` after landing

For a small bugfix:

1. implement
2. run targeted build/tests
3. run `/review`
4. run `/qa` if the bug was user-visible
5. run `/ship`

## What we are deliberately not doing

We are not using gstack to justify:

- shipping without product guardrails
- inventing user activity or record content
- turning Polio into a generic chatbot
- replacing real engineering verification with AI-only confidence
- hiding uncertainty when evidence is weak

## Current status

As of this setup:

- repo-local gstack source is present
- repo-local bun is present
- Codex-targeted generated skill files are present
- `.\scripts\gstack-doctor.cmd` is the fastest verification entry point

If `gstack-doctor` passes but your current agent session does not see the skills, start a new session after refresh.
