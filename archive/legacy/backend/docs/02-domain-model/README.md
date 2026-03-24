# 02 Domain Model

This is the minimum domain model needed for a coherent backend.

## Primary entities

- `User`
- `GuardianConsent`
- `StudentProfile`
- `TargetPlan`
- `UploadAsset`
- `ParsedDocument`
- `SourceDocument`
- `SourceChunk`
- `EvidenceCard`
- `TopicCandidate`
- `DiagnosisReport`
- `ChatSession`
- `DraftDocument`
- `DraftRevision`
- `ExportJob`
- `NotificationTask`
- `AuditEvent`

## Entity notes

### User

- login identity
- display name
- optional preferred name
- role: student, guardian, counselor, admin

### StudentProfile

- school year
- interests
- strengths and weaknesses
- optional target programs

### TargetPlan

- university
- major
- admission track
- cycle year

### UploadAsset

- raw file pointer
- uploader
- retention policy
- content type
- processing status

### ParsedDocument

- normalized text
- structural blocks
- extracted entities
- parser confidence

### SourceDocument and SourceChunk

- provenance fields
- source rank
- publication date
- crawl date
- license or usage notes

### DraftDocument and DraftRevision

- canonical structured document
- authored-by marker per block
- source references per block
- revision reason

## State transitions

- upload: received -> scanned -> parsed -> verified -> attached
- source: discovered -> normalized -> chunked -> embedded -> indexed
- diagnosis: queued -> generated -> reviewed -> delivered
- export: requested -> rendering -> stored -> delivered -> expired

## Design rule

Every user-visible answer should be reproducible from stored inputs, prompts, retrieval context, and model output logs.
