# 10 Render And Export

The app should not maintain separate writing logic for every output format.

## One canonical document model

Create and store one structured document model.
All exports should be projections of that model.

## Current visual-support slice

The current workshop artifact may persist structured visual blocks alongside markdown:

- `visual_specs` for tables, charts, diagrams, equations, or future external-source visuals
- `math_expressions` as a legacy-compatible equation preview field

Visuals should be planned from section context and grounding evidence. If no strong visual is justified, the artifact should keep no visual support block.

## Export order

### Phase 1

- PDF
- web preview

### Phase 2

- PPTX

### Phase 3

- HWPX

### Avoid

- binary `.hwp` as a required early target
- decorative visuals that do not improve comprehension
- fake quantitative charts derived from unsupported numbers
- hidden provenance for generated or external visuals

## Render service design

Use a separate render service because output generation has different runtime needs.

- queue an export job
- fetch canonical draft
- map to target template
- store artifact
- return signed download link

## PPTX strategy

- use PptxGenJS in `services/render`
- treat slides as layout projections, not separate authoring truth

## HWPX strategy

- support only after the canonical model is stable
- generate from template packages and XML mapping
- keep HWPX as a later compatibility feature, not a blocker
