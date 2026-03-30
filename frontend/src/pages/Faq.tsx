import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, CheckCircle2 } from 'lucide-react';
import { FaqAccordion } from '../components/FaqAccordion';
import { faqItems } from '../content/faq';

const categories = Array.from(new Set(faqItems.map(item => item.category)));

export function Faq() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8">
      <section className="rounded-[40px] border border-slate-200 bg-white p-8 shadow-sm sm:p-10">
        <p className="text-sm font-black uppercase tracking-[0.22em] text-blue-600">FAQ</p>
        <h1 className="mt-3 text-4xl font-black tracking-tight text-slate-900 sm:text-5xl">
          Uni Folia를 이해하는 데 필요한 질문을 정리했습니다.
        </h1>
        <p className="mt-5 max-w-3xl text-base font-medium leading-8 text-slate-600">
          서비스 개요, 게스트 사용, 기록 처리, 안전 원칙, 협업 문의까지 현재 제품 방향과 운영 상태에 맞춰 과장 없이 안내합니다.
        </p>

        <div className="mt-8 flex flex-wrap gap-3">
          {categories.map(category => (
            <span key={category} className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-bold text-slate-600">
              {category}
            </span>
          ))}
        </div>
      </section>

      <section className="mt-10">
        <FaqAccordion items={faqItems} initialOpenId={faqItems[0]?.id} />
      </section>

      <section className="mt-12 rounded-[36px] border border-blue-100 bg-blue-50 p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="mt-1 flex h-10 w-10 items-center justify-center rounded-2xl bg-white text-blue-600 shadow-sm">
              <CheckCircle2 size={18} />
            </div>
            <div>
              <h2 className="text-2xl font-black tracking-tight text-slate-900">원하는 답이 없다면 문의 허브로 연결하세요.</h2>
              <p className="mt-2 text-sm font-medium leading-7 text-slate-600">
                1:1 문의, 협업/도입 문의, 버그·기능 제안을 구분해서 보낼 수 있습니다.
              </p>
            </div>
          </div>
          <Link
            to="/contact"
            className="inline-flex items-center justify-center gap-2 rounded-full bg-slate-900 px-6 py-4 text-sm font-black text-white shadow-lg shadow-slate-900/10"
          >
            문의하기
            <ArrowRight size={16} />
          </Link>
        </div>
      </section>
    </main>
  );
}
