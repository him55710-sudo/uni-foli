export interface QuestStarterChoice {
  id: string;
  label: string;
  prompt: string;
}

export interface QuestStartPayload {
  quest_id: string;
  blueprint_id: string;
  project_id: string;
  project_title: string;
  target_major: string | null;
  subject: string;
  title: string;
  summary: string;
  why_this_matters: string;
  expected_record_impact: string;
  recommended_output_type: string;
  status: string;
  workshop_intro: string;
  document_seed_markdown: string;
  starter_choices_seed: QuestStarterChoice[];
}

const ACTIVE_QUEST_START_KEY = 'polio_active_quest_start';

export function saveQuestStart(payload: QuestStartPayload) {
  sessionStorage.setItem(ACTIVE_QUEST_START_KEY, JSON.stringify(payload));
}

export function readQuestStart(projectId?: string | null): QuestStartPayload | null {
  try {
    const raw = sessionStorage.getItem(ACTIVE_QUEST_START_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw) as QuestStartPayload;
    if (projectId && parsed.project_id !== projectId) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearQuestStart() {
  sessionStorage.removeItem(ACTIVE_QUEST_START_KEY);
}
