# Polio gstack Playbook

## 문서 목적

Polio는 학생 대상 AI 제품이다. 이 제품은 public landing, authenticated app, backend trust boundary가 함께 움직이고, 안전성·신뢰성·QA가 제품 품질의 핵심이다.

이 문서는 gstack을 단순한 스킬 모음이 아니라, 이 repo에서 반복적으로 사용하는 **기획 → 구현 → 리뷰 → QA → 배포 → 회고 운영 루프**로 고정하기 위한 day-to-day 플레이북이다.

기본 규칙:

- 대부분의 기능은 이 문서의 순서를 따른다.
- 작은 예외는 허용하지만, 예외를 택하면 brief나 PR에 이유를 남긴다.
- 구현은 항상 canonical path 기준으로 진행한다.
- public/app 경계, grounded drafting, support flow, backend validation은 항상 높은 우선순위로 본다.

## 언제 이 문서를 기준으로 삼는가

다음 작업은 기본적으로 이 플레이북을 따른다.

- public landing 개편
- FAQ / contact / partnership 흐름 추가 또는 수정
- dashboard / onboarding / record / diagnosis / workshop UX 개선
- backend API / auth / inquiry / provenance / render / research 변경
- competitor analysis 반영 작업
- safety / trust / QA 민감 변경

반대로 아주 작은 오탈자 수정이나 문장 1~2줄 교체 정도는 전체 루프를 다 돌리지 않아도 되지만, 그 경우에도 guardrail 위반 여부는 확인한다.

## 역할별 스킬 매핑

| 역할 | 주력 스킬 | 이 repo에서 맡는 판단 |
| --- | --- | --- |
| Product discovery / PM | `/office-hours`, `/plan-ceo-review` | 이 기능이 실제로 학생 준비를 더 낫게 만드는지, 불안을 줄이는지 |
| UX / design owner | `/plan-design-review` | public/app 흐름, CTA, 정보구조, empty/error state, visual hierarchy |
| Eng / backend / architecture owner | `/plan-eng-review` | auth, contracts, persistence, provenance, failure mode, test surface |
| Reviewer | `/review`, `/codex` | diff quality, trust boundary, risky regression, 2차 독립 검증 |
| QA owner | `/qa`, `/qa-only` | 실제 흐름 검증, 브라우저 QA, repro, fix 필요 여부 |
| Release owner | `/ship`, `/land-and-deploy` | PR 준비, merge, deploy, canary/health 확인 |
| EM / retrospective owner | `/retro` | shipped outcome, misses, next checklist 정리 |

## 신규 기능 시작 플레이북

### 기본 순서

1. 기능 brief 작성: `docs/plans/<date>-<slug>.md`
2. `/office-hours`
3. `/plan-ceo-review`
4. `/plan-design-review` if 다음 중 하나라도 해당:
   - public page
   - dashboard / onboarding / app UX
   - FAQ / contact / conversion
   - copy / IA / empty state / step flow
5. `/plan-eng-review` if 다음 중 하나라도 해당:
   - backend / auth / API
   - shared contract
   - upload / provenance / diagnosis / render
   - inquiry / permission / storage / rate limit
6. 구현 시작

### skip 규칙

- pure backend / internal API면 `/plan-design-review` 생략 가능
- pure copy / polish only면 `/plan-eng-review` 생략 가능
- mixed feature면 기본 순서를 유지하고 `design -> eng` 순서로 본다

### brief에 반드시 들어갈 것

- 사용자 문제
- 성공 기준
- public 영향인지 app 영향인지
- backend/API 변경 유무
- QA 대상 경로
- 관련 canonical docs

## 구현 단계 운영 규칙

### 구현 전에 확인할 것

- brief가 존재하는가
- public vs app 경계가 분명한가
- 관련 canonical docs를 읽었는가
- 테스트 대상과 QA 대상 경로를 정했는가
- `packages/shared-contracts/`가 필요한지 판단했는가

### 에이전트가 건드리면 안 되는 것

- `archive/legacy/`
- guardrail을 깨는 카피
- 근거 없는 admissions / 합격 뉘앙스
- unrelated diff revert
- production secret / local env 임의 변경
- 계획에 없는 schema / migration / codegen

### 기능 브랜치 원칙

- 한 브랜치 = 한 사용자 문제
- branch naming 예시:
  - `feat/public-contact-hub`
  - `feat/faq-refresh`
  - `fix/inquiry-validation`
