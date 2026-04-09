# Uni Foli Research Search Architecture

## Why This Exists
Uni Foli needs grounded admissions guidance with explicit source boundaries.  
Search and reasoning are separate capabilities and must be configured independently.

## Source Layers
- `uploaded_student_record`: uploaded student PDF evidence. This is the only layer allowed to support claims about student actions/achievements.
- `academic_source`: indexed academic results (Semantic Scholar, KCI).
- `official_guideline`: official policy/guideline pages detected from trusted domains (for example `.go.kr`).
- `live_web_source`: general live web results.

## Provider Architecture
- API route `/api/v1/research/papers` delegates to `search_provider_service.search_research_sources(...)`.
- Provider abstraction supports:
  - `semantic`
  - `kci`
  - `both` (merged academic results)
  - `live_web` (general web provider)
- Live web provider is optional. Default configuration keeps it disabled.

## Fallback Rules
- If `live_web` is requested and provider is disabled/missing/failing, backend falls back to Semantic Scholar.
- Response keeps `requested_source=live_web`, marks `fallback_applied=true`, and returns a human-readable `limitation_note`.
- No fake "live web success" state is returned when live web was not actually available.

## Output Metadata Contract
Each search result carries:
- `source_type`
- `source_label`
- `source_provider`
- `freshness_label`
- `retrieved_at`
- result-level `providers_used`
- result-level `source_type_counts`

This metadata is designed to flow into chat/workshop/report grounding so outputs can keep source boundaries visible.

## Capability Decision Note
- Ollama-only local chat can operate in constrained grounded mode.
- Paid cloud LLM can improve reasoning quality and premium UX.
- Live web search requires a separate external search provider/API.
- Therefore, "paid LLM" and "paid live web search" are two different product decisions.
