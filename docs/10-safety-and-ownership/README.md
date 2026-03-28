# Safety & Ownership: Ghostwriting Prevention

UNI FOLIA is designed to be an **academic mentor**, not a ghostwriter. We implement a multi-layered safety architecture to ensure that every word generated is grounded in the student's actual evidence and inquiry process.

## 1. Grounding-First Generation
The generation prompt strictly limits the AI's output to the contexts provided in the Workshop:
- **Workshop Turns**: Direct inputs and choices made by the student.
- **Pinned References**: Academic materials selected and understood by the student.
- **RAG Context**: Verified academic papers connected to the student's inquiry.

## 2. Ghostwriting Detection (Safety Guard)
Our `safety_guard` module monitors the **Input Grounding Ratio**.
- **Expansion Ratio**: We calculate the ratio between input characters (student/reference) and output characters.
- **Threshold**: If the AI expands the input by more than **8x** (for reports > 400 chars), the `GHOSTWRITING_RISK` flag is triggered.
- **Enforcement**: High expansion ratios significantly lower the `Safety Score` and may trigger an automatic **quality level downgrade** (e.g., from High to Low) to ensure a more conservative, safe draft.

## 3. Authorship Markers
Every part of the generated draft is explicitly tagged:
- **AI Suggested**: Clearly marked with UI labels and distinct borders.
- **Review Required**: Changes must be manually approved (`SuggestionReviewModal`) before being "applied" to the main draft.

## 4. Evidence Mapping
The `evidence_map` metadata links every claim in the generated AI report back to specific `turn_id` or `reference_id`. This transparency ensures that students (and teachers) can audit the source of every statement.
