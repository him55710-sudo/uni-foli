# Gemini Conversation Review

This file records how the original Gemini conversation was translated into a realistic backend strategy.

## Core product extracted from the conversation

The conversation consistently points to the same product center:

- upload a student record and existing materials
- understand strengths, gaps, and topic direction
- help the student think, not just auto-generate text
- produce cleaner, more convincing outputs with traceable evidence

That is the part worth building.

## Ideas that were directionally good

- reducing the fragmented workflow across search, writing, layout, and export
- helping students who do not know how to choose a topic
- giving kind, persistent guidance through a mascot layer
- supporting direct editing instead of one-shot AI generation
- grounding advice in real admissions criteria and artifacts

## Ideas that needed correction

### 1. Exact pass prediction

The conversation often drifted into "this will get you admitted" territory.
That should not be a backend promise.

Replace it with:

- fit diagnosis
- topic risk scoring
- evidence coverage scoring
- missing-proof checklist

### 2. Private accepted-student data moat

The conversation treated accepted-student records like an easy training dataset.
That is not a safe day-1 assumption.

Replace it with:

- official university admissions documents
- public and licensable source material
- user-owned uploads
- consented and de-identified contribution flows only after the MVP works

### 3. Build our own deep-learning admissions expert

For a one-person team, model pretraining is not the right problem.

Replace it with:

- model gateway
- retrieval over curated knowledge
- rule-based policy checks
- rubric evaluation
- human review loops for edge cases

### 4. Immediate support for HWP, PPTX, web canvas, and every export format

That is an output explosion.

Replace it with:

- one canonical document representation
- PDF first
- PPTX second
- HWPX third
- binary HWP never as an MVP blocker

### 5. Massive ingestion of blogs, shorts, books, and "tips"

This creates reliability and copyright problems.

Replace it with a ranked source ladder:

1. official university admissions pages and guidebooks
2. official school or ministry guidance
3. user-provided documents
4. curated expert notes with provenance
5. low-trust web content only as weak evidence, never as primary justification

## Backend implications

The backend needs four permanent constraints:

- every answer must be traceable to source records
- every high-risk claim must show confidence and freshness
- every student upload must be privacy-scoped and auditable
- every AI-generated draft must preserve provenance and revision history

## Final backend framing

Build `polio` as:

- a source-grounded topic diagnosis service
- a provenance-aware drafting service
- a student-safe document workflow system

Do not build it as:

- a black-box admissions oracle
- a mass-scraped consultancy clone
- a fully autonomous writer that hides what it changed
