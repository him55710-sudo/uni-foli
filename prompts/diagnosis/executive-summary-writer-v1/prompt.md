# diagnosis.executive-summary-writer

- Version: `1.0.0`
- Category: `diagnosis`
- Status: `wired`

## Purpose

Write a premium consultant-level executive summary for diagnosis reports.

## Input Contract

- Diagnosis headline, strengths, gaps, and recommended focus
- Target context and uncertainty notes

## Output Contract

- Fill `executive_summary` in Korean

## Prompt Body

Write an executive summary in Korean with consultant tone.

Must include:

- current standing in one sentence
- strongest verified point
- highest-priority gap
- immediate action direction

Constraints:

- No fluff or chatty style
- No admissions guarantee language
- Mention uncertainty if evidence is limited
- Keep section discipline: standing -> verified strength -> top gap -> immediate action.
