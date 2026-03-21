# Polio Backend CTO Assessment

> CTO 시각에서 정리한 Polio admissions intelligence backend 상태 문서
> 기준일: 2026-03-21
> 평가 기준: 현재 레포지토리, 구현된 코드, 로컬 검증 결과

이 문서는 현재 구성된 Polio 백엔드가 어떤 구조를 가지고 있는지, 무엇이 이미 구현되어 있는지, 어떤 오픈소스를 쓰고 있는지, 어디까지가 자동화 가능하고 어디부터는 사람이 직접 해야 하는지, 그리고 현재 상태를 얼마나 냉정하게 평가해야 하는지를 정리한 운영용 문서다.

이 문서의 목적은 두 가지다.

- 창업자와 미래 팀이 같은 현실을 보도록 만드는 것
- 향후 30일, 60일, 90일 실행계획의 기준 문서가 되는 것

현재 Polio 백엔드는 단순한 챗봇 골격이 아니라, 공식 입시 자료를 수집하고 문서를 파싱하고 chunk와 claim을 저장하고 학생 업로드 파일을 분석 가능한 단위로 전환하는 admissions-aware backend foundation으로 설계되어 있다.

동시에 아직 production-ready는 아니다. 실제 crawler, 강한 retrieval, privacy baseline, 운영형 queue, admissions expert review workflow, 평가셋, current cycle 공식 corpus가 붙어야 비로소 서비스로 개방할 수 있다.

### 문서 한 줄 결론

> 설계 방향은 매우 좋다.
> 작동하는 vertical slice도 있다.
> 그러나 지금은 "강한 기반을 가진 초기 백엔드"이지 "바로 대규모 운영 가능한 백엔드"는 아니다.

### 현재 상태 스냅샷

- 아키텍처 방향성: 좋음
- 도메인 적합성: 높음
- provenance 설계: 강점
- 공식 출처 중심 구조: 강점
- ingestion vertical slice: 동작함
- retrieval 품질: 아직 초기
- auth/privacy/ops: 아직 미흡
- product differentiation potential: 높음

---

## 1. Executive Summary

Polio 백엔드의 핵심 철학은 분명하다. 이 시스템은 학생에게 허위 기록을 만들어주거나 보기 좋은 문장을 대신 꾸며주는 도구가 아니라, 공식 평가 기준이 실제 학생 활동과 학생부 기록을 어떻게 해석하는지를 근거 중심으로 설명하는 admissions intelligence system이 되려 한다.

이 철학은 현재 코드 구조에도 반영되어 있다. 데이터 모델만 봐도 Source, Document, DocumentVersion, ParsedBlock, DocumentChunk, Claim, ClaimEvidence, RetrievalIndexRecord, StudentFile, StudentArtifact, StudentAnalysisRun, ResponseTrace, Citation, PolicyFlag, ReviewTask가 이미 존재한다. 이것은 "대답을 잘하는 앱"보다 "기록과 근거를 관리하는 시스템"을 먼저 만들고 있다는 뜻이다.

이 점은 Polio가 흔한 AI 포트폴리오 생성기와 갈라지는 지점이다.

현재 usable한 기능도 분명히 있다.

- source 생성
- source 파일 업로드
- ingestion job 생성 및 실행
- parsed document 생성
- parsed block와 document chunk 저장
- chunk 기반 claim extraction interface
- claim와 evidence persistence
- retrieval API
- student file upload와 artifact persistence
- admin inspection API

로컬 검증도 있다.

- pytest 11 passed
- ingestion vertical slice 테스트 존재
- alembic upgrade head 성공

하지만 이 문서는 장점만 말하지 않는다. 실제로 지금 시점의 가장 큰 기술적 과제는 아래와 같다.

- 진짜 공식 source crawler 부재
- 진짜 hybrid retrieval 부재
- 운영형 worker/queue 부재
- auth와 tenancy 부재
- privacy pipeline 미완성
- admissions-domain evaluation set 부재
- Korean heuristic keyword 일부 인코딩 깨짐
- legacy scaffold와 new root app의 이중 구조

현재 단계의 CTO 평가는 다음과 같다.

- "버릴 필요 없는 구조"다
- "바로 공개하면 안 되는 상태"다
- "정확한 데이터와 사람 검수 체계를 붙이면 경쟁력이 커지는 구조"다

---

## 2. 현재 백엔드 구조

