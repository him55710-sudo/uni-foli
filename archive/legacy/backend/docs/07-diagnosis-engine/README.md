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
