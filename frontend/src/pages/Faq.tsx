import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, CheckCircle2 } from 'lucide-react';
import { FaqAccordion } from '../components/FaqAccordion';
import { faqItems } from '../content/faq';
import { cn } from '../lib/cn';

const categories = Array.from(new Set(faqItems.map(item => item.category)));

const keywordChips: Array<{ id: string; label: string; faqIds: string[] }> = [
  { id: 'start', label: '처음 시작', faqIds: ['service-1', 'service-2'] },
  { id: 'upload', label: '파일 업로드', faqIds: ['upload-1', 'upload-2'] },
  { id: 'privacy', label: '개인정보', faqIds: ['privacy-1'] },
  { id: 'goal', label: '목표 설정', faqIds: ['goal-1'] },
  { id: 'diagnosis', label: '진단', faqIds: ['diagnosis-1'] },
  { id: 'writing', label: '문서 작성', faqIds: ['writing-1'] },
  { id: 'login', label: '로그인', faqIds: ['account-1'] },
  { id: 'pricing', label: '요금제', faqIds: ['plan-1'] },
  { id: 'support', label: '문의 방법', faqIds: ['contact-1'] },
  { id: 'school', label: '학교/학원', faqIds: ['school-1'] },
];

export function Faq() {
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [activeKeyword, setActiveKeyword] = useState<string | null>(null);

  const keywordFaqIdSet = useMemo(() => {
    if (!activeKeyword) return null;
    const found = keywordChips.find(chip => chip.id === activeKeyword);
    return new Set(found?.faqIds ?? []);
  }, [activeKeyword]);

  const filteredItems = useMemo(() => {
    let base = activeCategory ? faqItems.filter(item => item.category === activeCategory) : faqItems;
    if (keywordFaqIdSet) {
      base = base.filter(item => keywordFaqIdSet.has(item.id));
    }
    return base;
  }, [activeCategory, keywordFaqIdSet]);

  const relatedQuestionExamples = useMemo(() => {
    if (!activeKeyword) return [];
    const found = keywordChips.find(chip => chip.id === activeKeyword);
    if (!found) return [];
    return faqItems.filter(item => found.faqIds.includes(item.id)).map(item => item.question);
  }, [activeKeyword]);

  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14 lg:px-8 lg:py-16">
      <section className="rounded-[34px] border border-slate-200 bg-white p-6 shadow-sm sm:p-10">
        <p className="text-sm font-black uppercase tracking-[0.22em] text-blue-600">FAQ</p>
        <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-900 sm:text-5xl break-keep">
          자주 묻는 질문을 한눈에 정리했어요.
        </h1>
        <p className="mt-5 max-w-3xl text-sm font-medium leading-7 text-slate-600 sm:text-base sm:leading-8 break-keep">
          서비스 이용, 파일 업로드, 로그인, 문의 방법까지 많이 물어보는 내용을 학생 눈높이에 맞춰 간단하게 정리했습니다.
        </p>

        <div className="mt-8">
          <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">키워드 10개</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={() => setActiveKeyword(null)}
              className={cn(
                'rounded-full border px-4 py-2 text-sm font-bold transition-all',
                activeKeyword === null
                  ? 'border-blue-600 bg-blue-50 text-blue-700 shadow-sm'
                  : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100',
              )}
            >
              전체 보기
            </button>
            {keywordChips.map(chip => (
              <button
                key={chip.id}
                onClick={() => setActiveKeyword(chip.id)}
                className={cn(
                  'rounded-full border px-4 py-2 text-sm font-bold transition-all',
                  activeKeyword === chip.id
                    ? 'border-blue-600 bg-blue-50 text-blue-700 shadow-sm'
                    : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100',
                )}
              >
                {chip.label}
              </button>
            ))}
          </div>
        </div>

        {activeKeyword ? (
          <div className="mt-5 rounded-2xl border border-blue-100 bg-blue-50 p-4">
            <p className="text-sm font-black text-blue-800">관련 질문 사례</p>
            <div className="mt-2 grid gap-2">
              {relatedQuestionExamples.map(question => (
                <p key={question} className="text-sm font-medium text-blue-900 break-keep">
                  - {question}
                </p>
              ))}
            </div>
          </div>
        ) : null}

        <div className="mt-8">
          <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">카테고리</p>
          <div className="mt-3 flex flex-wrap gap-3">
            <button
              onClick={() => setActiveCategory(null)}
              className={cn(
                'rounded-full border px-4 py-2 text-sm font-bold transition-all',
                activeCategory === null
                  ? 'border-blue-600 bg-blue-50 text-blue-700 shadow-sm'
                  : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100',
              )}
            >
              전체
            </button>
            {categories.map(category => (
              <button
                key={category}
                onClick={() => setActiveCategory(category)}
                className={cn(
                  'rounded-full border px-4 py-2 text-sm font-bold transition-all',
                  activeCategory === category
                    ? 'border-blue-600 bg-blue-50 text-blue-700 shadow-sm'
                    : 'border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100',
                )}
              >
                {category}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-8 sm:mt-10">
        {filteredItems.length ? (
          <FaqAccordion
            items={filteredItems}
            key={`${activeCategory ?? 'all'}-${activeKeyword ?? 'all'}`}
            initialOpenId={filteredItems[0]?.id}
          />
        ) : (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center">
            <p className="text-sm font-semibold text-slate-600 break-keep">선택한 조건에 맞는 질문이 없어요. 다른 키워드나 카테고리를 눌러 보세요.</p>
          </div>
        )}
      </section>

      <section className="mt-10 rounded-[32px] border border-blue-100 bg-blue-50 p-6 sm:mt-12 sm:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="mt-1 flex h-10 w-10 items-center justify-center rounded-2xl bg-white text-blue-600 shadow-sm">
              <CheckCircle2 size={18} />
            </div>
            <div>
              <h2 className="text-xl font-black tracking-tight text-slate-900 sm:text-2xl break-keep">원하는 답이 없다면 문의 허브로 연결하세요.</h2>
              <p className="mt-2 text-sm font-medium leading-7 text-slate-600 break-keep">
                1:1 문의, 기관 문의, 오류 제보를 구분해서 보낼 수 있어요.
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

