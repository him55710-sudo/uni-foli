from __future__ import annotations

from typing import Any


def _clip(value: str | None, limit: int = 180) -> str:
    normalized = " ".join((value or "").split()).strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."


def _intent_key(message: str) -> str:
    lowered = message.lower()
    if any(token in lowered for token in ("개요", "목차", "outline", "구성")):
        return "outline"
    if any(token in lowered for token in ("도입", "서론", "인트로", "intro", "첫 문단")):
        return "intro"
    if any(token in lowered for token in ("제목", "title")):
        return "title"
    if any(token in lowered for token in ("근거", "증거", "출처", "자료")):
        return "evidence"
    if "?" in message or any(token in lowered for token in ("왜", "어떻게", "무엇", "뭐")):
        return "question"
    return "general"


def _safe_str(summary: dict[str, Any] | None, key: str) -> str | None:
    if not summary:
        return None
    raw = summary.get(key)
    text = _clip(str(raw) if raw is not None else "")
    return text or None


def _safe_list(summary: dict[str, Any] | None, key: str, *, limit: int = 3) -> list[str]:
    if not summary:
        return []
    raw = summary.get(key)
    if not isinstance(raw, list):
        return []
    normalized: list[str] = []
    for item in raw:
        text = _clip(str(item), 140)
        if text:
            normalized.append(text)
        if len(normalized) >= limit:
            break
    return normalized


def _draft_snippet(intent: str, *, topic: str | None, thesis: str | None) -> list[str]:
    topic_label = topic or "현재 선택 주제"
    thesis_label = thesis or "핵심 질문을 한 문장으로 명확히 두고"

    if intent == "outline":
        return [
            f"- 소단락 1: `{topic_label}`의 핵심 맥락을 2~3문장으로 요약",
            f"- 소단락 2: `{thesis_label}`를 기준으로 관찰/해석 근거 연결",
            "- 소단락 3: 결론 문장에서 다음 탐구 행동 1개 제안",
        ]
    if intent == "intro":
        return [
            f"`{topic_label}`를 다루는 이유는 학생의 실제 기록 흐름과 연결되기 때문이다.",
            f"이번 글은 `{thesis_label}`를 중심으로 사례와 근거를 분리해 점검한다.",
            "확정되지 않은 수치나 사실은 (추가 확인 필요)로 표시해 안전하게 유지한다.",
        ]
    if intent == "title":
        base = topic or "탐구 보고서"
        return [
            f"- {base}: 기록 기반 탐구의 핵심 질문 정리",
            f"- {base}: 근거 중심 분석과 다음 실험 제안",
            f"- {base}: 학습 기록 흐름에서 찾은 개선 포인트",
        ]
    if intent == "evidence":
        return [
            "- 지금 문장에서 사실 주장 1개와 해석 주장 1개를 분리",
            "- 사실 주장 옆에 출처(활동명/문서명/페이지)를 짧게 표시",
            "- 출처가 비어 있으면 (추가 확인 필요)로 남기고 초안을 계속 진행",
        ]
    if intent == "question":
        return [
            f"핵심 질문을 `{thesis_label}` 형태로 1문장 고정",
            "질문에 바로 답하는 근거 2개를 짧은 bullet로 정리",
            "마지막 한 줄에 '그래서 다음에 무엇을 확인할지'를 명시",
        ]
    return [
        f"`{topic_label}` 기준으로 이번 문장을 3~5문장으로 짧게 확장",
        "문장마다 사실/해석을 구분해 읽기 쉽게 배치",
        "불확실한 항목은 (추가 확인 필요) 태그로 표시하고 대화는 계속 진행",
    ]


def build_conversational_fallback(
    *,
    user_message: str,
    reason: str,
    summary: dict[str, Any] | None = None,
) -> str:
    intent = _intent_key(user_message)
    topic = _safe_str(summary, "selected_topic")
    thesis = _safe_str(summary, "thesis_question")
    evidence_points = _safe_list(summary, "confirmed_evidence_points", limit=2)
    unresolved_gaps = _safe_list(summary, "unresolved_evidence_gaps", limit=2)

    lines = [
        "모델 연결이 잠시 불안정해서 임시 코칭 모드로 답변드릴게요.",
        "대화는 계속 진행할 수 있고, 지금 요청한 작업을 바로 이어서 정리해 드리겠습니다.",
        "",
        f"요청 요약: {_clip(user_message, 120) or '문장 보강 요청'}",
    ]

    if topic:
        lines.append(f"현재 주제: {topic}")
    if thesis:
        lines.append(f"현재 중심 질문: {thesis}")
    if reason and reason != "llm_unavailable":
        lines.append(f"연결 상태 코드: {reason}")

    lines.extend(["", "지금 바로 쓸 수 있는 초안 가이드"])
    lines.extend(_draft_snippet(intent, topic=topic, thesis=thesis))

    if evidence_points:
        lines.extend(["", "활용 가능한 근거"])
        lines.extend([f"- {item}" for item in evidence_points])
    if unresolved_gaps:
        lines.extend(["", "보강하면 좋은 지점"])
        lines.extend([f"- {item}" for item in unresolved_gaps])

    lines.extend(
        [
            "",
            "원하면 다음 메시지에서 제가 바로 해줄 작업",
            "1. 지금 문장을 보고서 톤으로 다듬기",
            "2. 개요 다음 소단락 1개 작성",
            "3. 근거 태그(확정/추가 확인 필요) 붙여서 재정리",
        ]
    )
    return "\n".join(lines)

