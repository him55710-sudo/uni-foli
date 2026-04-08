import type { QuestStartPayload, QuestStarterChoice } from '@shared-contracts';

export type { QuestStartPayload, QuestStarterChoice } from '@shared-contracts';

const ACTIVE_QUEST_START_KEY = 'uni_foli_active_quest_start';

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
