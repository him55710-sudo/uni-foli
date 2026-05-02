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
    if any(token in lowered for token in ("도입", "서론", "intro", "첫 문단")):
        return "intro"
    if any(token in lowered for token in ("제목", "title")):
        return "title"
    if any(token in lowered for token in ("근거", "증거", "출처", "자료", "논문", "웹")):
        return "evidence"
    if "?" in message or any(token in lowered for token in ("왜", "어떻게", "무엇", "질문")):
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
    topic_label = topic or "현재 선택한 주제"
    thesis_label = thesis or "핵심 질문을 한 문장으로 먼저 정리"

    if intent == "outline":
        return [
            f"- 1단락: `{topic_label}`의 배경과 문제의식을 2~3문장으로 정리합니다.",
            f"- 2단락: `{thesis_label}`을 중심으로 근거 2개를 연결합니다.",
            "- 3단락: 이번 탐구에서 이어 갈 다음 행동 1개를 제안합니다.",
        ]
    if intent == "intro":
        return [
            f"`{topic_label}`을 다루게 된 이유를 학생의 실제 기록 흐름과 연결해 시작합니다.",
            f"첫 문단은 `{thesis_label}`을 중심축으로 두고 사실과 해석을 분리합니다.",
            "확인되지 않은 내용은 '(추가 확인 필요)'로 남겨두고 문단 구조를 먼저 완성합니다.",
        ]
    if intent == "title":
        base = topic or "탐구 보고서"
        return [
            f"- {base}: 기록 기반 핵심 질문 정리",
            f"- {base}: 근거 중심 분석과 다음 실천",
            f"- {base}: 학습 기록에서 찾은 개선 포인트",
        ]
    if intent == "evidence":
        return [
            "- 문장 안의 사실 주장과 해석 주장을 줄바꿈으로 분리합니다.",
            "- 사실 주장 옆에는 학생부, 웹 자료, 논문 등 출처 유형을 붙입니다.",
            "- 근거가 비어 있으면 '(추가 확인 필요)'로 표시하고 초안을 계속 전개합니다.",
        ]
    if intent == "question":
        return [
            f"- 핵심 질문은 `{thesis_label}` 형태로 1문장 고정합니다.",
            "- 질문 바로 아래에 근거 2개를 짧은 bullet로 정리합니다.",
            "- 마지막 줄에 '그래서 다음에 확인할 것'을 명시합니다.",
        ]
    return [
        f"- `{topic_label}` 기준으로 이번 문장을 3~5문장 정도로 확장합니다.",
        "- 문장마다 사실과 해석이 드러나도록 배치합니다.",
        "- 불확실한 정보는 '(추가 확인 필요)'로 남기고 전체 흐름을 유지합니다.",
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
        "Gemini 기반 AI 응답이 잠시 불안정해서 로컬 안내 모드로 이어갈게요.",
        "작업은 중단하지 않고, 바로 이어 쓸 수 있는 초안 가이드를 먼저 정리합니다.",
        "",
        f"요청 요약: {_clip(user_message, 120) or '문장 보강 요청'}",
    ]

    if topic:
        lines.append(f"현재 주제: {topic}")
    if thesis:
        lines.append(f"현재 핵심 질문: {thesis}")
    if reason and reason != "llm_unavailable":
        lines.append(f"상태 코드: {reason}")

    lines.extend(["", "지금 바로 사용할 수 있는 초안 가이드"])
    lines.extend(_draft_snippet(intent, topic=topic, thesis=thesis))

    if evidence_points:
        lines.extend(["", "사용 가능한 근거"])
        lines.extend(f"- {item}" for item in evidence_points)
    if unresolved_gaps:
        lines.extend(["", "보강하면 좋은 지점"])
        lines.extend(f"- {item}" for item in unresolved_gaps)

    lines.extend(
        [
            "",
            "다음 메시지에서 바로 이어갈 수 있는 작업",
            "1. 지금 문장을 자연스럽게 다시 쓰기",
            "2. 개요를 3단락 구조로 다시 잡기",
            "3. 근거 태그를 붙여 안전한 초안으로 정리하기",
        ]
    )
    return "\n".join(lines)
