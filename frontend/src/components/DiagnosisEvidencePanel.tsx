import React from 'react';
import { AlertTriangle, FileSearch, ShieldCheck } from 'lucide-react';
import {
  type DiagnosisCitation,
  type DiagnosisPolicyFlag,
} from '../lib/diagnosis';

interface DiagnosisEvidencePanelProps {
  citations: DiagnosisCitation[];
  reviewRequired: boolean;
  policyFlags: DiagnosisPolicyFlag[];
  responseTraceId?: string | null;
}

function severityTone(severity: string): string {
  switch (severity.toLowerCase()) {
    case 'critical':
      return 'border-red-200 bg-red-50 text-red-700';
    case 'high':
      return 'border-amber-200 bg-amber-50 text-amber-700';
    default:
      return 'border-slate-200 bg-slate-50 text-slate-600';
  }
}

export function DiagnosisEvidencePanel({
  citations,
  reviewRequired,
  policyFlags,
  responseTraceId,
}: DiagnosisEvidencePanelProps) {
  if (!citations.length && !reviewRequired && !policyFlags.length && !responseTraceId) {
    return null;
  }

  return (
    <div data-testid="diagnosis-evidence-panel" className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
      <section className="rounded-[32px] border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
            <FileSearch size={20} />
          </div>
          <div>
            <h3 className="text-lg font-black text-slate-800">근거 데이터 확인</h3>
            <p className="text-xs font-bold text-slate-400">
              AI 진단 결과는 실제 업로드된 학생부 기록(근거)에 기반하여 작성됩니다.
            </p>
          </div>
        </div>
 
        <div className="mt-5 space-y-4">
          {citations.length ? (
            citations.map((citation) => (
              <article
                key={`${citation.document_chunk_id || citation.source_label}-${citation.page_number || 'na'}`}
                className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[10px] font-black uppercase tracking-widest text-slate-400">
                    {citation.source_label}
                  </span>
                  {citation.page_number ? (
                    <span className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-[10px] font-black text-blue-600">
                      {citation.page_number}페이지
                    </span>
                  ) : null}
                  <span className="rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1 text-[10px] font-black text-emerald-600">
                    근거 신뢰도 {Math.round(citation.relevance_score * 100)}%
                  </span>
                </div>
                <p className="mt-3 text-sm font-bold leading-relaxed text-slate-600 italic">" {citation.excerpt} "</p>
              </article>
            ))
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-4 text-sm font-bold text-slate-400">
              추출된 근거 데이터가 없습니다. 기록이 더 쌓인 뒤 다시 진단을 시도해 보세요.
            </div>
          )}
        </div>
      </section>
 
      <section
        data-testid="diagnosis-review-panel"
        className="rounded-[32px] border border-slate-200 bg-white p-6 shadow-sm"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600">
            <ShieldCheck size={20} />
          </div>
          <div>
            <h3 className="text-lg font-black text-slate-800">안전성 및 투명성</h3>
            <p className="text-xs font-bold text-slate-400">
              시스템이 권장하는 검토 필요 사항과 추적 정보를 확인합니다.
            </p>
          </div>
        </div>
 
        <div className="mt-5 space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm font-medium text-slate-700">
            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-400">검토 상태 (Review posture)</p>
            <p className="mt-2 font-black text-slate-600">
              {reviewRequired ? '⚠️ AI 진단 결과에 대한 추가적인 수동 검토가 권장됩니다.' : '정상: 추가적인 검토 플래그가 없습니다.'}
            </p>
            {responseTraceId ? (
              <p className="mt-2 break-all text-[10px] font-bold text-slate-300">Trace ID: {responseTraceId}</p>
            ) : null}
          </div>
 
          {policyFlags.length ? (
            policyFlags.map((flag) => (
              <article
                key={flag.id}
                className={`rounded-2xl border p-4 text-sm ${severityTone(flag.severity)}`}
              >
                <div className="flex items-start gap-3">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                  <div>
                    <p className="font-extrabold">{flag.code}</p>
                    <p className="mt-2 font-medium leading-relaxed">{flag.detail}</p>
                  </div>
                </div>
              </article>
            ))
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-4 text-sm font-bold text-slate-400">
              이 진단 실행에서 감지된 정책 위반 사항이 없습니다.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