현재 admissions 코어는 root 기준 아래 구조에 있다.

```text
app/
  api/routes/
  schemas/
  core/
db/
  models/
parsers/
services/admissions/
workers/
alembic/
docs/
prompts/
```

이 구조는 일반적인 FastAPI 프로젝트보다 조금 더 명확한 장점이 있다.

- API 라우터는 얇게 유지된다
- 도메인 로직은 admissions 서비스에 들어간다
- 파서는 별도 계층으로 분리된다
- DB 모델은 admissions entity 중심으로 구성된다
- 추후 worker, retrieval, review를 확장하기 좋다

### 레이어별 역할

#### API Layer

FastAPI가 외부 진입점이다. 현재 source, ingestion, documents, claims, retrieval, student-files, analysis-runs, admin review 관련 API가 존재한다.

이 레이어의 장점은 route handler가 상대적으로 얇고, 핵심 로직을 service layer로 넘기려는 의도가 분명하다는 점이다.

#### Service Layer

`services/admissions/` 아래에 source, ingestion, document, claim, retrieval, student-file, review, safety, provenance, student-analysis 관련 서비스가 분리되어 있다.

이것은 매우 좋은 판단이다. 입시 서비스는 이후 규칙이 계속 늘어나기 때문에 로직이 route에 박히면 유지보수가 급격히 어려워진다.

#### Parser Layer

현재 parser abstraction이 존재한다. functional 수준 구현은 PDF, HTML, plain text이고, HWPX는 basic zip/xml parser 수준, OCR fallback은 stub에 가깝다.

즉, parser framework 자체는 맞게 가고 있지만 실제 문서 품질을 책임질 정도의 parsing sophistication은 아직 더 필요하다.

#### Persistence Layer

SQLAlchemy + Alembic 기반으로 구성되어 있고, 실질적인 domain schema는 꽤 잘 잡혀 있다. 단순 upload table 몇 개가 아니라, provenance와 audit을 고려한 구조라는 점이 중요하다.

#### Worker Layer

worker entry와 task 모듈이 존재하지만, 현재는 운영형 queue consumer라기보다는 sequential runner에 가깝다. 즉, 개념과 구조는 있고 실제 운영 수준 async orchestration은 아직 남아 있다.

#### Safety / Audit Layer

PolicyFlag, ReviewTask, ResponseTrace, Citation이 데이터 모델과 서비스 계층에 들어와 있다. 이것은 Polio가 제품 철학을 backend에 반영하고 있다는 강력한 신호다.

### 현재 주 흐름

```text
Official Source File
  -> FileObject
  -> IngestionJob
  -> Document
  -> DocumentVersion
  -> ParsedBlock
  -> DocumentChunk
  -> Claim
  -> ClaimEvidence
  -> RetrievalIndexRecord

Student Upload
  -> FileObject
  -> StudentFile
  -> StudentArtifact
  -> StudentAnalysisRun
  -> ResponseTrace / Citation / PolicyFlag
```

이 흐름은 현재 Polio 백엔드의 가장 큰 장점이다. 많은 AI 서비스는 문서를 넣고 결과만 뱉는다. 그런데 Polio는 intermediate object를 거의 다 저장한다. 이것은 미래 확장성과 운영 신뢰성을 크게 높인다.

---

## 3. 현재 구현된 기능과 실제 동작 범위

현재 구현 범위는 "설계만 완료" 수준이 아니다. 실제 동작하는 기능이 있다.

### 이미 동작하는 기능

- source creation / listing
- source file upload
- ingestion job creation / listing / execution
- parsed document persistence
- block persistence
- deterministic chunk generation
- chunk 기반 claim extraction request
- claim persistence
- claim evidence persistence
- retrieval search endpoint
- student file upload
- student artifact persistence
- analysis run persistence
- admin inspection routes

### 현재 노출된 주요 API

