import React from 'react';
import { motion } from 'motion/react';
import { FileUp, Plus, Send, Settings2 } from 'lucide-react';
import { SectionCard, SecondaryButton, WorkflowNotice } from '../primitives';
import {
  buildPreUploadGuideReply,
  PRE_UPLOAD_GUIDE_OPENING,
  PRE_UPLOAD_GUIDE_QUICK_ACTIONS,
  type PreUploadQuickAction,
} from '../../lib/preUploadDiagnosisGuide';

interface DiagnosisUploadProps {
  getRootProps: any;
  getInputProps: any;
  isDragActive: boolean;
  isUploading: boolean;
  handleOpenFileDialog: () => void;
  handleDropzoneKeyDown: (e: React.KeyboardEvent<HTMLDivElement>) => void;
  setStep: (step: any) => void;
  flowError: string | null;
  targetMajor?: string | null;
}

type GuideRole = 'assistant' | 'user';

interface GuideMessage {
  id: string;
  role: GuideRole;
  text: string;
}

function createGuideMessage(role: GuideRole, text: string): GuideMessage {
  return {
    id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    text,
  };
}

export const DiagnosisUpload: React.FC<DiagnosisUploadProps> = ({
  getRootProps,
  getInputProps,
  isDragActive,
  isUploading,
  handleOpenFileDialog,
  handleDropzoneKeyDown,
  setStep,
  flowError,
  targetMajor,
}) => {
  const [guideInput, setGuideInput] = React.useState('');
  const [currentConcern, setCurrentConcern] = React.useState<string | null>(null);
  const [guideMessages, setGuideMessages] = React.useState<GuideMessage[]>(() => [
    createGuideMessage('assistant', PRE_UPLOAD_GUIDE_OPENING),
  ]);

  const appendGuideExchange = React.useCallback((
    userText: string,
    concernText: string | null,
  ) => {
    const reply = buildPreUploadGuideReply({
      input: userText,
      targetMajor: targetMajor || null,
      currentConcern: concernText,
    });

    setGuideMessages((previous) => [
      ...previous,
      createGuideMessage('user', userText),
      createGuideMessage('assistant', reply.message),
    ].slice(-8));

    if (!reply.offTopicRedirected && !currentConcern) {
      const normalizedConcern = userText.trim().slice(0, 80);
      if (normalizedConcern) {
        setCurrentConcern(normalizedConcern);
      }
    }

    return reply;
  }, [currentConcern, targetMajor]);

  const handleQuickAction = React.useCallback((action: PreUploadQuickAction) => {
    const concernSeed = currentConcern || (action.id === 'upload_record' ? null : action.label);
    if (!currentConcern && concernSeed) {
      setCurrentConcern(concernSeed);
    }

    const reply = appendGuideExchange(action.label, concernSeed);
    if (action.id === 'upload_record' && !isUploading) {
      handleOpenFileDialog();
      if (!reply.offTopicRedirected) {
        setGuideMessages((previous) => [
          ...previous,
          createGuideMessage('assistant', '파일 선택 창을 열었습니다. 학생부 PDF 1개를 선택해 주세요.'),
        ].slice(-8));
      }
    }
  }, [appendGuideExchange, currentConcern, handleOpenFileDialog, isUploading]);

  const handleGuideSend = React.useCallback(() => {
    const trimmed = guideInput.trim();
    if (!trimmed || isUploading) return;
    appendGuideExchange(trimmed, currentConcern);
    setGuideInput('');
  }, [appendGuideExchange, currentConcern, guideInput, isUploading]);

  return (
    <motion.div
      key="upload"
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
    >
      <SectionCard
        title="학생부 PDF 등록"
        description="PDF 1개만 업로드하면 자동으로 파싱과 진단이 시작됩니다."
        className="overflow-hidden border-none bg-white/60 shadow-xl backdrop-blur-2xl ring-1 ring-white/50"
        actions={(
          <SecondaryButton
            size="sm"
            onClick={() => setStep('GOALS')}
            className="border-white/50 bg-white/50 backdrop-blur-sm"
          >
            <Settings2 size={14} className="mr-1.5" />
            목표 대학/전공 수정
          </SecondaryButton>
        )}
      >
        <div className="flex flex-wrap gap-2">
          <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-bold text-slate-600">
            PDF 1개
          </span>
          <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-bold text-slate-600">
            최대 50MB
          </span>
          <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-bold text-slate-600">
            업로드 후 자동 분석
          </span>
        </div>

        <div className="rounded-[1.75rem] border border-slate-200 bg-white/85 p-5 shadow-sm">
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full border border-[#004aad]/20 bg-[#004aad]/5 px-3 py-1 text-xs font-bold text-[#004aad]">
              업로드 전 사전 가이드
            </span>
            <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-600">
              목표 전공: {targetMajor?.trim() ? targetMajor : '아직 미설정'}
            </span>
            <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-600">
              현재 고민: {currentConcern?.trim() ? currentConcern : '아직 미입력'}
            </span>
          </div>

          <div className="mt-4 max-h-64 space-y-3 overflow-y-auto rounded-2xl border border-slate-200 bg-slate-50 p-3">
            {guideMessages.map((message) => (
              <div
                key={message.id}
                className={`rounded-xl px-3 py-2 text-sm leading-6 ${
                  message.role === 'assistant'
                    ? 'border border-slate-200 bg-white text-slate-700'
                    : 'border border-[#004aad]/30 bg-[#004aad] text-white'
                }`}
              >
                <p className="mb-1 text-[11px] font-black uppercase tracking-wide opacity-70">
                  {message.role === 'assistant' ? 'Consultant' : 'You'}
                </p>
                <p className="whitespace-pre-wrap">{message.text}</p>
              </div>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {PRE_UPLOAD_GUIDE_QUICK_ACTIONS.map((action) => (
              <button
                key={action.id}
                type="button"
                onClick={() => handleQuickAction(action)}
                disabled={isUploading}
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 transition-colors hover:border-[#004aad]/30 hover:bg-[#004aad]/5 hover:text-[#004aad] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {action.label}
              </button>
            ))}
          </div>

          <div className="mt-3 flex items-center gap-2">
            <input
              value={guideInput}
              onChange={(event) => setGuideInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== 'Enter' || event.shiftKey) return;
                event.preventDefault();
                handleGuideSend();
              }}
              placeholder="현재 고민을 한 줄로 입력하세요."
              disabled={isUploading}
              className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm font-medium text-slate-800 outline-none transition-colors placeholder:text-slate-400 focus:border-[#004aad]"
            />
            <button
              type="button"
              onClick={handleGuideSend}
              disabled={!guideInput.trim() || isUploading}
              className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-[#004aad] text-white transition-colors hover:bg-[#00398f] disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              <Send size={16} />
            </button>
          </div>

          <p className="mt-2 text-xs font-medium text-slate-500">
            업로드 전에는 학생부를 분석하지 않습니다. PDF 업로드 후에만 근거 기반 진단이 가능합니다.
          </p>
        </div>

        <div
          {...getRootProps({
            onClick: handleOpenFileDialog,
            onKeyDown: handleDropzoneKeyDown,
          })}
          className={`group relative mt-6 cursor-pointer overflow-hidden rounded-[2rem] border-2 border-dashed transition-all duration-300 ${
            isDragActive
              ? 'scale-[0.99] border-[#004aad] bg-[#004aad]/5'
              : 'border-slate-200 bg-white hover:border-[#004aad]/40 hover:shadow-2xl hover:shadow-blue-500/10'
          } ${isUploading ? 'pointer-events-none opacity-60' : ''}`}
        >
          <input data-testid="diagnosis-upload-input" {...getInputProps()} />

          <div className="flex flex-col items-center px-6 py-12 text-center sm:py-20">
            <div className="relative mb-8">
              <div className="absolute inset-0 animate-ping rounded-full bg-blue-400 opacity-20" />
              <div className="relative flex h-24 w-24 items-center justify-center rounded-3xl bg-gradient-to-br from-[#004aad] to-[#0070f3] text-white shadow-lg shadow-blue-500/20">
                {isUploading ? (
                  <div className="w-12">
                    <div className="h-2 overflow-hidden rounded-full bg-white/20">
                      <motion.div
                        className="h-full rounded-full bg-white"
                        animate={{ x: ['-100%', '100%'] }}
                        transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
                      />
                    </div>
                  </div>
                ) : (
                  <FileUp size={42} className="transition-transform duration-300 group-hover:-translate-y-1" />
                )}
              </div>
            </div>

            <h3 className="text-2xl font-black tracking-tight text-slate-900 sm:text-3xl">
              PDF를 <span className="text-[#004aad]">바로 올려 주세요</span>
            </h3>
            <p className="mt-4 max-w-md text-base font-medium leading-7 text-slate-500 sm:text-lg">
              드래그하거나 버튼을 눌러 파일을 선택하면 즉시 진단 파이프라인이 시작됩니다.
            </p>

            <button
              type="button"
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                handleOpenFileDialog();
              }}
              disabled={isUploading}
              className="mt-10 flex items-center gap-3 rounded-2xl bg-slate-900 px-8 py-4 text-base font-bold text-white shadow-xl shadow-slate-200 ring-offset-2 transition-all hover:bg-slate-800 hover:ring-2 hover:ring-slate-900 active:scale-95 disabled:opacity-50"
            >
              <Plus size={20} />
              PDF 선택하기
            </button>

            <div className="mt-5 flex flex-wrap justify-center gap-2 text-xs font-bold text-slate-500">
              <span className="rounded-full bg-slate-100 px-3 py-1">텍스트 추출</span>
              <span className="rounded-full bg-slate-100 px-3 py-1">근거 정리</span>
              <span className="rounded-full bg-slate-100 px-3 py-1">진단 생성</span>
            </div>
          </div>
        </div>

        {flowError ? (
          <div className="mt-6">
            <WorkflowNotice tone="danger" title="작업 중 오류 발생" description={flowError} />
          </div>
        ) : null}
      </SectionCard>
    </motion.div>
  );
};