- brief 파일 경로를 PR 본문과 연결한다
- 대규모 mixed scope는 `public / app / backend`를 한 브랜치에 한꺼번에 다 싣지 말고, 실제로 분리 가능하면 쪼갠다

## 리뷰 단계 플레이북

### `/review`를 쓰는 때

- 모든 non-trivial 기능의 기본 리뷰 게이트
- PR 생성 전
- merge 직전 마지막 구조 확인이 필요할 때

### `/codex`를 추가로 쓰는 때

- auth / ownership / protected route
- inquiry / persistence / validation
- diagnosis / provenance / grounded drafting
- public-to-app conversion boundary
- `/review` 결과가 애매하거나 risk가 큰 경우

### 리뷰 우선순위

1. safety / fabricated output risk
2. auth / owner-scoping / permission
3. provenance / evidence boundary
4. public/app route regression
5. broken inquiry / support / onboarding flow
6. data/privacy leak
7. cosmetic issues

## QA 단계 플레이북

### `/qa` vs `/qa-only`

- `/qa`
  - test + fix + re-verify가 필요할 때
  - ship-ready 상태를 만들고 싶을 때
- `/qa-only`
  - staging / preview에서 리포트만 필요할 때
  - fix authority가 아직 없을 때
  - implementation team에 넘길 repro pack이 필요할 때

### staging 기준 기본 점검 흐름

Public:

- `<staging-base-url>/`
- `<staging-base-url>/faq`
- `<staging-base-url>/contact`
- `<staging-base-url>/contact?type=partnership`
- `<staging-base-url>/auth`
- `<staging-base-url>/terms`
- `<staging-base-url>/privacy`

Authenticated:

- `<staging-base-url>/onboarding`
- `<staging-base-url>/app`
- `<staging-base-url>/app/record`
- `<staging-base-url>/app/diagnosis`
- `<staging-base-url>/app/workshop`
- `<staging-base-url>/app/archive`
- `<staging-base-url>/app/trends`
- `<staging-base-url>/app/settings`

프로젝트별 workshop detail이 있으면 `/app/workshop/:projectId`도 추가 확인한다.

### 각 흐름에서 반드시 확인할 것

- next action이 명확한가
- public → auth → app handoff가 자연스러운가
- empty / error / degraded state가 안전하게 안내되는가
- copy가 overpromise 하지 않는가
- inquiry / partnership entry가 살아 있는가
- backend-connected form이 성공 / 실패를 정직하게 보여주는가

## 배포 단계 플레이북

### `/ship` 사용 조건

- 구현 완료
- 핵심 build / test 완료
- `/review` 완료
- 필요한 경우 `/qa` 또는 `/qa-only` 결과 확보
- PR 생성 / changelog / release summary 정리가 필요할 때

기본 규칙:

- PR 만들기 전까지는 `/ship`
- 실제 배포 대상이나 플랫폼이 불명확하면 `/ship`에서 멈춘다

### `/land-and-deploy` 사용 조건

- 운영 반영 승인 완료
- PR merge 권한 / 절차 준비 완료
- 실제 deploy 및 canary / health 확인이 가능한 환경일 때만
- live merge + deploy + post-deploy verification이 목적일 때만

기본 규칙:

- 운영 반영 직전부터는 `/land-and-deploy`
- 모든 merge 기본값이 아니라 운영 반영 전용이다

## 회고 단계 플레이북

- `/retro`는 큰 기능 landing 후 또는 sprint 종료 후 사용
- 입력 자료:
  - feature brief
  - review findings
  - QA defects
  - shipped PR or deploy result
- 출력은 `docs/reports/<date>-<slug>-retro.md` 형태를 권장한다

회고 질문:

- 불안을 줄였는가
- next safe action이 더 선명해졌는가
- grounded drafting이 유지됐는가
- QA가 실제 문제를 잡았는가
- 다음부터 기본 체크리스트로 올릴 항목은 무엇인가

## 기능 유형별 권장 루틴 표

