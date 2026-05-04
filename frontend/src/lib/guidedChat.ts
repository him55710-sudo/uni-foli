export interface GuidedTopicSuggestion {
  id: string;
  title: string;
  why_fit_student: string;
  link_to_record_flow: string;
  link_to_target_major_or_university: string | null;
  novelty_point?: string | null;
  caution_note: string | null;
  suggestion_type?: 'interest' | 'subject' | 'major' | null;
  is_starred?: boolean;
}

export type GuidedConversationPhase =
  | 'subject_input'
  | 'specific_topic_check'
  | 'topic_recommendation'
  | 'topic_selection'
  | 'page_range_selection'
  | 'structure_selection'
  | 'drafting_next_step'
  | 'freeform_coauthoring';

export interface GuidedChoiceOption {
  id: string;
  label: string;
  description?: string | null;
  value?: string | null;
}

export interface GuidedChoiceGroup {
  id: string;
  title: string;
  style: 'cards' | 'chips' | 'buttons';
  options: GuidedChoiceOption[];
}

export interface GuidedPageRangeOption {
  label: string;
  min_pages: number;
  max_pages: number;
  why_this_length: string;
}

export interface GuidedStructureOption extends GuidedChoiceOption {}

export interface GuidedOutlineSection {
  title: string;
  purpose: string;
}

export interface GuidedTopicSelectionResponse {
  phase?: GuidedConversationPhase;
  assistant_message?: string | null;
  selected_topic_id: string;
  selected_title: string;
  recommended_page_ranges: GuidedPageRangeOption[];
  recommended_outline: GuidedOutlineSection[];
  starter_draft_markdown: string;
  guidance_message: string;
  structure_options?: GuidedStructureOption[];
  next_action_options?: GuidedChoiceOption[];
  choice_groups?: GuidedChoiceGroup[];
  limited_mode?: boolean | null;
  limited_reason?: string | null;
  state_summary?: Record<string, unknown> | null;
}

export interface GuidedTopicSuggestionResponse {
  greeting: string;
  assistant_message?: string | null;
  phase?: GuidedConversationPhase;
  subject: string;
  suggestions: GuidedTopicSuggestion[];
  evidence_gap_note: string | null;
  choice_groups?: GuidedChoiceGroup[];
  limited_mode?: boolean | null;
  limited_reason?: string | null;
  state_summary?: Record<string, unknown> | null;
}

export interface GuidedPageRangeSelectionResponse {
  phase?: GuidedConversationPhase;
  assistant_message: string;
  selected_page_range_label: string;
  selected_page_range_note?: string | null;
  structure_options: GuidedStructureOption[];
  choice_groups?: GuidedChoiceGroup[];
  limited_mode?: boolean | null;
  limited_reason?: string | null;
  state_summary?: Record<string, unknown> | null;
}

export interface GuidedStructureSelectionResponse {
  phase?: GuidedConversationPhase;
  assistant_message: string;
  selected_structure_id: string;
  selected_structure_label: string;
  next_action_options: GuidedChoiceOption[];
  choice_groups?: GuidedChoiceGroup[];
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

export const TOPIC_SUGGESTION_MIN_COUNT = 300;
export const TOPIC_SUGGESTION_PREVIEW_COUNT = 12;

export function limitTopicSuggestions(
  response: GuidedTopicSuggestionResponse,
  limit = TOPIC_SUGGESTION_MIN_COUNT,
): GuidedTopicSuggestionResponse {
  return {
    ...response,
    suggestions: response.suggestions.slice(0, limit),
  };
}
