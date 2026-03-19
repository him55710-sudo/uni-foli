# 10 Render And Export

The app should not maintain separate writing logic for every output format.

## One canonical document model

Create and store one structured document model.
All exports should be projections of that model.

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
