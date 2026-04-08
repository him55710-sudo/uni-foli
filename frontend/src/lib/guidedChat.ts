export interface GuidedTopicSuggestion {
  id: string;
  title: string;
  why_fit_student: string;
  link_to_record_flow: string;
  link_to_target_major_or_university: string | null;
  novelty_point: string;
  caution_note: string | null;
}

export interface GuidedPageRangeOption {
  label: string;
  min_pages: number;
  max_pages: number;
  why_this_length: string;
}

export interface GuidedOutlineSection {
  title: string;
  purpose: string;
}

export interface GuidedTopicSelectionResponse {
  selected_topic_id: string;
  selected_title: string;
  recommended_page_ranges: GuidedPageRangeOption[];
  recommended_outline: GuidedOutlineSection[];
  starter_draft_markdown: string;
  guidance_message: string;
  limited_mode?: boolean | null;
  limited_reason?: string | null;
  state_summary?: Record<string, unknown> | null;
}

export interface GuidedTopicSuggestionResponse {
  greeting: string;
  subject: string;
  suggestions: GuidedTopicSuggestion[];
  evidence_gap_note: string | null;
  limited_mode?: boolean | null;
  limited_reason?: string | null;
  state_summary?: Record<string, unknown> | null;
}

export interface GuidedChatUiState {
  draftMarkdown: string;
  selectedTopicId: string | null;
  selectedTitle: string | null;
  pageRanges: GuidedPageRangeOption[];
  outline: GuidedOutlineSection[];
  guidanceMessage: string | null;
}

export function createInitialGuidedChatUiState(initialDraft = ''): GuidedChatUiState {
  return {
    draftMarkdown: initialDraft,
    selectedTopicId: null,
    selectedTitle: null,
    pageRanges: [],
    outline: [],
    guidanceMessage: null,
  };
}

export function applyTopicSelectionToUiState(
  state: GuidedChatUiState,
  response: GuidedTopicSelectionResponse,
): GuidedChatUiState {
  return {
    ...state,
    draftMarkdown: response.starter_draft_markdown,
    selectedTopicId: response.selected_topic_id,
    selectedTitle: response.selected_title,
    pageRanges: response.recommended_page_ranges,
    outline: response.recommended_outline,
    guidanceMessage: response.guidance_message,
  };
}

export function ensureThreeSuggestions(response: GuidedTopicSuggestionResponse): GuidedTopicSuggestionResponse {
  return {
    ...response,
    suggestions: response.suggestions.slice(0, 3),
  };
}
