# 08 Chat Orchestration

The chat layer is the product surface, but the backend must make it disciplined.

## Model architecture

Use an LLM gateway rather than hardcoding one provider.

- LiteLLM as the gateway
- one fast model for interaction
- optional stronger model for diagnosis or export review

## Tool graph

The model should call backend tools, not improvise facts.

- retrieve source evidence
- inspect student profile
- read parsed document blocks
- request diagnosis
- update draft plan
- queue export

## Answer contract

Every high-value answer should return:

- short guidance
- cited evidence
- student-specific rationale
- next actions

## Prompt design rules

- prompt for questioning and coaching before drafting
- forbid unsupported admissions claims
- require source-backed statements for school-specific advice
- mark uncertainty and freshness explicitly

## Session memory

- long-term memory lives in the database
- volatile reasoning context can live in cache
- never rely on hidden model memory as product state
