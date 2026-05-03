import React from 'react';
import { motion } from 'motion/react';
import { FileUp, Loader2, Plus, Send, Settings2, Sparkles, Target } from 'lucide-react';
import { SectionCard, SecondaryButton, WorkflowNotice } from '../primitives';
import { cn } from '../../lib/cn';
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
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="mx-auto max-w-3xl"
    >
      <div className="text-center mb-6">
        <h1 className="text-2xl font-black text-slate-900 mb-2">학생부 분석 시작하기</h1>
      </div>

      <div
        {...getRootProps({
          onClick: handleOpenFileDialog,
          onKeyDown: handleDropzoneKeyDown,
        })}
        className={cn(
          'relative cursor-pointer overflow-hidden rounded-[2.5rem] border-2 border-dashed transition-all duration-300',
          isDragActive
            ? 'border-indigo-500 bg-indigo-50/50 scale-[0.99]'
            : 'border-slate-200 bg-white hover:border-indigo-400 hover:shadow-xl hover:shadow-indigo-100/50',
          isUploading && 'pointer-events-none opacity-60'
        )}
      >
        <input {...getInputProps()} />
        
        <div className="flex flex-col items-center px-8 py-20 sm:py-32">
          <div className="relative mb-10">
            <div className="absolute inset-0 animate-ping rounded-[2rem] bg-indigo-200 opacity-20" />
            <div className="relative flex h-20 w-20 items-center justify-center rounded-[2rem] bg-indigo-600 text-white shadow-xl shadow-indigo-200">
              {isUploading ? (
                <Loader2 size={36} className="animate-spin" />
              ) : (
                <FileUp size={36} strokeWidth={1.5} />
              )}
            </div>
          </div>

          <div className="space-y-4">
            <h2 className="text-2xl font-bold text-slate-900">
              {isDragActive ? '파일을 여기에 놓으세요' : 'PDF 파일을 마우스로 끌어오세요'}
            </h2>
            <div className="flex flex-wrap justify-center gap-3">
               <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-4 py-1.5 text-sm font-bold text-slate-600">
                <Settings2 size={14} />
                최대 50MB
               </span>
               <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-4 py-1.5 text-sm font-bold text-slate-600">
                <FileUp size={14} />
                PDF 형식
               </span>
            </div>
          </div>

          <button
            type="button"
            className="mt-12 rounded-2xl bg-indigo-600 px-10 py-4 text-base font-bold text-white shadow-lg shadow-indigo-200 transition-all hover:bg-indigo-700 active:scale-95"
          >
            내 컴퓨터에서 찾기
          </button>
        </div>
      </div>



      {flowError && (
        <div className="mt-8">
          <WorkflowNotice tone="danger" title="업로드 실패" description={flowError} />
        </div>
      )}
    </motion.div>
  );
};
