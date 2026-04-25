import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { BookOpen, Check, ChevronLeft, Download, FileText, Loader2, Save } from 'lucide-react';
import toast from 'react-hot-toast';
import type { JSONContent } from '@tiptap/react';
import { api } from '../lib/api';
import { TiptapEditor, type TiptapEditorHandle } from '../components/editor/TiptapEditor';
import { ExportModal } from '../components/editor/ExportModal';
import { PrimaryButton, SecondaryButton, StatusBadge } from '../components/primitives';

interface Draft {
  id: string;
  project_id: string;
  title: string;
  content_markdown: string;
  content_json: string | null;
  status: string;
}

interface EditorLocationState {
  seedMarkdown?: string;
}

const LOCAL_DRAFT_TITLE = '새 탐구 보고서 (오프라인)';

export function DocumentEditorPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const [draft, setDraft] = useState<Draft | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [isExportOpen, setIsExportOpen] = useState(false);

  const editorRef = useRef<TiptapEditorHandle>(null);
  const pendingContentRef = useRef<JSONContent | null>(null);
  const saveTimerRef = useRef<number | null>(null);

  const seedMarkdown = ((location.state as EditorLocationState | null)?.seedMarkdown || '').trim();
  const isLocalMode = !projectId || projectId === 'demo' || projectId === 'undefined';

  useEffect(() => {
    async function load() {
      setIsLoading(true);

      if (isLocalMode) {
        setDraft({
          id: 'local',
          project_id: projectId ?? 'demo',
          title: LOCAL_DRAFT_TITLE,
          content_markdown: seedMarkdown,
          content_json: null,
          status: 'in_progress',
        });
        setIsLoading(false);
        return;
      }

      try {
        const drafts = await api.get<Draft[]>(`/api/v1/projects/${projectId}/drafts`);

        if (drafts && drafts.length > 0) {
          setDraft(drafts[0]);
        } else {
          const newDraft = await api.post<Draft>(`/api/v1/projects/${projectId}/drafts`, {
            title: '새 탐구 보고서',
            content_markdown: seedMarkdown,
            content_json: null,
          });
          setDraft(newDraft);
        }
      } catch (err) {
        console.error('Load draft failed:', err);
        setDraft({
          id: 'local',
          project_id: projectId ?? 'demo',
          title: LOCAL_DRAFT_TITLE,
          content_markdown: seedMarkdown,
          content_json: null,
          status: 'in_progress',
        });
      } finally {
        setIsLoading(false);
      }
    }

    void load();
  }, [isLocalMode, projectId, seedMarkdown]);

  const flushSave = useCallback(async () => {
    const content = pendingContentRef.current;

    if (!content || !projectId || !draft || draft.id === 'local') {
      return;
    }
    if (isSaving) {
      return;
    }

    setIsSaving(true);
    try {
      await api.patch(`/api/v1/projects/${projectId}/drafts/${draft.id}`, {
        content_json: JSON.stringify(content),
      });
      setLastSaved(new Date());
      pendingContentRef.current = null;
    } catch (err) {
      console.error('Auto-save failed:', err);
    } finally {
      setIsSaving(false);
    }
  }, [draft, isSaving, projectId]);

  const handleEditorUpdate = useCallback(
    (json: JSONContent) => {
      pendingContentRef.current = json;
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);

      if (draft?.id === 'local') {
        setLastSaved(new Date());
        return;
      }

      saveTimerRef.current = window.setTimeout(() => {
        void flushSave();
      }, 2000);
    },
    [draft?.id, flushSave],
  );

  const handleManualSave = useCallback(async () => {
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);

    const json = editorRef.current?.getJSON();
    if (json) pendingContentRef.current = json;

    if (draft?.id === 'local') {
      setLastSaved(new Date());
      toast.success('오프라인 상태로 임시 저장되었습니다.');
      return;
    }

    await flushSave();
    toast.success('문서를 저장했습니다.');
  }, [draft?.id, flushSave]);

  useEffect(
    () => () => {
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    },
    [],
  );

  const initialContent = (() => {
    if (!draft?.content_json) {
      return draft?.content_markdown || seedMarkdown || null;
    }

    try {
      return JSON.parse(draft.content_json) as JSONContent;
    } catch (error) {
      console.error('Failed to parse saved editor JSON:', error);
      return draft.content_markdown || seedMarkdown || null;
    }
  })();
  const editorStatus = isSaving
    ? { tone: 'active' as const, label: 'Saving...' }
    : lastSaved
      ? { tone: 'success' as const, label: `Saved ${lastSaved.toLocaleTimeString()}` }
      : isLocalMode
        ? { tone: 'warning' as const, label: 'Local mode' }
        : { tone: 'neutral' as const, label: 'Autosave enabled' };

  if (isLoading) {
    return (
      <div className="flex h-[80vh] w-full items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#004aad]/5">
              <FileText size={28} className="text-[#004aad]" />
            </div>
            <Loader2 size={20} className="absolute -right-1 -bottom-1 animate-spin text-[#004aad]" />
          </div>
          <p className="text-sm font-medium text-slate-500">문서를 준비하고 있습니다...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-[100dvh] flex-col overflow-hidden bg-slate-50">
      <header className="sticky top-0 z-30 flex h-14 w-full shrink-0 items-center justify-between border-b border-slate-200 bg-white/95 px-3 backdrop-blur sm:px-4">
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          <button
            onClick={() => navigate(-1)}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition hover:bg-slate-50 hover:text-slate-700"
            aria-label="이전 화면으로 이동"
          >
            <ChevronLeft size={18} />
          </button>

          <div className="hidden h-6 w-px bg-slate-200 sm:block" />

          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <BookOpen size={16} className="shrink-0 text-[#004aad]" />
              <h1 className="truncate text-sm font-bold text-slate-900">{draft?.title || '문서 편집기'}</h1>
            </div>
            <div className="mt-1">
              <StatusBadge status={editorStatus.tone}>
                {isSaving ? <Loader2 size={10} className="animate-spin" /> : null}
                {!isSaving && lastSaved ? <Check size={10} /> : null}
                {editorStatus.label}
              </StatusBadge>
            </div>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
          <SecondaryButton size="sm" onClick={() => setIsExportOpen(true)} className="px-2.5 sm:px-3.5">
            <Download size={14} />
            <span className="hidden sm:inline">내보내기</span>
          </SecondaryButton>
          <PrimaryButton size="sm" onClick={() => void handleManualSave()} disabled={isSaving} className="px-2.5 sm:px-3.5">
            <Save size={14} />
            <span className="hidden sm:inline">저장</span>
          </PrimaryButton>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-hidden">
        <TiptapEditor ref={editorRef} initialContent={initialContent} onJsonUpdate={handleEditorUpdate} />
      </main>

      <ExportModal
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        documentTitle={draft?.title || '탐구보고서'}
        getJSON={() => editorRef.current?.getJSON() || { type: 'doc', content: [] }}
        getHTML={() => editorRef.current?.getHTML() || ''}
      />
    </div>
  );
}