| 작업 유형 | 필수 스킬 순서 | 조건부 스킬 | QA 대상 | 배포 게이트 |
| --- | --- | --- | --- | --- |
| 랜딩 페이지 개편 | `/office-hours` → `/plan-ceo-review` → `/plan-design-review` → 구현 → `/review` → `/qa` → `/ship` | backend CTA나 form 연동이 생기면 `/plan-eng-review` 추가 | `/`, `/faq`, `/contact`, `/auth` | PR 준비는 `/ship`, 운영 반영 시 `/land-and-deploy` |
| 문의 폼 / FAQ 추가 | `/office-hours` → `/plan-ceo-review` → `/plan-design-review` → 구현 → `/review` → `/qa` | API / persistence가 있으면 `/plan-eng-review` 추가 | `/faq`, `/contact`, `/contact?type=partnership`, `/auth` | PR 준비는 `/ship`, 운영 반영 시 `/land-and-deploy` |
| backend API 추가 | brief → `/office-hours` → `/plan-eng-review` → 구현 → `/review` | user-facing impact가 있으면 `/plan-ceo-review`, UI가 붙으면 `/plan-design-review` | staging API consumer flow, 필요한 경우 `/qa-only` 또는 `/qa` | PR 준비는 `/ship`, 운영 반영 시 `/land-and-deploy` |
| 경쟁사 분석 반영 | `/office-hours` → `/plan-ceo-review` → `/plan-design-review` → 구현 → `/review` → `/qa` | backend / auth / inquiry 영향이 있으면 `/plan-eng-review` | public landing, FAQ, contact, auth handoff | PR 준비는 `/ship`, 운영 반영 시 `/land-and-deploy` |
| 디자인 개선 | `/office-hours` → `/plan-design-review` → 구현 → `/review` → `/qa` | backend state / data dependency가 바뀌면 `/plan-eng-review` | 해당 page flow + empty/error state | PR 준비는 `/ship`, 운영 반영 시 `/land-and-deploy` |

## 짧은 실행 예시 3개

### 예시 1. public landing hero / FAQ preview 개편

1. `docs/plans/2026-03-30-public-hero-refresh.md`에 brief 작성
2. `/office-hours`로 message, CTA, next action 방향 정리
3. `/plan-ceo-review`로 경쟁사 대비 차별 메시지 검증
4. `/plan-design-review`로 hero, FAQ preview, CTA hierarchy 검토
5. `frontend/src/pages/Landing.tsx`, `frontend/src/pages/Faq.tsx`, 관련 docs를 보고 구현
6. `/review`로 public/app 경계와 overpromise copy 점검
7. `/qa`로 `/`, `/faq`, `/auth` handoff 검증
8. `/ship`으로 PR 준비

### 예시 2. `/contact` + `POST /api/v1/inquiries` 개선

1. `docs/plans/2026-03-30-inquiry-flow-hardening.md`에 brief 작성
2. `/office-hours`로 user support flow와 expected response states 정리
3. `/plan-ceo-review`로 support hub가 실제 user trust를 높이는지 검토
4. `/plan-design-review`로 `/contact`, partnership CTA, error/success toast UX 검토
5. `/plan-eng-review`로 route, schema, validation, persistence, rate limit 범위 고정
6. `frontend/src/pages/Contact.tsx`, `backend/services/api/src/polio_api/api/routes/inquiries.py`, `docs/public-entry-and-support.md`를 보고 구현
7. `/review`로 validation, auth boundary, support regression 확인
8. `/qa`로 `/contact`, `/contact?type=partnership`, modal entry, 실패 케이스 검증 후 `/ship`

### 예시 3. diagnosis 결과에서 workshop 다음 행동 연결 개선

1. `docs/plans/2026-03-30-diagnosis-to-workshop-handoff.md`에 brief 작성
2. `/office-hours`로 “next safe action”이 실제로 무엇인지 정리
3. `/plan-ceo-review`로 이 변경이 학생 불안을 줄이는지 검토
4. `/plan-design-review`로 diagnosis 화면의 CTA, empty state, step flow 검토
5. `/plan-eng-review`로 diagnosis output contract나 workshop handoff state 변경 여부 확인
6. `docs/07-diagnosis-engine/README.md`, `docs/08-chat-orchestration/README.md`, `docs/09-drafting-provenance/README.md`를 보고 구현
7. `/review`로 grounded drafting / provenance boundary 점검
8. `/qa`로 `/app/diagnosis` → `/app/workshop` 흐름 검증 후 `/ship`

## 운영 메모

- 설치 / refresh / doctor 중심 정보는 `docs/ai-dev-workflow.md`를 본다.
- day-to-day 실행 순서와 gate 판단은 이 문서를 우선 기준으로 삼는다.
