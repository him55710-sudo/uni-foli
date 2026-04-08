# chat.guided-drafting-state

- Version: `1.0.0`
- Category: `chat`
- Status: `wired-shared-fragment`

## Purpose

Provide a compact drafting-state contract so chat prompts can stay short while preserving continuity.

## Prompt Body

Use the provided guided drafting state as the source of long-term memory.

State handling rules:

- Treat `subject`, `selected_topic`, `thesis_question`, `accepted_outline` as current plan.
- Treat `confirmed_evidence_points` as claim-safe anchors.
- Treat `unresolved_evidence_gaps` as mandatory uncertainty markers.
- Treat `starter_draft_markdown` as draft seed, not as final answer.
- Never invent facts that are missing from this state.
- If state conflicts with new user input, prefer the newest explicit user instruction and mark what changed.
