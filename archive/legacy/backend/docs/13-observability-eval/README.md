# 13 Observability And Evaluation

The product will fail silently if you cannot inspect retrieval quality, prompt drift, and citation accuracy.

## Observability requirements

- request traces
- retrieval traces
- prompt and model version logging
- export job traces
- latency and failure metrics

## Evaluation requirements

- citation accuracy checks
- source freshness checks
- diagnosis rubric scoring
- hallucination and unsupported-claim review
- document-parsing regression suite

## Storage to keep

- retrieval input and output
- prompt template version
- model identifier
- structured answer schema
- human review verdict when available

## Tooling direction

- Langfuse for traces and eval review
- OpenTelemetry for telemetry plumbing
- database tables for business metrics and audit-safe snapshots

## MVP metrics

- diagnosis completion time
- citation coverage rate
- unsupported-claim rate
- export success rate
- user correction frequency on AI-authored blocks
