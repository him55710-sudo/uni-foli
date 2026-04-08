import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, FileText, Layers3, Loader2, Presentation, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import { api, resolveApiBaseUrl } from '../lib/api';
import { buildInitialGuidedSelection, resolveTemplateSelection } from '../lib/guidedChoice';
import type {
  DiagnosisGuidedPlanResponse,
  DiagnosisResultPayload,
  FormatRecommendation,
  GuidedDraftOutline,
  PageCountOption,
  RecommendedDirection,
  TemplateCandidate,
  TopicCandidate,
} from '../lib/diagnosis';

interface RenderTemplateInfo extends TemplateCandidate {}

interface RenderJobRead {
  id: string;
  draft_id: string;
  render_format: string;
  template_id: string | null;
  template_label: string | null;
  status: string;
  download_url: string | null;
  result_message: string | null;
}

interface DiagnosisGuidedChoicePanelProps {
  diagnosisRunId: string;
  projectId: string;
  diagnosis: DiagnosisResultPayload;
  useSynchronousApiJobs: boolean;
}

function tone(selected: boolean) {
  return selected
    ? 'border-slate-900 bg-slate-900 text-white shadow-lg'
    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-400';
}

function toAbsoluteDownloadUrl(downloadUrl: string): string {
  if (/^https?:\/\//i.test(downloadUrl)) {
    return downloadUrl;
  }
  const apiBase = resolveApiBaseUrl();
  if (downloadUrl.startsWith('/')) {
    return `${apiBase}${downloadUrl}`;
  }
  return `${apiBase}/${downloadUrl}`;
}

