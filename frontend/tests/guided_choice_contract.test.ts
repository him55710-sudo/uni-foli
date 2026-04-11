import assert from 'node:assert/strict';
import test from 'node:test';

import { buildInitialGuidedSelection, resolveTemplateSelection } from '../src/lib/guidedChoice';
import type { DiagnosisResultPayload, TemplateCandidate } from '../src/lib/diagnosis';

function makeDiagnosisPayload(): DiagnosisResultPayload {
  return {
    headline: 'Guided diagnosis headline',
    strengths: ['Grounded observation exists.'],
    gaps: ['Concept explanation is still thin.'],
    recommended_focus: 'Strengthen conceptual depth first.',
    risk_level: 'warning',
    diagnosis_summary: {
      overview: 'The record needs a concept-first next step.',
      target_context: 'Mathematics Education',
      reasoning: 'Application is visible, but conceptual explanation is still weak.',
      authenticity_note: 'Keep the next move grounded in the existing record.',
    },
    gap_axes: [
      {
        key: 'cluster_depth',
        label: 'Conceptual depth',
        score: 42,
        severity: 'weak',
        rationale: 'The record explains what happened more than why it happened.',
      },
    ],
    recommended_directions: [
      {
        id: 'cluster_depth',
        label: 'Concept-driven reset',
        summary: 'Shift the next draft toward principles and mechanisms.',
        why_now: 'This is the weakest axis.',
        complexity: 'balanced',
        related_axes: ['cluster_depth'],
        topic_candidates: [
          {
            id: 'why_this_works',
            title: 'Why this works',
            summary: 'Explain the underlying concept.',
            why_it_fits: 'Repairs conceptual depth.',
            evidence_hooks: ['Existing statistics activity'],
          },
        ],
        page_count_options: [
          {
            id: 'balanced_3',
            label: '3 pages',
            page_count: 3,
            rationale: 'Enough room for question, evidence, and reflection.',
          },
        ],
        format_recommendations: [
          {
            format: 'pdf',
            label: 'PDF report',
            rationale: 'Best for concept explanation.',
            recommended: true,
          },
          {
            format: 'hwpx',
            label: 'HWPX submission',
            rationale: 'Good when submission tone matters.',
            recommended: false,
          },
        ],
        template_candidates: [
          {
            id: 'academic_report_evidence',
            label: 'Academic Report with Evidence',
            description: 'Dense evidence-forward report.',
            supported_formats: ['pdf', 'hwpx', 'pptx'],
            category: 'report',
            section_schema: ['title', 'analysis'],
            density: 'dense',
            visual_priority: 'medium',
            supports_provenance_appendix: true,
            recommended_for: ['concept-driven inquiry'],
            preview: {
              accent_color: '#1d4ed8',
              surface_tone: 'scholarly',
              cover_title: 'Evidence-backed inquiry',
              preview_sections: ['Question', 'Method'],
              thumbnail_hint: 'Academic report preview',
            },
            recommended: true,
          },
          {
            id: 'activity_summary_school',
            label: 'School Activity Summary',
            description: 'Submission-friendly summary.',
            supported_formats: ['pdf', 'hwpx'],
            category: 'school_record',
            section_schema: ['title', 'record_note'],
            density: 'light',
            visual_priority: 'low',
            supports_provenance_appendix: true,
            recommended_for: ['school submission'],
            preview: {
              accent_color: '#166534',
              surface_tone: 'school',
              cover_title: 'Activity summary',
              preview_sections: ['Scope', 'Record Note'],
              thumbnail_hint: 'School summary preview',
            },
            recommended: false,
          },
        ],
      },
    ],
    recommended_default_action: {
      direction_id: 'cluster_depth',
      topic_id: 'why_this_works',
      page_count: 3,
      export_format: 'pdf',
      template_id: 'academic_report_evidence',
      rationale: 'This is the safest coherent next move.',
    },
  };
}

test('buildInitialGuidedSelection respects the recommended default action', () => {
  const selection = buildInitialGuidedSelection(makeDiagnosisPayload());

  assert.deepEqual(selection, {
    directionId: 'cluster_depth',
    topicId: 'why_this_works',
    pageCount: 3,
    format: 'pdf',
    templateId: 'academic_report_evidence',
  });
});

test('buildInitialGuidedSelection falls back to the first available structured choice', () => {
  const diagnosis = makeDiagnosisPayload();
  diagnosis.recommended_default_action = null;

  const selection = buildInitialGuidedSelection(diagnosis);

  assert.equal(selection.directionId, 'cluster_depth');
  assert.equal(selection.topicId, 'why_this_works');
  assert.equal(selection.pageCount, 3);
  assert.equal(selection.format, 'pdf');
});

test('resolveTemplateSelection keeps valid current choice and otherwise prefers recommended or default templates', () => {
  const templates = makeDiagnosisPayload().recommended_directions?.[0].template_candidates as TemplateCandidate[];

  assert.equal(
    resolveTemplateSelection(templates, {
      currentTemplateId: 'activity_summary_school',
      preferredTemplateId: 'academic_report_evidence',
      recommendedTemplateIds: new Set(['academic_report_evidence']),
    }),
    'activity_summary_school',
  );

  assert.equal(
    resolveTemplateSelection(templates, {
      currentTemplateId: 'missing-template',
      preferredTemplateId: 'academic_report_evidence',
      recommendedTemplateIds: new Set(['academic_report_evidence']),
    }),
    'academic_report_evidence',
  );

  assert.equal(
    resolveTemplateSelection(templates, {
      currentTemplateId: null,
      preferredTemplateId: null,
      recommendedTemplateIds: new Set(['activity_summary_school']),
    }),
    'activity_summary_school',
  );
});
