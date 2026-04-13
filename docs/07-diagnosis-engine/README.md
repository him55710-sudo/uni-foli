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

Top-level score groups remain fixed and separated:

- `student_evaluation`
- `system_quality`

### Student evaluation dimensions (consultant-grade)

The diagnosis report expands student-side scoring into a multi-dimensional matrix:

- academic rigor
- specificity and concreteness
- inquiry depth
- evidence density
- process reflection quality
- continuity across grades
- major-fit alignment
- originality without overclaim
- authenticity safety
- narrative cohesion
- actionability for next report
- interview explainability

These dimensions are still grounded on the existing backbone axes and evidence bank,
with conservative score clamping when anchor/page thresholds are not met.

### System quality dimensions (separate gate)

System quality is explicitly separated from student evaluation and includes:

- parse coverage
- citation coverage
- evidence uniqueness
- anchor diversity
- page diversity
- section coverage reliability
- contradiction check
- redaction safety
- reanalysis requirement gate
- diagnosis confidence gate

If contradiction checks fail, premium rendering is blocked.
If anchor/page/coverage quality is weak, output is marked provisional/reference-only.

## Trust gates and conservative behavior

The diagnosis engine is intentionally strict:

- important axes require minimum anchor counts
- page diversity minimums are enforced
- required section coverage is checked before confidence claims
- weak evidence triggers score caps and explicit uncertainty messaging
- uncertainty is surfaced, not hidden behind polished language

Every report should clearly differentiate:

- verified findings
- inferred findings
- uncertainty / verification-needed items
- action roadmap

## Report architecture (compatible extension)

Report modes and template IDs stay stable:

- report modes: `compact`, `premium_10p`
- templates: `consultant_diagnosis_compact`, `consultant_diagnosis_premium_10p`

The premium report now follows a richer consultant structure (cover, verdict,
baseline, student/system matrices, strengths/risks, section diagnosis,
major-fit interpretation, recommended/avoid directions, evidence cards,
interview readiness, roadmap, uncertainty, citation appendix) while keeping the
same render pipeline and storage flow.

Compact mode remains concise but includes explicit uncertainty and recommendation
sections for better decision support.

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
