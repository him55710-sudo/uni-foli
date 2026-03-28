# 07 Diagnosis Engine

This engine turns uploads and retrieved evidence into actionable feedback.

## Outputs

- topic fit score
- evidence coverage score
- risk flags
- recommended next actions
- alternate topic pivots

## Replace vague "pass predictor"

Do not produce "you will get in" outputs.
Produce:

- fit-to-target analysis
- published-criteria coverage
- writing-depth gaps
- originality and support gaps

## Input model

- student profile
- target plan
- parsed student documents
- retrieved official evidence
- prior draft state

## Async execution note

- Diagnosis runs now persist their own async job state.
- The diagnosis API remains pollable through the diagnosis run itself, while `/api/v1/jobs/{job_id}` exposes retry and failure details.
- Cached diagnosis responses are scoped to the owning project and the current evidence fingerprint.
- The primary diagnosis UX should surface job status, failure reason, retry affordances, and the citations that support the final diagnosis.

## Explainable scoring

Every score must include:

- contributing factors
- missing evidence
- uncertainty note
- next-best action

## Suggested sub-engines

- `topic_fit`
- `evidence_gap`
- `authenticity_risk`
- `criteria_mapping`
- `next_action_planner`

## Guardrails

- never overrule official sources with lower-rank commentary
- never score confidence without enough retrieval support
- never hide uncertainty when target-plan data is incomplete
