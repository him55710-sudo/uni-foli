# 14 Delivery Roadmap

This roadmap converts the large product idea into a backend sequence one developer can sustain.

## Phase 0: foundation

- identity and consent
- upload pipeline
- parser integration
- primary database schema
- audit logging

## Phase 1: official-source brain

- source ingestion from official admissions materials
- chunking and vector indexing
- retrieval API
- evidence card model

## Phase 2: diagnosis MVP

- topic fit analysis
- criteria mapping
- evidence gap report
- next-step planner

## Phase 3: chat and draft loop

- chat orchestration
- provenance-aware draft blocks
- revision history
- student-vs-AI authored markers

## Phase 4: export and workflow

- PDF export
- async jobs
- in-app reminders
- review dashboard

## Phase 5: expansion

- PPTX export
- HWPX support
- stronger personalization
- consented benchmark datasets

## Freeze rules

Do not start the next phase until:

- current phase has logs
- current phase has tests
- current phase has a failure-handling path
