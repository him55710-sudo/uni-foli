# 01 Product Boundary

This section defines what the backend is responsible for.

## User-facing backend outcomes

- ingest student-owned materials
- understand target school and major context
- diagnose topic quality and evidence gaps
- run guided chat with structured tool use
- maintain a traceable draft state
- export final artifacts

## Non-goals for the backend

- exact admission prediction
- psychographic manipulation
- unauthorized collection of third-party student records
- silent rewriting that hides AI involvement

## MVP contract

The first backend release should answer:

1. What is the student trying to submit?
2. What official criteria or source signals are relevant?
3. What is missing, weak, or unsupported?
4. What should the student do next?

## Core bounded contexts

- identity and consent
- student record ingestion
- source knowledge ingestion
- diagnosis
- chat orchestration
- drafting and provenance
- rendering and delivery

## Failure modes to guard against

- weak sources overpower strong sources
- old admissions rules reused as if current
- AI suggestions detached from the user's actual record
- too much automation leading to "AI smell"
