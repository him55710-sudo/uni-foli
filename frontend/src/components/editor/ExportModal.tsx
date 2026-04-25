import React, { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  X,
  FileText,
  FileType2,
  Globe,
  Loader2,
  CheckCircle2,
  Download,
} from 'lucide-react';
import type { JSONContent } from '@tiptap/react';
import toast from 'react-hot-toast';

type ExportFormat = 'pdf' | 'docx' | 'html';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentTitle: string;
  getJSON: () => JSONContent;
  getHTML: () => string;
}

const FORMAT_OPTIONS: Array<{
  id: ExportFormat;
  label: string;
  description: string;
  icon: React.ReactNode;
  badge?: string;
}> = [
  {
    id: 'pdf',
    label: 'PDF',
    description: '인쇄, 제출, 공유에 가장 적합한 형식입니다.',
    icon: <FileText size={22} className="text-red-500" />,
    badge: '추천',
  },
  {
    id: 'docx',
    label: 'DOCX (Word)',
    description: 'Microsoft Word로 추가 편집이 가능합니다.',
    icon: <FileType2 size={22} className="text-[#004aad]" />,
  },
  {
    id: 'html',
    label: 'HTML',
    description: '브라우저에서 바로 열 수 있는 웹 문서입니다.',
    icon: <Globe size={22} className="text-emerald-600" />,
  },
];

export function ExportModal({ isOpen, onClose, documentTitle, getJSON, getHTML }: ExportModalProps) {
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('pdf');
  const [isExporting, setIsExporting] = useState(false);
  const [exportComplete, setExportComplete] = useState(false);
  const [filename, setFilename] = useState(documentTitle || '탐구보고서');

  const handleExport = async () => {
    setIsExporting(true);
    setExportComplete(false);

    try {
      switch (selectedFormat) {
        case 'pdf': {
          const { exportToPdf } = await import('./exporters/exportPdf');
          await exportToPdf({ html: getHTML(), filename });
          break;
        }
        case 'docx': {
          const { exportToDocx } = await import('./exporters/exportDocx');
          await exportToDocx(getJSON(), filename);
          break;
        }
        case 'html': {
          const { exportToHtml } = await import('./exporters/exportHtml');
          exportToHtml(getHTML(), filename);
          break;
        }
      }
      setExportComplete(true);
      toast.success(`${filename}.${selectedFormat} 파일이 다운로드됩니다.`);
      setTimeout(() => {
        onClose();
        setExportComplete(false);
      }, 1500);
    } catch (error) {
      console.error('Export failed:', error);
      toast.error('내보내기에 실패했습니다. 다시 시도해 주세요.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ type: 'spring', duration: 0.4 }}
            className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2"
          >
            <div className="rounded-2xl border border-slate-200 bg-white shadow-2xl">
              {/* Header */}
              <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50">
                    <Download size={18} className="text-[#004aad]" />
                  </div>
                  <div>
                    <h2 className="text-sm font-black text-slate-900">문서 내보내기</h2>
                    <p className="text-[11px] font-medium text-slate-400">
                      형식을 선택하고 다운로드하세요
                    </p>
                  </div>
                </div>
                <button
                  onClick={onClose}
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Body */}
              <div className="space-y-4 px-6 py-5">
                {/* Filename */}
                <div>
                  <label className="mb-1.5 block text-[11px] font-black uppercase tracking-[0.12em] text-slate-500">
                    파일명
                  </label>
                  <input
                    type="text"
                    value={filename}
                    onChange={(e) => setFilename(e.target.value)}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm font-semibold text-slate-800 outline-none transition focus:border-blue-300 focus:bg-white focus:ring-2 focus:ring-blue-100"
                    placeholder="파일명을 입력하세요"
                  />
                </div>

                {/* Format Selection */}
                <div>
                  <label className="mb-1.5 block text-[11px] font-black uppercase tracking-[0.12em] text-slate-500">
                    내보내기 형식
                  </label>
                  <div className="space-y-2">
                    {FORMAT_OPTIONS.map((fmt) => (
                      <button
                        key={fmt.id}
                        type="button"
                        onClick={() => setSelectedFormat(fmt.id)}
                        className={`flex w-full items-center gap-3 rounded-xl border-2 px-4 py-3 text-left transition-all ${
                          selectedFormat === fmt.id
                            ? 'border-blue-500 bg-blue-50/50 shadow-sm'
                            : 'border-slate-100 bg-white hover:border-slate-200 hover:bg-slate-50'
                        }`}
                      >
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white shadow-sm ring-1 ring-slate-100">
                          {fmt.icon}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-bold text-slate-800">{fmt.label}</span>
                            {fmt.badge && (
                              <span className="rounded-md bg-blue-100 px-1.5 py-0.5 text-[9px] font-black text-blue-700">
                                {fmt.badge}
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] font-medium text-slate-400">{fmt.description}</p>
                        </div>
                        <div
                          className={`h-5 w-5 shrink-0 rounded-full border-2 transition ${
                            selectedFormat === fmt.id
                              ? 'border-blue-500 bg-blue-500'
                              : 'border-slate-200'
                          }`}
                        >
                          {selectedFormat === fmt.id && (
                            <div className="flex h-full items-center justify-center">
                              <div className="h-2 w-2 rounded-full bg-white" />
                            </div>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-end gap-2 border-t border-slate-100 px-6 py-4">
                <button
                  onClick={onClose}
                  className="h-10 rounded-xl border border-slate-200 px-4 text-sm font-bold text-slate-600 transition hover:bg-slate-50"
                >
                  취소
                </button>
                <button
                  onClick={handleExport}
                  disabled={isExporting || !filename.trim()}
                  className="flex h-10 items-center gap-2 rounded-xl bg-[#004aad] px-5 text-sm font-bold text-white transition hover:bg-[#003d8f] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isExporting ? (
                    <>
                      <Loader2 size={15} className="animate-spin" />
                      내보내는 중...
                    </>
                  ) : exportComplete ? (
                    <>
                      <CheckCircle2 size={15} />
                      완료!
                    </>
                  ) : (
                    <>
                      <Download size={15} />
                      다운로드
                    </>
                  )}
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
