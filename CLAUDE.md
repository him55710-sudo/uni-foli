# Polio Agent Guide

This repository uses a repo-local gstack install as its default AI development workflow.

## Canonical Paths

- `frontend/`: web product source of truth
- `backend/`: API and runtime source of truth
- `packages/shared-contracts/`: shared request/response contracts
- `docs/`: product, safety, architecture, workflow docs
- `scripts/`: local wrappers for setup, run, QA, and gstack maintenance

Do not treat `archive/legacy/` as a working surface.

## Product Guardrails

- Reduce anxiety; do not increase it with exaggerated product claims.
- Ground drafting and planning in real student records, goals, and explicit evidence.
- Do not fabricate activities or overstate what the student did not actually do.
- Do not imply guaranteed admission outcomes.
- When evidence is weak, stop guessing and recommend the next safe action.

## Repo-Local gstack

- Source checkout: `.agents/skills/gstack`
- Repo-local bun runtime: `.agents/tools/bun/bin/bun.exe`
- Generated Codex-oriented skills are published to: `.agents/skills/gstack-*`
- gstack's own generated cache lives under: `.agents/skills/gstack/.agents/skills/`
- On Windows, `gstack-refresh` shells out through Git Bash because the gstack generator is more reliable there than direct Bun invocation from PowerShell.
- Refresh generated skills: `.\scripts\gstack-refresh.cmd`
- Verify install health: `.\scripts\gstack-doctor.cmd`

## Skill Routing

Use these skills by default when the task matches.

- `/office-hours` or `gstack-office-hours`
  Use before coding a new product surface, AI workflow, onboarding flow, support flow, or safety-sensitive feature.
- `/plan-ceo-review` or `gstack-plan-ceo-review`
  Use after the first draft of a plan when we need to test ambition, product wedge, scope, and user value.
- `/plan-eng-review` or `gstack-plan-eng-review`
  Use before implementation to lock architecture, contracts, failure modes, migrations, and tests.
- `/plan-design-review` or `gstack-plan-design-review`
  Use for any meaningful UI/UX scope in `frontend/`, especially dashboard, onboarding, workshop, FAQ, landing, or contact surfaces.
- `/review` or `gstack-review`
  Use before merge or PR creation to review the diff against base and catch prod-facing issues.
- `/qa` or `gstack-qa`
  Use after implementation to test real user flows in a browser and fix regressions.
- `/ship` or `gstack-ship`
  Use when the branch is ready for PR/landing and review + tests + release notes should be bundled.
- `/retro` or `gstack-retro`
  Use at the end of a sprint or major feature push to summarize what shipped, what regressed, and what to improve next.
- `/codex` or `gstack-codex`
  Use when an independent second opinion is useful for architecture, review, or adversarial challenge.

## Standard Loop

1. Write or update the feature brief in `docs/plans/` or an existing design/product doc.
2. Run idea shaping with `/office-hours`.
3. Run `/plan-ceo-review`, `/plan-eng-review`, and `/plan-design-review` as needed.
4. Implement in canonical paths only.
5. Run `/review` before merge.
6. Run `/qa` on public and authenticated flows.
7. Run `/ship` when opening the PR or preparing release.
8. Run `/retro` after the feature lands.

Detailed setup usage lives in `docs/ai-dev-workflow.md`.
Daily execution order, QA scope, and release gates live in `docs/gstack-playbook.md`.