- `GET /api/v1/health`
- `GET /api/v1/ready`
- `POST /api/v1/sources`
- `GET /api/v1/sources`
- `POST /api/v1/sources/{id}/files`
- `POST /api/v1/ingestion/jobs`
- `GET /api/v1/ingestion/jobs`
- `POST /api/v1/ingestion/jobs/{id}/run`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{id}`
- `GET /api/v1/documents/{id}/blocks`
- `GET /api/v1/documents/{id}/chunks`
- `GET /api/v1/documents/{id}/claims`
- `POST /api/v1/claims/extract`
- `POST /api/v1/retrieval/search`
- `POST /api/v1/student-files`
- `GET /api/v1/student-files`
- `POST /api/v1/analysis/runs`
- `GET /api/v1/analysis/runs`
- `GET /api/v1/admin/*`

### 실제로 검증된 vertical slice

현재 테스트 기준으로 다음 흐름은 실제로 검증되어 있다.

- source 생성
- source에 텍스트 파일 업로드
- ingestion job 실행
- document 생성
- chunk 조회
- claim extraction 호출
- claim evidence에 chunk pointer 저장
- retrieval search에서 결과 확인
- admin chunk inspection 확인

이것은 중요하다. 입시 제품에서 "아키텍처 예쁘게 설계함"과 "실제로 ingestion slice가 돈다"는 완전히 다르다. Polio는 이제 후자에 진입했다.

### 아직 부분 구현인 기능

- HWPX parsing은 매우 기초적 수준
- OCR fallback은 production-grade 아님
- true hybrid retrieval 아님
- reranking 없음
- conflict resolution automation 미완성
- stale source penalty 자동화 미완성
- privacy masking runtime 미연결
- admissions-specific eval framework 미완성

---

## 4. 데이터 모델과 provenance 설계

현재 Polio 백엔드의 가장 큰 강점 중 하나는 데이터 모델이다. 일반적인 AI 앱은 request와 response만 저장하고 끝나지만, Polio는 입시 제품에 필요한 운영 객체를 상당히 잘 쪼개어 모델링했다.

### 핵심 엔티티 그룹

#### Source 계열

- `Source`
- `SourceCrawlJob`

의미:

- 어떤 기관의 어떤 base URL을 신뢰 대상으로 볼 것인지
- 그 source가 어떤 tier인지
- 향후 recrawl과 freshness 관리가 가능한지

#### Content 계열

- `FileObject`
- `Document`
- `DocumentVersion`
- `ParsedBlock`
- `DocumentChunk`
- `Claim`
- `ClaimEvidence`
- `ConflictRecord`
- `RetrievalIndexRecord`

의미:

- 문서를 파일 단위로 저장
- 문서 자체는 canonical object로 유지
- 버전 이력 유지
- parse 결과를 block으로 저장
- retrieval과 extraction은 chunk 단위로 처리
- claim은 근거와 함께 별도 저장
- claim conflict를 future-ready하게 모델링

#### Student 계열

- `StudentFile`
- `StudentArtifact`
- `StudentAnalysisRun`

의미:

- 학생이 올린 원본과 분석 가능한 artifact를 분리
- 분석 실행 자체를 별도 run으로 남겨 재현성과 비교 가능성 확보

#### Audit / Review 계열

- `Citation`
- `ResponseTrace`
- `PolicyFlag`
- `ReviewTask`

의미:

- 왜 이런 답이 나왔는지 역추적 가능
- 어떤 안전 플래그가 떴는지 확인 가능
- 사람 검수 업무를 workflow로 관리 가능

### 현재 provenance 체인의 의미

> claim은 document와 document_version에 연결된다.
> claim evidence는 parsed_block과 document_chunk를 동시에 가리킨다.
> response trace와 citation은 나중에 어떤 답변이 어떤 근거를 사용했는지 복원할 수 있게 해준다.

이 구조 덕분에 Polio는 단순히 "답이 맞는가"만 보는 게 아니라 "어떤 공식 자료의 어느 부분을 보고 이런 해석이 나왔는가"까지 보여줄 수 있다.

이건 입시 제품에서 매우 큰 차별점이다.

### 설계적으로 특히 좋은 부분

- `DocumentVersion`이 있어 재수집과 재파싱을 두려워하지 않아도 됨
- `DocumentChunk`가 독립 엔티티라 retrieval와 claim extraction의 operational unit이 명확함
- `ClaimEvidence`에 `document_chunk_id`가 있어 citation 조립이 쉬움
- `PolicyFlag`, `ReviewTask`가 초기에 들어가 있어 나중에 safety를 덧붙이는 구조가 아님

### 앞으로 더 보강해야 하는 부분

- `ConflictRecord`를 실제로 채우는 로직
- freshness scoring update job
- claim supersession logic
- evaluation dimension alias mapping
- university / cycle canonicalization table

---

## 5. 사용 중인 오픈소스와 도입 의도

현재 Polio 백엔드는 오픈소스 선택이 비교적 합리적이다. 무엇보다 "한 명 또는 소수 팀이 운영 가능한 범위"를 크게 벗어나지 않는다.

### 현재 runtime에 직접 연결된 오픈소스

- FastAPI
  - API 서버
  - admissions-specific route surface 제공
- SQLAlchemy
  - ORM과 schema mapping
  - domain model을 명시적으로 유지
- Alembic
  - 마이그레이션 관리
  - schema evolution 기반 마련
- pypdf
  - PDF parsing의 첫 functional parser
- reportlab
  - PDF 생성
  - export와 문서화에 실용적
- python-pptx
  - PPTX export runtime 기반
- pydantic / pydantic-settings
  - DTO와 config 관리
- uvicorn
  - API server runtime
- python-multipart
  - file upload 처리
- psycopg / pgvector
  - intended production PostgreSQL path

### 인프라용 오픈소스 / 컨테이너

- PostgreSQL
- pgvector image
- Redis
- MinIO

### 이미 확보했지만 아직 본격 런타임에 연결하지 않은 오픈소스

- Docling
  - advanced parsing 후보
- Presidio
  - PII masking과 privacy pipeline용
- LiteLLM
  - model gateway abstraction
- Langfuse
  - trace, prompt, evaluation, model debugging
- Valkey
  - cache / broker 대안
- Citation.js
  - citation formatting reference
- python-hwpx
  - HWPX 생태계 참고용
- PptxGenJS
  - future Node-based rendering option

### CTO 의견

- stack choice는 과하게 무겁지 않다
- PostgreSQL + pgvector를 중심으로 두려는 방향은 MVP에 적절하다
- 다만 currently downloaded reference와 actual runtime integration 사이의 간극이 크다
- 다운로드만 되어 있고 아직 연결되지 않은 오픈소스는 실제 제품 가치가 아니다

즉, "무엇을 깔아두었는가"보다 "무엇이 runtime path에 연결되어 있는가"를 기준으로 계속 판단해야 한다.

---

## 6. 앞으로 더 진행해야 하는 부분

현재 백엔드는 foundation은 좋지만, 서비스화에 필요한 핵심 영역이 아직 남아 있다.

### 최우선 기술 과제

#### 1. 실제 source crawler

현재는 source file을 수동 업로드하면 ingestion이 도는 구조다.

실제로 필요한 것은:

- source seed 등록
- URL discovery
- file download
- idempotent recrawl
- stale refresh schedule
- robots / allowlist / trust policy

이 부분이 붙어야 진짜 official corpus가 자라기 시작한다.

#### 2. true hybrid retrieval

현재 retrieval는 scaffold와 lexical fallback이 있지만, 정말 중요한 수준의 hybrid retrieval은 아직 아니다.

필요한 것:

- metadata filter 강화
- BM25 or lexical index
- pgvector embedding search
- source-tier weighted ranking
- freshness penalty
- conflict penalty
- reranking hook

#### 3. claim extraction hardening

현재 claim extraction은 interface, prompt, schema, persistence가 있다.

하지만 아직 부족하다.

- actual Ollama model quality evaluation
- per-document chunk selection policy
- retry and backoff
- extraction failure analysis
- prompt version governance
- human approval loop

#### 4. privacy and auth baseline

현재 `owner_key` 기반 lightweight separation은 내부 개발 단계에서는 괜찮다.

그러나 실제 학생 데이터를 다루는 순간 반드시 필요하다.

- real authentication
- account and role model
- tenant boundary
- upload access control
- retention and deletion policy
- PII masking and logging controls

#### 5. 운영형 worker

현재 worker는 sequential runner stub에 가깝다.

실서비스 기준으로는 다음이 필요하다.

- real async queue
- retry policy
- dead-letter handling
- failed job visibility
- backpressure
- rate limiting

### 중기 과제

- admin UI
- claim review workflow 정교화
- policy flag triage workflow
- conflict resolution UX
- observability dashboard
- evaluation dataset management
- admissions cycle archive strategy
- prompt and model registry

### 즉시 수정 권고

현재 문서화 차원에서 명확히 짚어야 할 문제도 있다.

- 일부 Korean heuristic string이 인코딩 깨짐 상태를 보임
- legacy scaffold와 root app이 동시에 존재하여 repo 이해 비용이 큼
- Redis / RQ 의존성은 있지만 진짜 queue integration은 아직 얕음
- safety / privacy runtime integration이 제한적임

이건 "나중에 천천히"가 아니라 조기에 손대는 것이 맞다.

---

## 7. AI가 아닌 사람이 직접 작업해줘야 하는 부분

Polio의 경쟁력은 AI 자동화에만 있지 않다. 오히려 이 제품은 사람이 어디에 개입해야 하는지를 정확히 아는 것이 중요하다.

### 반드시 사람이 맡아야 하는 영역

#### 공식 source 큐레이션

사람이 직접 정해야 한다.

- 어떤 대학을 먼저 수집할 것인지
- 어떤 자료가 공식성과 재사용 가치가 높은지
- 어떤 자료는 제외해야 하는지

이것은 crawler가 대신 결정할 수 없다.

#### admissions taxonomy 설계

AI가 멋대로 evaluation dimension taxonomy를 정하면 안 된다.

사람이 직접 해야 한다.

- academic competence
- self-directed growth
- career exploration
- major fit
- community contribution
- evidence quality
- authenticity

이 축의 정의, alias, 예외 규칙은 admissions-domain 지식을 가진 사람이 검토해야 한다.

#### claim review

LLM이 뽑은 claim이 그럴듯해 보여도 그대로 통과시키면 안 된다.

사람이 직접 해야 한다.

- approved / rejected 기준 수립
- evidence quality rubric 작성
- 대학별 예외 판단
- interpretation note와 direct rule 구분

#### 학생 데이터 privacy 검토

학생부는 민감정보다. 사람이 직접 해야 한다.

- retention policy
- 삭제 요청 처리
- masking 기준
- admin access policy
- legal / terms language

#### evaluation dataset 제작

모델 품질은 결국 평가셋으로 관리된다.

사람이 직접 해야 한다.

- 좋은 claim 예시 선정
- 나쁜 claim 예시 선정
- evidence span annotation
- weak evidence zone annotation
- unsafe prompt set 구축

### CTO 의견

> 사람 개입은 이 제품의 약점이 아니라 신뢰성의 원천이다.
> Polio는 human-in-the-loop를 product cost가 아니라 product moat로 봐야 한다.

---

## 8. 필요한 자료와 데이터

지금 코드보다 더 중요한 것은 앞으로 쌓아야 할 데이터 자산이다.

### 반드시 필요한 자료

- 대학별 공식 모집요강
- 대학별 학생부종합전형 안내서
- 대학 admissions FAQ
- 대학 설명회 자료
- 교육부 / 교육청 학생부 가이드
- current cycle admissions metadata
- 대학명 alias / 캠퍼스 / 모집단위 정리표

### 반드시 만들어야 하는 내부 데이터

- document type label set
- source tier classification examples
- evaluation dimension mapping examples
- claim extraction gold set
- evidence span annotation set
- unsafe / deceptive request examples
- stale document detection policy set

### 있으면 매우 좋은 데이터

- 익명화된 학생부 예시
- 익명화된 탐구보고서 예시
- 실제 weak evidence / strong evidence 샘플
- 대학별 표현 차이 정리 자료
- admissions expert review notes

### 현재 상태 평가

- 코드 기반은 있음
- official corpus는 아직 초기
- human-labeled eval set은 사실상 아직 없음
- 대학별 current cycle knowledge base는 앞으로 쌓아야 함

즉, 지금 Polio의 핵심 병목은 모델이 아니라 데이터다.

---

## 9. 현재 백엔드 상태에 대한 객관적 평가

이 섹션은 가장 중요하다. 낙관도 비관도 아닌, 운영 관점에서 냉정하게 본다.

### 항목별 점수

- Architecture foundation: 4/5
- Domain modeling: 4/5
- Provenance and auditability: 4/5
- Ingestion vertical slice: 3/5
- Parser maturity: 2.5/5
- Claim extraction maturity: 2/5
- Retrieval quality: 2/5
- Student analysis quality: 2.5/5
- Admin workflow maturity: 3/5
- Auth / tenancy: 1/5
- Privacy readiness: 1.5/5
- Observability / ops: 2/5
- Production readiness overall: 2/5

### 강점

- 입시 도메인에 맞는 데이터 모델이 이미 존재한다
- provenance와 citation 구조가 초기에 들어가 있다
- 정책 경계가 코드 구조에 반영되어 있다
- vertical slice가 실제로 작동한다
- 오픈소스 선택이 대체로 현실적이다

### 약점

- 진짜 corpus가 아직 없다
- 진짜 hybrid retrieval가 아직 없다
- 사람 검수 workflow가 API 수준에 머물러 있다
- 학생 개인정보 대응 체계가 아직 product-grade가 아니다
- queue, monitoring, alerting이 운영형이 아니다
- 일부 heuristic 한국어 문자열이 깨져 있다
- legacy와 new stack 이중 구조가 있다

### 운영 관점 한 줄 평가

현재 백엔드는 "처음부터 다시 만들 필요는 없는 구조"다.

하지만 "이 상태로 학생들에게 바로 개방하면 안 되는 구조"이기도 하다.

즉, foundation은 strong, production readiness는 early다.

### 가장 시급한 리스크

- 입시 신뢰성을 해칠 수 있는 low-quality claim
- 인코딩 문제로 인해 한국어 heuristic 품질 저하
- auth 부재로 인한 데이터 접근 리스크
- privacy policy 부재
- source freshness 관리 미완성

---

## 10. 타 접근 방식 대비 차별점

이 비교는 특정 회사를 지목한 시장 분석이 아니라, 흔한 제품 접근 방식과 Polio의 구조를 비교한 것이다.

### 1. 일반 AI 챗봇형 입시 서비스와의 차이

일반적인 형태:

- PDF 몇 개 넣고 vector search
- 질문하면 대답
- 왜 그런 답이 나왔는지 추적 어려움

Polio:

- source tier를 고려함
- claim과 evidence를 따로 저장함
- provenance와 citation 구조가 존재함
- stale / low trust / unsafe request를 backend concern으로 봄

### 2. 포트폴리오 / 서사 생성기와의 차이

일반적인 형태:

- 보기 좋은 문장 생성
- narrative polishing에 집중
- 허위 과장 가능성이 높음

Polio:

- fabricated narrative를 목표로 하지 않음
- official criteria interpretation에 집중
- 실제 기록과 근거 중심 분석을 지향

### 3. 컨설팅 CRM류와의 차이

일반적인 형태:

- 학생 관리와 workflow는 좋음
- 문서 이해와 evidence intelligence는 약함

Polio:

- backend 자체가 corpus ingestion + claim extraction + provenance를 중심으로 설계됨

### 차별화의 핵심 문장

> Polio의 진짜 차별점은 "더 화려한 생성"이 아니라
> "더 신뢰 가능한 공식 기준 해석과 근거 관리"에 있다.

이 포지션을 유지하면 generic AI 툴과는 다른 category를 만들 수 있다.

---

## 11. 앞으로의 실행 계획

### 0-30일

- 공식 source seed 정리
- crawler 설계 시작
- normalization alias 테이블 구축
- Korean heuristic cleanup
- root app 기준으로 canonical path 정리

목표:

- official corpus를 실제로 키우기 시작

### 31-60일

- retrieval quality 개선
- claim review workflow 강화
- auth 초안
- privacy baseline
- failed job visibility

목표:

- 내부 alpha 운영 가능 상태

### 61-90일

- admissions-domain eval dataset
- human review SOP
- admin UI 초안
- observability 붙이기
- current cycle freshness 운영

목표:

- 신뢰 가능한 beta 준비

### CTO 최종 권고

지금은 새로운 기능을 무한히 늘릴 시점이 아니다.

우선순위는 아래 순서가 맞다.

- 데이터
- review
- privacy
- retrieval 품질
- 운영성

이 순서를 지키면 Polio는 단순한 AI 작성기가 아니라, 한국 입시형 고신뢰 백엔드로 발전할 수 있다.

---

## Appendix A. 현재 구현 기준 검증 사실

- FastAPI admissions app 존재
- source registration 구현
- source file upload 구현
- ingestion job 실행 구현
- document / chunk persistence 구현
- claim extraction interface 구현
- retrieval endpoint 구현
- student file upload 구현
- admin inspection route 구현
- pytest 11 passed
- alembic upgrade head passed

## Appendix B. 현재 즉시 수정이 필요한 기술 메모

- safety_service와 student_analysis_service 내 한국어 heuristic 문자열 재정비
- legacy scaffold 정리 여부 결정
- auth path 설계 시작
- privacy / retention 문서 초안 작성
- current cycle source acquisition 우선순위 수립
