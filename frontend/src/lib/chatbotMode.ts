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
  kind: 'strengths' | 'weaknesses' | 'major_fit' | 'activities' | 'interview', 
  snapshot: DiagnosisArtifactSnapshot
): string {
  const lines = [
    '아래는 저장된 진단 아티팩트 요약이다. 반드시 이 근거를 우선 사용해 답변해.',
    `headline: ${snapshot.headline || '-'}`,
    `recommended_focus: ${snapshot.recommendedFocus || '-'}`,
    `risk_level: ${snapshot.riskLevel || '-'}`,
    `key_strengths: ${compactList(snapshot.strengths) || '-'}`,
    `key_weaknesses: ${compactList(snapshot.weaknesses) || '-'}`,
    `major_alignment_hints: ${compactList(snapshot.majorAlignmentHints) || '-'}`,
    `recommended_activity_topics: ${compactList(snapshot.recommendedActivityTopics) || '-'}`,
    `record_completion_state: ${snapshot.completionState}`,
    '근거가 부족하면 추측하지 말고 부족한 지점을 명시해.',
  ];

  if (kind === 'strengths') {
    lines.push(
      '요청: 강점 보기',
      '출력: 짧은 bullet 3개 이내, 각 bullet마다 근거 1줄, 마지막에 즉시 실행 가능한 1문장 제안.',
    );
  } else if (kind === 'weaknesses') {
    lines.push(
      '요청: 약점 보기',
      '출력: 보완 우선순위 3개 이내 bullet, 각 항목마다 왜 중요한지 1줄, 과장 금지.',
    );
  } else if (kind === 'major_fit') {
    lines.push(
      '요청: 전공적합성 보기',
      '출력: 전공적합성 근거/리스크를 균형 있게 요약, 4줄 이내, 불확실성은 명확히 표시.',
    );
  } else if (kind === 'interview') {
     lines.push(
      '요청: 면접 질문 및 답변 가이드',
      '출력: 실전 면접 예상 질문 2개와 그에 대한 생기부 기반 답변 전략 제안.',
    );
  } else {
    lines.push(
      '요청: 추천 활동 보기',
      '출력: 추천 활동 3개 이내 bullet, 각 항목에 기대효과와 주의점 1줄씩.',
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
    isFinalized ? '생기부가 마감된 시기네요! 이제 실전 면접과 서류 검증에 집중해야 할 때입니다.' : '진단 결과를 기반으로 생기부 보완을 시작해볼까요?',
    snapshot.headline ? `- 핵심 요약: ${snapshot.headline}` : '- 핵심 요약: 진단 아티팩트가 준비되었습니다.',
    snapshot.recommendedFocus ? `- 추천 초점: ${snapshot.recommendedFocus}` : null,
    riskLabel ? `- 현재 상태: ${riskLabel}` : null,
    isFinalized ? '면접 예상 질문을 확인하거나, 현재 생기부의 강점 포인트를 정리해보세요.' : '아래 항목을 눌러 보완이 필요한 지점부터 확인해보세요.',
  ].filter(Boolean) as string[];

  const options = [
    {
      id: 'diagnosis-strengths',
      label: '강점 보기',
      value: buildGroundedPrompt('strengths', snapshot),
    },
    {
      id: 'diagnosis-weaknesses',
      label: '약점 보기',
      value: buildGroundedPrompt('weaknesses', snapshot),
    },
    {
      id: 'diagnosis-major-fit',
      label: '전공적합성 보기',
      value: buildGroundedPrompt('major_fit', snapshot),
    },
  ];

  if (isFinalized) {
    options.push({
      id: 'diagnosis-interview',
      label: '면접 질문 샘플',
      value: buildGroundedPrompt('interview', snapshot),
    });
  } else {
    options.push({
      id: 'diagnosis-activities',
      label: '보완 활동 추천',
      value: buildGroundedPrompt('activities', snapshot),
    });
  }

  const quickActionGroup: GuidedChoiceGroup = {
    id: 'diagnosis-quick-actions',
    title: isFinalized ? '면접 및 실전 대비' : '진단 결과 빠른 확인',
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