function resolveFileName(contentDisposition: string, fallbackName: string): string {
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const simpleMatch = contentDisposition.match(/filename=\"?([^\";]+)\"?/i);
  if (simpleMatch?.[1]) {
    return simpleMatch[1];
  }
  return fallbackName;
}

export function DiagnosisGuidedChoicePanel({
  diagnosisRunId,
  projectId,
  diagnosis,
  useSynchronousApiJobs,
}: DiagnosisGuidedChoicePanelProps) {
  const directions = diagnosis.recommended_directions ?? [];
  const defaultAction = diagnosis.recommended_default_action ?? null;
  const initialSelection = useMemo(() => buildInitialGuidedSelection(diagnosis), [diagnosis]);
  const [selectedDirectionId, setSelectedDirectionId] = useState<string | null>(initialSelection.directionId);
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const [selectedPageCount, setSelectedPageCount] = useState<number | null>(null);
  const [selectedFormat, setSelectedFormat] = useState<'pdf' | 'pptx' | 'hwpx' | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [templateGallery, setTemplateGallery] = useState<RenderTemplateInfo[]>([]);
  const [outline, setOutline] = useState<GuidedDraftOutline | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [lastRenderJob, setLastRenderJob] = useState<RenderJobRead | null>(null);
  const [includeProvenanceAppendix, setIncludeProvenanceAppendix] = useState(false);
  const [hideInternalProvenance, setHideInternalProvenance] = useState(true);
  const downloadRenderedArtifact = async (downloadUrl: string, formatHint?: string) => {
    const absoluteDownloadUrl = toAbsoluteDownloadUrl(downloadUrl);
    const fallbackName = `diagnosis_export.${formatHint || 'pdf'}`;
    const loadingId = toast.loading('Downloading the export...');
    try {
      const file = await api.download(absoluteDownloadUrl);
      const fileName = resolveFileName(file.contentDisposition, fallbackName);
      const objectUrl = window.URL.createObjectURL(file.blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = fileName;
      anchor.rel = 'noreferrer';
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      window.setTimeout(() => window.URL.revokeObjectURL(objectUrl), 2000);
      toast.success('Export downloaded.', { id: loadingId });
    } catch (error) {
      console.error(error);
      toast.error('The exported file could not be downloaded.', { id: loadingId });
    }
  };

  const waitForRenderJobResult = async (jobId: string, maxAttempts = 15): Promise<RenderJobRead | null> => {
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const current = await api.get<RenderJobRead>(`/api/v1/render-jobs/${jobId}`);
      if (current.download_url || current.status === 'failed' || current.status === 'succeeded') {
        return current;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1200));
    }
    return null;
  };

  const selectedDirection = useMemo<RecommendedDirection | null>(
    () => directions.find((item) => item.id === selectedDirectionId) ?? null,
    [directions, selectedDirectionId],
  );
  const topicCandidates = selectedDirection?.topic_candidates ?? [];
  const pageCountOptions = selectedDirection?.page_count_options ?? [];
  const formatRecommendations = selectedDirection?.format_recommendations ?? [];
  const recommendedTemplateIds = useMemo(
    () => new Set((selectedDirection?.template_candidates ?? []).map((item) => item.id)),
    [selectedDirection],
  );
  const recommendedDirection = useMemo(
    () => directions.find((item) => item.id === defaultAction?.direction_id) ?? null,
    [defaultAction?.direction_id, directions],
  );

  useEffect(() => {
    setSelectedDirectionId(initialSelection.directionId);
    setSelectedTopicId(initialSelection.topicId);
    setSelectedPageCount(initialSelection.pageCount);
    setSelectedFormat(initialSelection.format);
    setSelectedTemplateId(initialSelection.templateId);
    setOutline(null);
    setLastRenderJob(null);
  }, [initialSelection.directionId, initialSelection.format, initialSelection.pageCount, initialSelection.templateId, initialSelection.topicId]);

  useEffect(() => {
    const useDefaultAction = initialSelection.directionId === selectedDirectionId;
    setSelectedTopicId(
      useDefaultAction
        ? (topicCandidates.find((item) => item.id === initialSelection.topicId)?.id ?? topicCandidates[0]?.id ?? null)
        : (topicCandidates[0]?.id ?? null),
    );
    setSelectedPageCount(
      useDefaultAction
        ? (pageCountOptions.find((item) => item.page_count === initialSelection.pageCount)?.page_count ?? pageCountOptions[0]?.page_count ?? null)
        : (pageCountOptions[0]?.page_count ?? null),
    );
    setSelectedFormat(
      useDefaultAction
        ? ((formatRecommendations.find((item) => item.format === initialSelection.format)?.format) ??
            (formatRecommendations.find((item) => item.recommended) ?? formatRecommendations[0])?.format ??
            null)
        : ((formatRecommendations.find((item) => item.recommended) ?? formatRecommendations[0])?.format ?? null),
    );
    setSelectedTemplateId(useDefaultAction ? initialSelection.templateId : null);
    setOutline(null);
    setLastRenderJob(null);
  }, [formatRecommendations, initialSelection.directionId, initialSelection.format, initialSelection.pageCount, initialSelection.templateId, initialSelection.topicId, pageCountOptions, selectedDirectionId, topicCandidates]);

  useEffect(() => {
    if (!selectedFormat) {
      setTemplateGallery([]);
      setSelectedTemplateId(null);
      return;
    }
    let cancelled = false;
    void api
      .get<RenderTemplateInfo[]>(`/api/v1/render-jobs/templates?render_format=${selectedFormat}`)
      .then((templates) => {
        if (!cancelled) {
          setTemplateGallery(templates);
          setSelectedTemplateId((current) =>
            resolveTemplateSelection(templates, {
              currentTemplateId: current,
              preferredTemplateId: selectedDirectionId === initialSelection.directionId ? initialSelection.templateId : null,
              recommendedTemplateIds,
            }),
          );
        }
      })
      .catch(() => {
        if (!cancelled) {
          setTemplateGallery([]);
          setSelectedTemplateId(null);
          toast.error('The template gallery could not be loaded for this format.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [initialSelection.directionId, initialSelection.templateId, recommendedTemplateIds, selectedDirectionId, selectedFormat]);

  useEffect(() => {
    if (outline) {
      setOutline(null);
      setLastRenderJob(null);
    }
  }, [hideInternalProvenance, includeProvenanceAppendix, selectedFormat, selectedPageCount, selectedTemplateId, selectedTopicId]);

  const buildPlan = async () => {
    if (!selectedDirection || !selectedTopicId || !selectedPageCount || !selectedFormat || !selectedTemplateId) {
      toast.error('Select a direction, topic, length, format, and template first.');
      return;
    }
    setIsGenerating(true);
    try {
      const response = await api.post<DiagnosisGuidedPlanResponse>(
        `/api/v1/diagnosis/${diagnosisRunId}/guided-plan`,
        {
          direction_id: selectedDirection.id,
          topic_id: selectedTopicId,
          page_count: selectedPageCount,
          export_format: selectedFormat,
          template_id: selectedTemplateId,
          include_provenance_appendix: includeProvenanceAppendix,
          hide_internal_provenance_on_final_export: hideInternalProvenance,
        },
      );
      setOutline(response.outline);
      toast.success('Guided outline is ready.');
    } catch (error) {
      console.error(error);
      toast.error('The guided outline could not be generated.');
    } finally {
      setIsGenerating(false);
    }
  };

  const exportOutline = async () => {
    if (!outline?.draft_id || !selectedFormat || !selectedTemplateId) {
      toast.error('Generate the outline before exporting.');
      return;
    }
    setIsExporting(true);
    try {
      const created = await api.post<RenderJobRead>('/api/v1/render-jobs', {
        project_id: projectId,
        draft_id: outline.draft_id,
        render_format: selectedFormat,
        template_id: selectedTemplateId,
        include_provenance_appendix: includeProvenanceAppendix,
        hide_internal_provenance_on_final_export: hideInternalProvenance,
      });
      let resolved = created;
      if (useSynchronousApiJobs) {
        resolved = await api.post<RenderJobRead>(`/api/v1/render-jobs/${created.id}/process`);
      } else {
        try {
          resolved = await api.post<RenderJobRead>(`/api/v1/render-jobs/${created.id}/process`);
        } catch {
          // Fallback to queue mode when inline processing is unavailable.
        }
        if (!resolved.download_url) {
          const eventual = await waitForRenderJobResult(created.id);
          if (eventual) {
            resolved = eventual;
          }
        }
      }
      setLastRenderJob(resolved);
      if (resolved.download_url) {
        await downloadRenderedArtifact(resolved.download_url, resolved.render_format);
      } else if (resolved.status === 'failed') {
        toast.error(resolved.result_message || 'The export job failed.');
      } else {
        toast.success('Export job queued.');
      }
    } catch (error) {
      console.error(error);
      toast.error('The export could not be started.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <section data-testid="guided-choice-panel" className="space-y-8 rounded-[40px] border border-slate-200 bg-white p-8 shadow-xl">
      <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="rounded-[28px] border border-slate-200 bg-slate-50 p-6">
          <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-400">Diagnosis Summary</p>
          <p className="mt-3 text-xl font-black text-slate-900">{diagnosis.diagnosis_summary?.overview ?? diagnosis.headline}</p>
          <p className="mt-4 text-sm font-semibold leading-relaxed text-slate-600">
            {diagnosis.diagnosis_summary?.reasoning ?? diagnosis.recommended_focus}
          </p>
        </div>
        <div className="rounded-[28px] border border-slate-200 bg-slate-900 p-6 text-white">
          <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-300">Authenticity Rule</p>
          <p className="mt-3 text-sm font-semibold leading-relaxed text-slate-100">
            {diagnosis.diagnosis_summary?.authenticity_note ??
              'Keep the next draft grounded in the student record and treat open text as optional.'}
          </p>
        </div>
      </div>

      {defaultAction && recommendedDirection ? (
        <div data-testid="guided-default-action" className="rounded-[28px] border border-blue-200 bg-blue-50 p-6">
          <p className="text-[11px] font-black uppercase tracking-[0.18em] text-blue-500">Recommended Start</p>
          <h3 className="mt-3 text-xl font-black text-slate-900">{recommendedDirection.label}</h3>
          <p className="mt-3 text-sm font-semibold leading-relaxed text-slate-700">{defaultAction.rationale}</p>
          <div className="mt-4 flex flex-wrap gap-2 text-xs font-black text-blue-900">
            <span className="rounded-full bg-white px-3 py-2">{defaultAction.export_format.toUpperCase()}</span>
            <span className="rounded-full bg-white px-3 py-2">{defaultAction.page_count} pages</span>
            <span className="rounded-full bg-white px-3 py-2">{defaultAction.template_id}</span>
          </div>
        </div>
      ) : null}

      <div className="space-y-4">
        <div className="flex items-center gap-2 text-slate-900">
          <Sparkles size={18} />
          <h3 className="text-lg font-black">Weak Axes</h3>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {(diagnosis.gap_axes ?? []).map((axis) => (
            <div key={axis.key} className="rounded-[24px] border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">{axis.label}</p>
              <p className="mt-3 text-2xl font-black text-slate-900">{axis.score}</p>
              <p className="mt-2 text-sm font-semibold leading-relaxed text-slate-600">{axis.rationale}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-center gap-2 text-slate-900">
          <Layers3 size={18} />
          <h3 className="text-lg font-black">Recommended Directions</h3>
        </div>
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {directions.map((direction) => (
            <button
              key={direction.id}
              type="button"
              data-testid={`guided-direction-${direction.id}`}
              onClick={() => setSelectedDirectionId(direction.id)}
              className={`rounded-[28px] border p-5 text-left transition-all ${tone(direction.id === selectedDirectionId)}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-black uppercase tracking-[0.14em] opacity-70">{direction.complexity}</p>
                  <h4 className="mt-2 text-lg font-black">{direction.label}</h4>
                </div>
                {direction.id === selectedDirectionId ? <CheckCircle2 size={18} /> : null}
              </div>
              <p className="mt-3 text-sm font-semibold leading-relaxed opacity-90">{direction.summary}</p>
              <p className="mt-4 text-xs font-bold leading-relaxed opacity-70">{direction.why_now}</p>
            </button>
          ))}
        </div>
      </div>

      {selectedDirection ? (
        <div className="space-y-8">
          <div className="grid gap-8 xl:grid-cols-2">
            <div className="space-y-4">
              <h4 className="text-sm font-black uppercase tracking-[0.14em] text-slate-500">Topic</h4>
              <div className="space-y-3">
                {topicCandidates.map((topic) => (
                  <button
                    key={topic.id}
                    type="button"
                    data-testid={`guided-topic-${topic.id}`}
                    onClick={() => setSelectedTopicId(topic.id)}
                    className={`w-full rounded-[24px] border p-4 text-left transition-all ${tone(topic.id === selectedTopicId)}`}
                  >
                    <p className="text-base font-black">{topic.title}</p>
                    <p className="mt-2 text-sm font-semibold opacity-90">{topic.summary}</p>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-6">
              <div className="space-y-3">
                <h4 className="text-sm font-black uppercase tracking-[0.14em] text-slate-500">Page Count</h4>
                <div className="grid gap-3 sm:grid-cols-3">
                  {pageCountOptions.map((option: PageCountOption) => (
                    <button
                      key={option.id}
                      type="button"
                      data-testid={`guided-pages-${option.page_count}`}
                      onClick={() => setSelectedPageCount(option.page_count)}
                      className={`rounded-[20px] border p-4 text-left transition-all ${tone(option.page_count === selectedPageCount)}`}
                    >
                      <p className="text-lg font-black">{option.label}</p>
                      <p className="mt-2 text-xs font-semibold opacity-80">{option.rationale}</p>
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="text-sm font-black uppercase tracking-[0.14em] text-slate-500">Export Format</h4>
                <div className="grid gap-3 sm:grid-cols-3">
                  {formatRecommendations.map((item: FormatRecommendation) => (
                    <button
                      key={item.format}
                      type="button"
                      data-testid={`guided-format-${item.format}`}
                      onClick={() => setSelectedFormat(item.format)}
                      className={`rounded-[20px] border p-4 text-left transition-all ${tone(item.format === selectedFormat)}`}
                    >
                      <div className="flex items-center gap-2">
                        {item.format === 'pptx' ? <Presentation size={16} /> : <FileText size={16} />}
                        <p className="font-black uppercase">{item.format}</p>
                      </div>
                      <p className="mt-2 text-xs font-semibold opacity-80">{item.rationale}</p>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <h4 className="text-sm font-black uppercase tracking-[0.14em] text-slate-500">Template Gallery</h4>
              <div className="flex flex-wrap gap-3 text-xs font-bold text-slate-500">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={includeProvenanceAppendix}
                    onChange={(event) => setIncludeProvenanceAppendix(event.target.checked)}
                  />
                  Include provenance appendix
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={hideInternalProvenance}
                    onChange={(event) => setHideInternalProvenance(event.target.checked)}
                  />
                  Hide internal provenance IDs
                </label>
              </div>
            </div>
            <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
              {templateGallery.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  data-testid={`guided-template-${template.id}`}
                  onClick={() => setSelectedTemplateId(template.id)}
                  className={`rounded-[28px] border p-4 text-left transition-all ${tone(template.id === selectedTemplateId)}`}
                >
                  <div
                    className="h-28 rounded-[20px] border border-white/20"
                    style={{ background: `linear-gradient(135deg, ${template.preview.accent_color} 0%, #f8fafc 100%)` }}
                  />
                  <div className="mt-4 flex items-start justify-between gap-3">
                    <div>
                      <p className="text-base font-black">{template.label}</p>
                      <p className="mt-1 text-xs font-bold uppercase tracking-[0.14em] opacity-70">{template.category}</p>
                    </div>
                    {recommendedTemplateIds.has(template.id) ? (
                      <span className="rounded-full border border-current/20 px-2 py-1 text-[10px] font-black uppercase">
                        Recommended
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-3 text-sm font-semibold opacity-90">{template.description}</p>
                  <p className="mt-3 text-xs font-bold opacity-70">
                    {template.preview.preview_sections.join(' / ')}
                  </p>
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <button
              type="button"
              data-testid="guided-build-outline"
              onClick={buildPlan}
              disabled={isGenerating}
              className="rounded-[24px] bg-slate-900 px-7 py-4 text-sm font-black text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isGenerating ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 size={16} className="animate-spin" /> Building outline
                </span>
              ) : (
                'Build guided outline'
              )}
            </button>
            {outline ? (
              <button
                type="button"
                data-testid="guided-export"
                onClick={exportOutline}
                disabled={isExporting}
                className="rounded-[24px] border border-slate-900 px-7 py-4 text-sm font-black text-slate-900 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isExporting ? 'Exporting...' : 'Export with selected template'}
              </button>
            ) : null}
          </div>

          {outline ? (
            <div data-testid="guided-outline-preview" className="rounded-[32px] border border-slate-200 bg-slate-50 p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">Outline Preview</p>
                  <h4 className="mt-2 text-2xl font-black text-slate-900">{outline.title}</h4>
                  <p className="mt-2 text-sm font-semibold text-slate-600">{outline.summary}</p>
                </div>
                <div className="rounded-[20px] border border-slate-200 bg-white px-4 py-3 text-right">
                  <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-400">{outline.export_format}</p>
                  <p className="mt-1 text-sm font-bold text-slate-700">{outline.template_label}</p>
                </div>
              </div>
              <div className="mt-6 grid gap-4 lg:grid-cols-2">
                {outline.sections.map((section) => (
                  <div key={section.id} className="rounded-[24px] border border-slate-200 bg-white p-4">
                    <p className="text-sm font-black text-slate-900">{section.title}</p>
                    <p className="mt-2 text-sm font-semibold leading-relaxed text-slate-600">{section.purpose}</p>
                    <div className="mt-3 space-y-1 text-xs font-bold text-slate-500">
                      {section.evidence_plan.map((item) => (
                        <p key={item}>- {item}</p>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              {lastRenderJob?.download_url ? (
                <button
                  type="button"
                  data-testid="guided-download-latest"
                  onClick={() => {
                    void downloadRenderedArtifact(lastRenderJob.download_url || '', lastRenderJob.render_format);
                  }}
                  className="mt-6 inline-flex rounded-[20px] bg-slate-900 px-5 py-3 text-sm font-black text-white"
                >
                  Download latest export
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
