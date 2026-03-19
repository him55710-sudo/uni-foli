# 09 Drafting And Provenance

This is where `polio` stays useful without becoming a trust-destroying ghostwriter.

## Core rule

A draft block should always know:

- who authored it
- what source evidence supports it
- which revision created it

## Canonical block model

Suggested fields per block:

- block id
- type
- content
- authored by: student, AI, imported
- confidence
- attached evidence ids
- edit history pointer

## Required features

- AI-written vs student-written markers
- per-block revision history
- evidence drawer
- undo and restore
- export-time provenance stripping or inclusion by policy

## Why this matters

If a teacher or student feels the output is "too polished to be real," trust collapses.
The backend should support authenticity-preserving UX by design.

## Drafting flow

1. chat produces outline candidates
2. student selects a direction
3. backend creates draft blocks
4. blocks reference evidence cards
5. student edits
6. diagnosis reruns on changed sections
