# Public Entry And Benchmarking

## Why `/` and `/app` are separated

Uni Folia는 공개 소개 레이어와 실제 작업 레이어의 역할이 다릅니다.

- `/`는 처음 방문한 사용자가 제품 철학과 작동 방식을 이해하는 곳입니다.
- `/app`은 로그인 또는 게스트 시작 이후 실제로 기록을 올리고, 진단을 보고, 작업실에서 이어가는 곳입니다.
- `/onboarding`은 보호된 상태에서 목표와 방향을 먼저 정리하는 흐름입니다.

이 분리는 두 가지 이유에서 필요했습니다.

1. 비로그인 사용자가 서비스 소개 없이 바로 로그인으로 밀려나지 않게 하기 위해
2. Uni Folia가 generic AI chatbot이 아니라 기록 기반 실행 플랫폼이라는 점을 공개 단계에서 먼저 분명히 보여주기 위해

## Benchmark patterns we intentionally absorbed

경쟁/참고 사이트를 그대로 복제하지 않고, 아래 패턴만 구조 차원에서 흡수했습니다.

- 단계형 랜딩 구조
  - 기능을 병렬로 나열하기보다 `시작 → 이해 → 실행` 순서로 읽히게 만드는 패턴
- 1차 CTA + 2차 설명 CTA
  - 바로 시작하는 버튼과, 먼저 이해하는 버튼을 함께 두는 패턴
- 공개 FAQ의 전면 배치
  - 데이터 처리, 기록 부족, 신뢰성, 결제 준비 상태 같은 실제 질문을 먼저 답하는 방식
- 지원 허브의 명시적 분리
  - 1:1 문의, 협업/도입 문의, 버그·기능 제안을 같은 화면 안에서 분기하는 구조
- 학생용과 기관용 CTA의 분리
  - 학생 지원 흐름과 학교/학원 협업 흐름을 같은 버튼으로 섞지 않는 패턴

## Patterns we intentionally did not adopt

다음 패턴은 경쟁사에서 자주 보였지만 Uni Folia 철학과 맞지 않아 반영하지 않았습니다.

- 합격 보장처럼 읽히는 표현
- 과도한 합격 예측 정확도 전면 노출
- 기록과 무관한 생성 결과를 빠르게 약속하는 표현
- 불안을 키운 뒤 상담이나 구매로 밀어 넣는 퍼널
- 기능을 너무 많이 한 화면에 펼쳐 복잡도를 높이는 메뉴 구조

## Uni Folia differentiation

Uni Folia는 다음 차이를 공개 페이지와 앱 내부에서 모두 반복해서 보여줍니다.

- 기록 기반
  - 학생 기록과 실제 맥락을 먼저 읽고 시작합니다.
- 근거 기반
  - 기록과 연결되지 않는 문장을 무리하게 만들지 않습니다.
- 다음 행동 제안
  - 결과 한 번으로 끝나지 않고, 탐구 플랜과 실행 흐름으로 이어집니다.
- 안전한 생성
  - 근거가 부족하면 추측하지 않고 보완 행동을 먼저 안내합니다.

핵심 문장:

> Uni Folia는 화려한 결과를 과장하는 입시 AI가 아니라, 학생 기록을 바탕으로 다음 안전한 행동까지 설계하는 실행형 플랫폼입니다.

## Inquiry API overview

문의 처리는 더 이상 프론트엔드 `setTimeout` 모의 성공에 의존하지 않습니다.

- Endpoint: `POST /api/v1/inquiries`
- Inquiry types:
  - `one_to_one`
  - `partnership`
  - `bug_report`
- Shared fields:
  - `name`
  - `email`
  - `phone`
  - `subject`
  - `message`
  - `source_path`
  - `metadata`
- Type-specific fields:
  - one-to-one: `inquiry_category`
  - partnership: `institution_name`, `institution_type`
  - bug report: `inquiry_category`, `context_location`

Backend locations:

- route: `backend/services/api/src/polio_api/api/routes/inquiries.py`
- schema: `backend/services/api/src/polio_api/schemas/inquiry.py`
- model: `backend/services/api/src/polio_api/db/models/inquiry.py`
- service: `backend/services/api/src/polio_api/services/inquiry_service.py`

현재 `/contact`와 authenticated shell 내부 `B2BPartnershipModal`은 같은 API를 사용합니다.

## Future extensions

다음 단계에서는 이 구조를 확장할 수 있습니다.

- 문의 접수 후 운영자 inbox 또는 admin dashboard 추가
- 이메일, Slack, webhook 알림 연결
- FAQ JSON/CMS 관리
- 기관용 전용 public page와 도입 FAQ 분리
- 문의 유형별 응답 SLA와 상태 추적 추가
