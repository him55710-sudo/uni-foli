import os
from typing import Literal

import google.generativeai as genai
from pydantic import BaseModel, Field

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "DUMMY_KEY"))


class DiagnosisResult(BaseModel):
    headline: str = Field(description="Short diagnosis summary headline")
    strengths: list[str] = Field(description="Current grounded strengths in the record")
    gaps: list[str] = Field(description="Visible evidence or inquiry gaps to close next")
    risk_level: Literal["safe", "warning", "danger"] = Field(description="Risk tier")
    recommended_focus: str = Field(description="Most important next focus")


def build_grounded_diagnosis_result(
    *,
    project_title: str,
    target_major: str | None,
    document_count: int,
    full_text: str,
) -> DiagnosisResult:
    major_label = target_major or "the selected major"
    lowered = full_text.lower()

    has_measurement = any(token in lowered for token in ["measure", "experiment", "data", "analysis", "survey"])
    has_comparison = any(token in lowered for token in ["compare", "difference", "before", "after", "trend"])
    has_reflection = any(token in lowered for token in ["reflect", "limit", "improve", "lesson", "feedback"])

    strengths: list[str] = []
    gaps: list[str] = []

    if document_count >= 1 and len(full_text.split()) >= 120:
        strengths.append("The uploaded record already contains enough grounded text to build the next activity.")
    else:
        gaps.append("The current record is still thin, so the next quest should create clearer evidence before expanding claims.")

    if has_measurement or has_comparison:
        strengths.append("The record shows an inquiry trace through measuring, comparing, or analyzing.")
    else:
        gaps.append("The record does not yet show a visible inquiry process such as comparison, measurement, or analysis.")

    if has_reflection:
        strengths.append("The student already reflects on limits or improvements, which helps later drafting.")
    else:
        gaps.append("Method limits and next-step reflection are still weak in the current record.")

    if not strengths:
        strengths.append("The record has a usable starting point, but it needs a more explicit evidence trail.")
    if not gaps:
        gaps.append("Turn the strongest topic into a deeper follow-up activity with clearer evidence and reflection.")

    risk_level: Literal["safe", "warning", "danger"]
    if len(gaps) >= 3:
        risk_level = "danger"
    elif len(gaps) == 2:
        risk_level = "warning"
    else:
        risk_level = "safe"

    recommended_focus = (
        f"{major_label} inquiry for {project_title} that adds one comparison, one explicit method limit, "
        "and one concrete reflection tied to the current record."
    )
    headline = (
        f"For {major_label}, the record is {'grounded enough' if risk_level == 'safe' else 'not finished yet'}; "
        "the next step should produce clearer evidence, not broader claims."
    )

    return DiagnosisResult(
        headline=headline,
        strengths=strengths[:3],
        gaps=gaps[:4],
        risk_level=risk_level,
        recommended_focus=recommended_focus,
    )


async def evaluate_student_record(
    user_major: str,
    masked_text: str,
    target_university: str | None = None,
    target_major: str | None = None,
) -> DiagnosisResult:
    system_instruction = (
        "You are a rigorous admissions-oriented school record analyst. "
        "Read the student's grounded record and explain the real gaps between the current evidence "
        "and the stated target major. Do not predict admission. Focus on what is missing and what "
        "the next action should be."
    )
    target_context = (
        f"Target University: {target_university or 'Not set'}\n"
        f"Target Major: {target_major or user_major}"
    )

    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        system_instruction=system_instruction,
    )

    try:
        response = await model.generate_content_async(
            f"{target_context}\nPrimary Major Context: {user_major}\n\n[Masked Record]\n{masked_text}",
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=DiagnosisResult,
                temperature=0.2,
            ),
        )
        return DiagnosisResult.model_validate_json(response.text)
    except Exception as exc:  # noqa: BLE001
        return DiagnosisResult(
            headline=f"Diagnosis request failed: {exc}",
            strengths=[],
            gaps=["The AI diagnosis call failed, so use the grounded fallback diagnosis instead."],
            risk_level="warning",
            recommended_focus="Retry the diagnosis or continue with the grounded fallback blueprint.",
        )
