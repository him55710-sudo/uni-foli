# Public Entry And Support

## Why `/` and `/app` are now separated

기존에는 `/`가 보호된 앱 진입점이라 비로그인 사용자가 서비스 소개를 보지 못한 채 바로 `/auth`로 밀려났습니다.  
이번 변경에서는 공개 레이어와 실제 작업 레이어를 분리해, 처음 방문한 사용자도 Uni Folia의 기록 중심 워크플로와 안전 원칙을 먼저 이해한 뒤 앱으로 들어갈 수 있게 했습니다.

- `/`: 공개 랜딩 페이지
- `/app`: 로그인 또는 게스트 시작 이후 사용하는 실제 앱 영역
- `/onboarding`: 보호된 상태에서만 접근 가능한 프로필/목표 설정 플로우

이 구조는 공개 소개, FAQ, 문의, 법률 문서를 안정적으로 노출하면서도 기존 ProtectedRoute 기반 앱 흐름은 유지하기 위한 분리입니다.

## Public pages

현재 공개 레이어는 다음 페이지로 구성됩니다.

- `/`: 랜딩 페이지
  - 핵심 메시지
  - 문제 인식
  - 4단계 작동 방식
  - 실제 기능 소개
  - 차별점
  - 신뢰/안전 원칙
  - FAQ 미리보기
  - 학생용 / 기관용 CTA
- `/faq`: 제품 방향과 운영 상태에 맞춘 FAQ
- `/contact`: 1:1 문의 / 협업·도입 문의 / 버그·기능 제안 허브
- `/auth`: 로그인 및 게스트 시작 진입
- `/terms`, `/privacy`: 공개 법률 페이지

## Inquiry API overview

문의는 더 이상 프론트엔드 `setTimeout` 모의 성공 UI에 의존하지 않습니다.

- Endpoint: `POST /api/v1/inquiries`
- Inquiry types:
  - `one_to_one`
  - `partnership`
  - `bug_report`
- Backend location:
  - route: `backend/services/api/src/polio_api/api/routes/inquiries.py`
  - schema: `backend/services/api/src/polio_api/schemas/inquiry.py`
  - model: `backend/services/api/src/polio_api/db/models/inquiry.py`
  - service: `backend/services/api/src/polio_api/services/inquiry_service.py`

현재 저장 방식은 기존 FastAPI + SQLAlchemy + Pydantic 패턴을 그대로 따릅니다.  
공개 `/contact` 페이지와 authenticated shell 내부의 `B2BPartnershipModal` 모두 같은 엔드포인트를 사용합니다.

## Future expansion

다음 확장은 이 구조를 기준으로 진행할 수 있습니다.

- 문의 접수 후 관리자용 inbox 또는 운영 대시보드 추가
- 이메일 알림, Slack/Webhook 연동
- FAQ를 CMS 또는 JSON 소스 기반으로 분리
- 기관 협업 문의에 대한 후속 단계 상태 관리
- 문의 카테고리별 자동 분류 및 응답 템플릿 연결

현재 단계에서는 먼저 공개 진입 경험과 실제 접수 흐름을 안정적으로 분리하는 데 집중했습니다.
