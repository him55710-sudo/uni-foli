# Uni Folia Conservative UX Correction Pass

Date: 2026-03-30

## Scope note

This pass is intentionally conservative.

- Product name remains `uni folia`
- Repository remains `polio`
- Goal: reduce friction and improve workflow clarity without breaking the current visual identity
- Non-goal: full redesign, new design system, or backend flow replacement

## Figma note

The `figma-generate-design` and `figma-use` skills were loaded for this task, but this session did not expose Figma MCP resources, templates, or write tools such as `use_figma` / `search_design_system`.

Result:

- code-grounded audit completed
- conservative Figma-ready proposal documented below
- actual Figma canvas write deferred until Figma MCP access is available in-session

## Audit summary

### What is already working and should be preserved

- Soft premium mood built from blue-tinted surfaces, white cards, gentle borders, and rounded corners
- Card-heavy composition with modest shadows rather than flat utility styling
- Pretendard-based typography and bold heading hierarchy
- Existing animated polish is restrained and mostly aligned with the product tone
- Dashboard, Record, Diagnosis, and Workshop already share a recognizable family resemblance

### Issue-to-file mapping

- App routing and onboarding gate:
  - `frontend/src/App.tsx`
- Shell, sidebar, topbar, footer, mobile navigation:
  - `frontend/src/components/Layout.tsx`
- Dashboard hierarchy, hero dominance, goal surface, plan empty state:
  - `frontend/src/pages/Dashboard.tsx`
- First-run onboarding modal and target ordering:
  - `frontend/src/components/OnboardingModal.tsx`
- Full onboarding flow:
  - `frontend/src/pages/Onboarding.tsx`
- Record upload / masking / parsing flow and status presentation:
  - `frontend/src/pages/Record.tsx`
- Diagnosis goal confirmation, upload, async job state, result state:
  - `frontend/src/pages/Diagnosis.tsx`
- Workshop degraded fallback repetition, quality badge, guest/demo behavior:
  - `frontend/src/pages/Workshop.tsx`
- Guest session behavior and account connection:
  - `frontend/src/contexts/AuthContext.tsx`
  - `frontend/src/pages/Settings.tsx`

### Key UX findings

- The dashboard leads with marketing-style hero copy before operationally useful state.
- The sidebar presents destinations as flat siblings instead of a preparation-to-execution flow.
- First-run guidance exists, but it is split between redirects and modal prompts rather than one persistent path.
- Record has useful technical trust cues, but the step sequence still reads more like status cards than a clear stepper.
- Workshop fallback behavior repeats the same full degraded block on consecutive failures.
- Empty states are visually consistent with the brand, but they often stop short of giving one explicit next action.
- Footer/legal details are accurate enough to keep, but some placeholder phrasing lands awkwardly inside the polished shell.

## Visual preservation rules

### Do not break

- Blue-first palette and soft slate neutrals
- Large radii on major cards and panels
- Current border and shadow softness
- Card-driven page composition
- Premium-but-friendly tone
- Existing typography family and bold emphasis pattern
- Existing motion restraint and non-generic feel

### Safe to change

- Information order inside surfaces
- CTA emphasis and button hierarchy
- Empty-state composition
- Navigation grouping and labels
- Workflow visibility and step framing
- Status-chip language
- Dashboard content balance
- Repetitive degraded/fallback presentation

## Conservative Figma-ready proposal

### Dashboard

- Keep the large white premium container language, but move a strong `next action` card above the brand story.
- Add a visible four-step path: `목표 설정 → 생기부 업로드 → AI 진단 → 작업실`.
- Keep the goal-card and progress-card treatment, but make them operational rather than decorative.
- Reduce hero dominance by moving brand explanation below the immediate action area.
- Empty plan state should explain the missing step and present one primary CTA.

### Sidebar / shell

- Keep the same sidebar width behavior, icon family, rounded nav items, and general shell.
- Group items into `준비 / 분석 / 실행 / 관리`.
- Add a small workflow summary card near the top of the expanded sidebar.
- Add subtle badges per item to imply sequence without inventing fake completion data.
- Improve guest-state signaling with a gentle account-link cue.

### Onboarding entry

- Do not replace onboarding with a long wizard.
- Use dashboard-driven entry:
  - persistent next-step card
  - better target-empty-state CTA
  - existing onboarding modal as the editing surface

### Record

- Keep the current upload surface and trust detail.
- Reframe the three status blocks into a clearer stepper feel.
- Increase emphasis on active / done / error state differences.
- Make retry and “what happens next” cues more obvious.

### Workshop degraded state

- Keep the two-panel workshop structure.
- First degraded reply can stay explanatory.
- Second and later degraded replies should shrink to lighter “continuing in degraded mode” prompts rather than repeating the full fallback block.
- Keep authorship and AI-marking cues untouched.

### Reusable empty-state pattern

- Illustration/icon area
- one-line status label
- strong headline
- warm but operational supporting copy
- exactly one primary CTA
- optional support note for failures or fetch issues

## Safe first slice selected

Implemented first slice:

- `frontend/src/components/Layout.tsx`
  - grouped sidebar sections
  - workflow summary card
  - better current-stage signaling
  - guest-to-Google connection cue
  - footer placeholder phrasing cleanup
- `frontend/src/pages/Dashboard.tsx`
  - new next-action surface
  - visible four-step workflow summary
  - stronger first-run guidance
  - more informative progress / level card
  - reduced hero dominance
  - improved plan empty state with one explicit CTA

Why this slice first:

- It improves clarity across the whole app without touching backend contracts.
- It preserves the visual identity while fixing the highest-friction IA and dashboard issues.
- It creates the right staging area for later Record and Workshop refinements.

## Deferred items

- Record stepper polish
  - deferred because it is best handled as its own focused pass after the shell and dashboard cueing are in place
- Workshop degraded messaging changes
  - deferred because it should be updated together with response-state tracking, not as isolated copy swaps
- Figma canvas write
  - deferred because Figma MCP write access was not available in this session
