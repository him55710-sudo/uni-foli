import type { GuidedChoiceGroup } from './guidedChat';

export type ChatbotMode = 'upload' | 'diagnosis' | 'trend';

const CHATBOT_MODES: ChatbotMode[] = ['upload', 'diagnosis', 'trend'];

export interface DiagnosisArtifactSnapshot {
  headline: string | null;
  recommendedFocus: string | null;
  riskLevel: string | null;
  strengths: string[];
  weaknesses: string[];
  majorAlignmentHints: string[];
  recommendedActivityTopics: string[];
  completionState: 'ongoing' | 'finalized' | 'unknown';
}

export interface DiagnosisChatStarter {
  mode: 'diagnosis';
  briefing: string;
  quickActionGroup: GuidedChoiceGroup;
  artifactSnapshot: DiagnosisArtifactSnapshot;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asText(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const normalized = value.trim();
  return normalized || null;
}

function asTextList(value: unknown, limit = 4): string[] {
  if (!Array.isArray(value)) return [];
  const out: string[] = [];
  const seen = new Set<string>();
  for (const item of value) {
    const text = asText(item);
    if (!text) continue;
    const key = text.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(text);
    if (out.length >= limit) break;
  }
  return out;
}

function collectMajorDirectionLabels(value: unknown, limit = 3): string[] {
  if (!Array.isArray(value)) return [];
  const labels: string[] = [];
  const seen = new Set<string>();
  for (const item of value) {
    let candidate: string | null = null;
    if (typeof item === 'string') {
      candidate = asText(item);
    } else if (item && typeof item === 'object') {
      const record = item as Record<string, unknown>;
      candidate =
        asText(record.label) ??
        asText(record.major) ??
        asText(record.title) ??
        asText(record.name);
    }
    if (!candidate) continue;
    const normalized = candidate.toLowerCase();
    if (seen.has(normalized)) continue;
    seen.add(normalized);
    labels.push(candidate);
    if (labels.length >= limit) break;
  }
  return labels;
}

function hasAnyArtifactContent(snapshot: DiagnosisArtifactSnapshot): boolean {
  return Boolean(
    snapshot.headline ||
      snapshot.recommendedFocus ||
      snapshot.riskLevel ||
      snapshot.strengths.length ||
      snapshot.weaknesses.length ||
      snapshot.majorAlignmentHints.length ||
      snapshot.recommendedActivityTopics.length,
  );
}

function normalizeRiskLabel(riskLevel: string | null): string | null {
  const key = (riskLevel || '').trim().toLowerCase();
  if (!key) return null;
  if (key === 'safe') return '안정 구간';
  if (key === 'warning') return '보완 필요';
  if (key === 'danger') return '집중 보완 필요';
  return riskLevel;
}

function compactList(values: string[]): string {
  return values.slice(0, 3).join('; ');
}

function buildGroundedPrompt(
  kind: 'topic' | 'outline' | 'opening' | 'revision',
  snapshot: DiagnosisArtifactSnapshot
): string {
  const lines = [
    '아래는 저장된 진단 아티팩트 요약이다. 이 내용은 학생에게 그대로 나열하지 말고, 탐구보고서 작성 가이드에 자연스럽게 반영해.',
    `headline: ${snapshot.headline || '-'}`,
    `recommended_focus: ${snapshot.recommendedFocus || '-'}`,
    `risk_level: ${snapshot.riskLevel || '-'}`,
    `key_strengths: ${compactList(snapshot.strengths) || '-'}`,
    `key_weaknesses: ${compactList(snapshot.weaknesses) || '-'}`,
    `major_alignment_hints: ${compactList(snapshot.majorAlignmentHints) || '-'}`,
    `recommended_activity_topics: ${compactList(snapshot.recommendedActivityTopics) || '-'}`,
    `record_completion_state: ${snapshot.completionState}`,
    '강점은 주제 선택과 논지의 차별화에 쓰고, 약점은 보고서 구조의 보완 체크리스트로 써.',
    '부족한 내용은 학생이 다음에 확인할 질문으로 바꿔.',
  ];

  if (kind === 'topic') {
    lines.push(
      '요청: 탐구보고서 주제 설계',
      '출력: 학생 진단의 강점과 보완점을 고려해 탐구 주제 후보를 최소 300개 이상 넓게 제안하되, 먼저 볼 만한 하이라이트와 각 주제의 적합성/주의점을 함께 적어.',
    );
  } else if (kind === 'outline') {
    lines.push(
      '요청: 탐구보고서 개요 작성',
      '출력: 한 가지 추천 주제를 고르고 서론-본론-결론 개요를 제안해. 각 단락이 학생의 강점을 어떻게 살리고 약점을 어떻게 보완하는지 함께 안내해.',
    );
  } else if (kind === 'opening') {
    lines.push(
      '요청: 첫 문단 작성',
      '출력: 탐구 동기와 문제의식이 드러나는 서론 초안을 작성해. 학생 기록을 과장하지 말고 자연스럽게 전공 관심과 연결해.',
    );
  } else {
    lines.push(
      '요청: 초안 보완 방향',
      '출력: 현재 탐구보고서를 쓴다고 가정하고, 강점은 더 선명하게 살리고 약점은 줄이는 보완 체크리스트와 다음 작성 순서를 제안해.',
    );
  }

  return lines.join('\n');
}

export function extractDiagnosisArtifactSnapshot(resultPayload: unknown): DiagnosisArtifactSnapshot | null {
  const payload = asRecord(resultPayload);
  if (!payload) return null;

  const summary = asRecord(payload.diagnosis_summary_json);
  const chatbotContext = asRecord(payload.chatbot_context_json);

  const rawState = (summary?.completion_state || payload.record_completion_state || 'unknown') as string;
  const completionState = (['ongoing', 'finalized'].includes(rawState) ? rawState : 'unknown') as 'ongoing' | 'finalized' | 'unknown';

  const snapshot: DiagnosisArtifactSnapshot = {
    headline: asText(summary?.headline) ?? asText(payload.headline),
    recommendedFocus: asText(summary?.recommended_focus) ?? asText(payload.recommended_focus),
    riskLevel: asText(summary?.risk_level) ?? asText(payload.risk_level),
    strengths: asTextList(chatbotContext?.key_strengths ?? summary?.strengths ?? payload.strengths, 4),
    weaknesses: asTextList(chatbotContext?.key_weaknesses ?? summary?.gaps ?? payload.gaps, 4),
    majorAlignmentHints: asTextList(chatbotContext?.major_alignment_hints, 4),
    recommendedActivityTopics: asTextList(
      chatbotContext?.recommended_activity_topics ?? summary?.recommended_topics ?? payload.recommended_topics,
      4,
    ),
    completionState,
  };

  if (!hasAnyArtifactContent(snapshot)) return null;
  return snapshot;
}

export function extractDiagnosisMajorDirectionCandidates(resultPayload: unknown, limit = 3): string[] {
  const payload = asRecord(resultPayload);
  if (!payload) return [];
  const summary = asRecord(payload.diagnosis_summary_json);
  const labelsFromSummary = collectMajorDirectionLabels(summary?.major_direction_candidates_top3, limit);
  if (labelsFromSummary.length > 0) return labelsFromSummary;

  const labelsFromPayloadSummary = collectMajorDirectionLabels(payload.major_direction_candidates_top3, limit);
  if (labelsFromPayloadSummary.length > 0) return labelsFromPayloadSummary;

  const recommendedDirections = Array.isArray(payload.recommended_directions)
    ? payload.recommended_directions
    : [];
  return collectMajorDirectionLabels(recommendedDirections, limit);
}

export function buildDiagnosisChatStarter(resultPayload: unknown): DiagnosisChatStarter | null {
  const snapshot = extractDiagnosisArtifactSnapshot(resultPayload);
  if (!snapshot) return null;

  const riskLabel = normalizeRiskLabel(snapshot.riskLevel);
  const isFinalized = snapshot.completionState === 'finalized';

  const briefingLines = [
    isFinalized
      ? '진단 결과를 바탕으로 탐구보고서 작성 방향을 잡아볼게요. 강점과 보완점은 제가 내부 기준으로 반영하겠습니다.'
      : '진단 결과를 바탕으로 탐구보고서 작성 방향을 잡아볼게요. 강점은 살리고 보완점은 구조 안에서 메우겠습니다.',
    snapshot.headline ? `- 핵심 요약: ${snapshot.headline}` : '- 핵심 요약: 진단 아티팩트가 준비되었습니다.',
    snapshot.recommendedFocus ? `- 추천 초점: ${snapshot.recommendedFocus}` : null,
    riskLabel ? `- 현재 상태: ${riskLabel}` : null,
    '아래 항목을 고르면 진단 내용을 따로 나열하지 않고, 보고서 주제와 구성에 녹여서 안내합니다.',
  ].filter(Boolean) as string[];

  const options = [
    {
      id: 'diagnosis-report-topic',
      label: '주제 잡기',
      value: buildGroundedPrompt('topic', snapshot),
    },
    {
      id: 'diagnosis-report-outline',
      label: '개요 만들기',
      value: buildGroundedPrompt('outline', snapshot),
    },
    {
      id: 'diagnosis-report-opening',
      label: '첫 문단 쓰기',
      value: buildGroundedPrompt('opening', snapshot),
    },
    {
      id: 'diagnosis-report-revision',
      label: '보완 반영하기',
      value: buildGroundedPrompt('revision', snapshot),
    },
  ];

  const quickActionGroup: GuidedChoiceGroup = {
    id: 'diagnosis-quick-actions',
    title: '진단 기반 탐구보고서 작성',
    style: 'chips',
    options,
  };

  return {
    mode: 'diagnosis',
    briefing: briefingLines.join('\n'),
    quickActionGroup,
    artifactSnapshot: snapshot,
  };
}

function isChatbotMode(value: unknown): value is ChatbotMode {
  return typeof value === 'string' && CHATBOT_MODES.includes(value as ChatbotMode);
}

export function resolveChatbotModeFromRouteContext(params: {
  pathname: string;
  routeState?: unknown;
  hasDiagnosisArtifact?: boolean;
}): ChatbotMode {
  const routeState = asRecord(params.routeState);
  const directMode = routeState?.chatbotMode;
  if (isChatbotMode(directMode)) return directMode;

  if (routeState?.fromDiagnosis === true || params.hasDiagnosisArtifact) return 'diagnosis';

  if (params.pathname.includes('/trend')) return 'trend';
  if (params.pathname.includes('/diagnosis')) return 'upload';

  return 'upload';
}
