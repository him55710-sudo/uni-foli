# 00 Principles

These rules are meant to constrain all future backend decisions.

## Product truth

`polio` helps students plan and refine admissions-relevant work.
It does not guarantee admission.

## Required behavior

- Always show what came from source evidence.
- Always distinguish AI inference from quoted or extracted facts.
- Always preserve the student's authorship trail.
- Always prefer user-owned and official documents over scraped web opinion.

## Required backend properties

- traceability
- reversibility
- privacy scoping
- source freshness awareness
- graceful uncertainty

## Scoring principles

Every score shown to the user must have:

- a definition
- input factors
- confidence or completeness caveat
- next actions

Never show a mysterious "AI score" with no explanation.

## Safety principles

- Do not output fabricated university-specific policies.
- Do not infer personal attributes that are not necessary to the task.
- Do not retain raw student records longer than needed for the feature.
- Do not treat copyrighted commercial material as a reusable training corpus.

## Engineering principles

- keep the first version monolithic at the deployment boundary
- split into services only where runtime needs are clearly different
- keep data ownership explicit for every storage system
- version prompts, rubrics, and scoring policies like code
