from datetime import datetime

from pydantic import BaseModel


class QuestRead(BaseModel):
    id: str
    subject: str
    title: str
    summary: str
    difficulty: str
    why_this_matters: str
    expected_record_impact: str
    recommended_output_type: str
    status: str


class QuestGroupRead(BaseModel):
    name: str
    quests: list[QuestRead]


class CurrentBlueprintRead(BaseModel):
    id: str
    project_id: str
    project_title: str
    target_major: str | None = None
    headline: str
    recommended_focus: str
    semester_priority_message: str
    priority_quests: list[QuestRead]
    subject_groups: list[QuestGroupRead]
    activity_groups: list[QuestGroupRead]
    expected_record_effects: list[str]
    created_at: datetime


class StarterChoiceRead(BaseModel):
    id: str
    label: str
    prompt: str


class QuestStartResponse(BaseModel):
    quest_id: str
    blueprint_id: str
    project_id: str
    project_title: str
    target_major: str | None = None
    subject: str
    title: str
    summary: str
    why_this_matters: str
    expected_record_impact: str
    recommended_output_type: str
    status: str
    workshop_intro: str
    document_seed_markdown: str
    starter_choices_seed: list[StarterChoiceRead]
