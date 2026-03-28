import React from 'react';
import { motion } from 'framer-motion';
import { ShieldCheck, Scale, Info, CheckCircle2 } from 'lucide-react';

interface LegalSectionProps {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}

function LegalSection({ title, icon, children }: LegalSectionProps) {
  return (
    <div className="mb-12">
      <div className="flex items-center gap-3 mb-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 shadow-sm border border-blue-100">
          {icon}
        </div>
        <h2 className="text-xl font-black text-slate-800 tracking-tight">{title}</h2>
      </div>
      <div className="space-y-4 text-[15px] leading-relaxed text-slate-600 font-medium pl-13">
        {children}
      </div>
    </div>
  );
}

export function TermsOfService() {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-4xl mx-auto py-16 px-6"
    >
      <div className="mb-16 text-center">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-slate-100 text-slate-500 rounded-full text-xs font-black mb-4 tracking-widest uppercase">
          Service Policy
        </div>
        <h1 className="text-4xl md:text-5xl font-black text-slate-900 tracking-tight mb-6">이용약관</h1>
        <p className="text-lg text-slate-500 font-medium">Uni Folia는 투명하고 책임감 있는 AI 교육 서비스를 제공합니다.</p>
      </div>

      <div className="bg-white rounded-[2.5rem] border border-slate-100 p-10 md:p-16 shadow-xl shadow-slate-200/50">
        <LegalSection title="서비스의 본질" icon={<Scale size={20} />}>
          <p>Uni Folia는 학생의 학습 기록과 성취를 체계적으로 정리하고 성찰할 수 있도록 돕는 AI 기반 교육 서비스입니다.</p>
          <div className="flex items-start gap-4 bg-amber-50/50 rounded-2xl p-6 border border-amber-100/50">
            <Info className="text-amber-500 shrink-0 mt-1" size={20} />
            <p className="text-amber-700 text-sm font-bold">
              주의: Uni Folia는 특정 대학교의 합격을 보장하지 않으며, 입시 결과에 대한 법적 책임을 지지 않습니다. 대학 입학 결정은 각 교육 기관의 고유 권한입니다.
            </p>
          </div>
        </LegalSection>

        <LegalSection title="저작권 및 소유권" icon={<ShieldCheck size={20} />}>
          <p>학생이 직접 입력하거나 작성한 모든 텍스트와 데이터의 소유권은 전적으로 학생 본인에게 있습니다.</p>
          <ul className="space-y-3 list-none">
            {[
              "사용자가 입력한 원본 자료(Original Data)의 권리는 사용자에게 귀속됩니다.",
              "AI가 제안한 내용은 사용자가 이를 검토하고 승인한 시점부터 기록물의 일부로 간주됩니다.",
              "Uni Folia는 사용자의 허가 없이 사용자의 데이터를 외부에 공개하거나 상업적으로 재판매하지 않습니다."
            ].map(item => (
              <li key={item} className="flex items-start gap-3">
                <CheckCircle2 size={16} className="text-blue-500 mt-1 shrink-0" />
                <span className="text-slate-600">{item}</span>
              </li>
            ))}
          </ul>
        </LegalSection>

        <LegalSection title="금지 사항" icon={<CheckCircle2 size={20} />}>
          <p>사용자는 다음과 같은 목적으로 서비스를 이용할 수 없습니다.</p>
          <ul className="space-y-2">
            <li>• 타인의 개인정보 또는 학업 기록을 무단으로 도용하는 행위</li>
            <li>• 실현되지 않은 허위 사실을 날조하여 기록물에 포함시키는 행위</li>
            <li>• 서비스의 정상적인 운영을 방해하거나 AI 알고리즘을 악용하는 행위</li>
          </ul>
        </LegalSection>

        <div className="mt-20 pt-10 border-t border-slate-100 text-sm text-slate-400 font-medium text-center">
          최종 업데이트: 2026년 3월 29일
        </div>
      </div>
    </motion.div>
  );
}

export function PrivacyPolicy() {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-4xl mx-auto py-16 px-6"
    >
      <div className="mb-16 text-center">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-blue-50 text-blue-600 rounded-full text-xs font-black mb-4 tracking-widest uppercase">
          Transparency & Safety
        </div>
        <h1 className="text-4xl md:text-5xl font-black text-slate-900 tracking-tight mb-6">개인정보 처리방침</h1>
        <p className="text-lg text-slate-500 font-medium">데이터 보호는 Uni Folia의 최우선 가치입니다.</p>
      </div>

      <div className="bg-white rounded-[2.5rem] border border-slate-100 p-10 md:p-16 shadow-xl shadow-slate-200/50">
        <LegalSection title="수집하는 정보" icon={<ShieldCheck size={20} />}>
          <p>Uni Folia는 서비스 제공을 위해 필요한 최소한의 정보를 수집합니다.</p>
          <ul className="space-y-4">
            <li>
              <span className="font-black text-slate-700 block mb-1">필수 정보:</span>
              이메일 주소, 학년, 목표 대학교 및 전공 (맞춤형 상담을 위해 필요)
            </li>
            <li>
              <span className="font-black text-slate-700 block mb-1">학업 데이터:</span>
              사용자가 업로드한 성적표(선택), 활동 내역 및 작성 중인 보고서 초안
            </li>
          </ul>
        </LegalSection>

        <LegalSection title="AI 처리 및 보안" icon={<Info size={20} />}>
          <div className="p-6 bg-slate-50 rounded-2xl border border-slate-100 mb-6">
            <h3 className="font-black text-slate-800 mb-2">중요: AI 데이터 불활용 원칙</h3>
            <p className="text-sm text-slate-600 font-bold">
              Uni Folia는 사용자의 학업 데이터를 거대 언어 모델(LLM)의 기본 학습 데이터로 활용하지 않습니다. 
              AI 파트너사(Google Cloud Vertex AI 등)와의 보안 규약을 통해 전송된 데이터는 오직 사용자의 실시간 요청 처리를 위해서만 사용됩니다.
            </p>
          </div>
          <ul className="space-y-3">
            <li className="flex items-start gap-3">
              <CheckCircle2 size={16} className="text-blue-500 mt-1 shrink-0" />
              <span>모든 데이터는 전송 시 SSL 암호화 처리됩니다.</span>
            </li>
            <li className="flex items-start gap-3">
              <CheckCircle2 size={16} className="text-blue-500 mt-1 shrink-0" />
              <span>Firebase 및 Google Cloud 인프라를 통해 안전하게 관리됩니다.</span>
            </li>
          </ul>
        </LegalSection>

        <LegalSection title="파기 절차" icon={<CheckCircle2 size={20} />}>
          <p>사용자가 계정 탈퇴를 요청하거나 개인정보 이용 목적이 달성된 경우, 해당 정보는 즉시 또는 관계 법령에 따른 보존 기간 이후 즉각 파기됩니다.</p>
        </LegalSection>

        <div className="mt-20 pt-10 border-t border-slate-100 text-sm text-slate-400 font-medium text-center">
          최종 업데이트: 2026년 3월 29일
        </div>
      </div>
    </motion.div>
  );
}
