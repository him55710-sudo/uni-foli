import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, Search, AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, Zap, Sparkles, AlertCircle, FileText, ShieldCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';

interface DiagnosisModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const subjectsData = [
  { 
    id: 'math', 
    name: '수학', 
    status: 'danger', 
    score: 65, 
    comment: '조건부 확률의 개념 이해도는 높으나, 지망 학과(경영학)의 마케팅/소비자 행동 분석과의 연계 논리가 현저히 부족함. 단순 공식 나열에 그침.' 
  },
  { 
    id: 'science', 
    name: '통합과학', 
    status: 'warning', 
    score: 78, 
    comment: '기후 변화에 대한 탐구는 좋으나, 이를 ESG 경영이나 탄소 배출권 거래제 등 상경계열 이슈로 확장하지 못한 점이 아쉬움.' 
  },
  { 
    id: 'korean', 
    name: '국어', 
    status: 'safe', 
    score: 92, 
    comment: '비문학 지문 분석 능력이 탁월하며, 특히 경제 지문을 경영학적 관점에서 재해석한 발표가 매우 인상적임.' 
  }
];

export function DiagnosisModal({ isOpen, onClose }: DiagnosisModalProps) {
  const [step, setStep] = useState(1);
  const [major, setMajor] = useState('');
  const [expandedSubject, setExpandedSubject] = useState<string | null>('math');
  const navigate = useNavigate();

  useEffect(() => {
    if (step === 3) {
      const timer = setTimeout(() => {
        setStep(4);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [step]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setStep(3); // 파일 업로드 시 바로 분석(Step 3)으로 넘어감
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ 
    onDrop, 
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1
  });

  if (!isOpen) return null;

  const handleNext = () => {
    if (step < 3) setStep(step + 1);
  };

  const handleClose = () => {
    onClose();
    setTimeout(() => {
      setStep(1);
      setMajor('');
      setExpandedSubject('math');
    }, 300);
  };

  const handleStartWorkshop = () => {
    handleClose();
    navigate('/workshop');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-900/40 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, y: 100 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 100 }}
        className={`w-full bg-white rounded-t-3xl sm:rounded-3xl overflow-hidden shadow-2xl relative flex flex-col transition-all duration-500 ${
          step === 4 ? 'sm:max-w-3xl h-[90vh] sm:h-[800px]' : 'sm:max-w-md h-[80vh] sm:h-[600px]'
        }`}
      >
        <button onClick={handleClose} className="absolute top-4 right-4 z-20 p-2 text-slate-400 hover:text-slate-600 bg-slate-50/80 backdrop-blur-sm rounded-full transition-colors">
          <X size={20} />
        </button>

        <div className="flex-1 overflow-y-auto relative hide-scrollbar">
          <AnimatePresence mode="wait">
            {/* Step 1: 목표 설정 */}
            {step === 1 && (
              <motion.div key="step1" initial={{ opacity: 0, x: 50 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -50 }} className="h-full flex flex-col justify-center p-6 sm:p-8">
                <h3 className="text-3xl font-extrabold text-slate-800 mb-3 break-keep leading-tight">목표로 하는<br/>지망 학과는 어디인가요?</h3>
                <p className="text-slate-500 mb-10 font-medium text-lg">Poli가 학과 맞춤형으로 분석해 드릴게요.</p>
                <input 
                  type="text" 
                  value={major} 
                  onChange={(e) => setMajor(e.target.value)} 
                  onKeyDown={(e) => { if (e.key === 'Enter' && major) handleNext(); }}
                  placeholder="예: 경영학과, 컴퓨터공학과" 
                  className="w-full text-3xl font-bold border-b-2 border-slate-200 focus:border-blue-500 pb-3 outline-none placeholder:text-slate-300 transition-colors text-slate-800" 
                  autoFocus 
                />
              </motion.div>
            )}

            {/* Step 2: 생기부 PDF 업로드 */}
            {step === 2 && (
              <motion.div key="step2" initial={{ opacity: 0, x: 50 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -50 }} className="h-full flex flex-col p-6 sm:p-8 pt-16">
                <h3 className="text-2xl font-extrabold text-slate-800 mb-2 break-keep">생기부 PDF를<br/>업로드해주세요.</h3>
                <p className="text-slate-500 mb-6 font-medium">나이스(NEIS)에서 다운로드한 생기부를 올려주세요.</p>
                
                <div 
                  {...getRootProps()} 
                  className={`flex-1 border-2 border-dashed rounded-3xl flex flex-col items-center justify-center p-6 cursor-pointer transition-all duration-300 group ${
                    isDragActive ? 'border-blue-500 bg-blue-100' : 'border-blue-300 bg-blue-50/50 hover:bg-blue-50 hover:border-blue-400'
                  }`}
                >
                  <input {...getInputProps()} />
                  <div className="w-20 h-20 mb-6 bg-gradient-to-br from-blue-400 to-blue-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/30 transform rotate-3 group-hover:rotate-6 group-hover:scale-110 transition-all duration-300">
                    <FileText size={36} className="text-white" />
                  </div>
                  <h3 className="text-xl font-extrabold text-slate-800 mb-2 text-center break-keep">나이스(NEIS) 생기부 PDF를<br/>이곳에 끌어다 놓으세요</h3>
                  <p className="text-slate-500 font-medium text-center mb-8 text-sm">또는 클릭하여 파일을 선택해주세요</p>
                  
                  <div className="mt-auto flex items-center gap-1.5 text-xs font-bold text-slate-500 bg-white/60 px-4 py-2.5 rounded-full text-center break-keep">
                    <ShieldCheck size={16} className="text-emerald-500 shrink-0" />
                    PDF 파일은 서버에 저장되지 않고 즉시 분석 후 파기됩니다.
                  </div>
                </div>
              </motion.div>
            )}

            {/* Step 3: 로딩 애니메이션 */}
            {step === 3 && (
              <motion.div key="step3" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 1.1 }} className="h-full flex flex-col items-center justify-center text-center p-6">
                <div className="relative w-32 h-32 mb-8 flex items-center justify-center">
                  <div className="absolute inset-0 border-4 border-blue-100 rounded-full"></div>
                  <div className="absolute inset-0 border-4 border-blue-500 rounded-full border-t-transparent animate-spin" style={{ animationDuration: '1.5s' }}></div>
                  <Search size={40} className="text-blue-500 animate-pulse" />
                </div>
                <h3 className="text-2xl font-extrabold text-slate-800 mb-3 break-keep">AI가 생기부 PDF를 해독하고<br/>KCI 데이터와 대조 중입니다...</h3>
                <p className="text-blue-500 font-bold animate-pulse">Poli가 사정관의 시선으로 분석하고 있어요</p>
              </motion.div>
            )}

            {/* Step 4: AI 종합 진단 리포트 */}
            {step === 4 && (
              <motion.div key="step4" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="h-full flex flex-col bg-slate-50">
                <div className="flex-1 overflow-y-auto p-6 sm:p-8 pb-32 hide-scrollbar space-y-6">
                  
                  {/* 섹션 A: 종합 지표 */}
                  <div className="clay-card p-8 text-center relative overflow-hidden bg-white">
                    <div className="absolute top-0 left-0 w-full h-2 bg-gradient-to-r from-blue-400 to-indigo-500"></div>
                    <h2 className="text-xl font-extrabold text-slate-800 mb-6">AI 종합 진단 리포트</h2>
                    
                    {/* 반원형 게이지 차트 */}
                    <div className="relative w-48 h-24 mx-auto mb-4">
                      <svg viewBox="0 0 100 50" className="w-full h-full overflow-visible drop-shadow-md">
                        <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="#F1F5F9" strokeWidth="12" strokeLinecap="round" />
                        <motion.path
                          d="M 10 50 A 40 40 0 0 1 90 50"
                          fill="none"
                          stroke="url(#gradient)"
                          strokeWidth="12"
                          strokeLinecap="round"
                          strokeDasharray="125.6"
                          strokeDashoffset="125.6"
                          animate={{ strokeDashoffset: 43.96 }} // 65% (125.6 * 0.35)
                          transition={{ duration: 1.5, ease: "easeOut", delay: 0.2 }}
                        />
                        <defs>
                          <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#3B82F6" />
                            <stop offset="100%" stopColor="#6366F1" />
                          </linearGradient>
                        </defs>
                      </svg>
                      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 flex flex-col items-center">
                        <span className="text-4xl font-black text-slate-800 tracking-tighter">65<span className="text-2xl text-slate-400">%</span></span>
                        <span className="text-xs font-bold text-slate-500 mt-1">전공 적합도</span>
                      </div>
                    </div>

                    <div className="inline-flex items-center gap-2 px-4 py-2.5 bg-red-50 border border-red-100 rounded-xl text-red-600 font-bold text-sm mt-4">
                      <AlertTriangle size={18} className="shrink-0" />
                      <span className="text-left">위험: 전공 연계 심화 탐구가 전반적으로 부족합니다.</span>
                    </div>
                  </div>

                  {/* 섹션 B: 과목별 상세 진단 리스트 */}
                  <div className="space-y-3">
                    <h3 className="text-lg font-extrabold text-slate-800 px-2">과목별 상세 진단</h3>
                    {subjectsData.map((sub) => (
                      <div 
                        key={sub.id} 
                        className={`clay-card bg-white overflow-hidden transition-all duration-300 border-2 ${expandedSubject === sub.id ? (sub.status === 'danger' ? 'border-red-200' : sub.status === 'warning' ? 'border-amber-200' : 'border-emerald-200') : 'border-transparent'}`}
                      >
                        <button 
                          onClick={() => setExpandedSubject(expandedSubject === sub.id ? null : sub.id)}
                          className="w-full p-5 flex items-center justify-between bg-white hover:bg-slate-50 transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <span className="px-3 py-1.5 bg-slate-100 text-slate-700 font-extrabold text-sm rounded-lg">
                              {sub.name}
                            </span>
                            <div className="flex items-center gap-1.5">
                              {sub.status === 'safe' && <><CheckCircle2 size={18} className="text-emerald-500" /><span className="text-sm font-bold text-emerald-600">안전</span></>}
                              {sub.status === 'warning' && <><AlertCircle size={18} className="text-amber-500" /><span className="text-sm font-bold text-amber-600">보완 필요</span></>}
                              {sub.status === 'danger' && <><AlertTriangle size={18} className="text-red-500" /><span className="text-sm font-bold text-red-600">위험</span></>}
                            </div>
                          </div>
                          {expandedSubject === sub.id ? <ChevronUp size={20} className="text-slate-400" /> : <ChevronDown size={20} className="text-slate-400" />}
                        </button>
                        
                        <AnimatePresence>
                          {expandedSubject === sub.id && (
                            <motion.div 
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="overflow-hidden"
                            >
                              <div className={`p-5 pt-0 text-sm font-medium leading-relaxed ${sub.status === 'danger' ? 'text-red-700' : sub.status === 'warning' ? 'text-amber-700' : 'text-emerald-700'}`}>
                                <div className={`p-4 rounded-xl ${sub.status === 'danger' ? 'bg-red-50' : sub.status === 'warning' ? 'bg-amber-50' : 'bg-emerald-50'}`}>
                                  <span className="font-extrabold block mb-1">💡 Poli's 팩트 폭행:</span>
                                  {sub.comment}
                                </div>
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    ))}
                  </div>

                </div>

                {/* 섹션 C: Poli의 처방전 & 액션 버튼 (Sticky Bottom) */}
                <div className="absolute bottom-0 left-0 w-full bg-white/90 backdrop-blur-md border-t border-slate-200 p-6 sm:px-8 shadow-[0_-10px_30px_rgba(0,0,0,0.05)]">
                  <div className="flex items-start gap-3 mb-4">
                    <div className="w-10 h-10 bg-blue-500 rounded-xl flex items-center justify-center text-white font-extrabold shadow-md shrink-0">
                      P
                    </div>
                    <div className="bg-blue-50 border border-blue-100 rounded-2xl rounded-tl-sm p-4 flex-1">
                      <p className="text-sm sm:text-base font-bold text-blue-900 leading-snug">
                        수학 세특을 보완할 <span className="text-blue-600 font-black">'상권 폐업률 회귀분석'</span> 보고서를 지금 당장 써볼까요?
                      </p>
                    </div>
                  </div>
                  <button onClick={handleStartWorkshop} className="clay-btn-primary w-full py-4 text-lg font-extrabold flex items-center justify-center gap-2 group">
                    <Zap size={20} className="text-yellow-300 fill-yellow-300 group-hover:scale-110 transition-transform" />
                    진단받은 내용으로 새 탐구 시작하기
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* 하단 버튼 (Step 1) */}
        {step === 1 && (
          <div className="p-6 border-t border-slate-100 bg-white z-10">
            <button 
              onClick={handleNext} 
              disabled={!major} 
              className="clay-btn-primary w-full py-4 text-lg font-extrabold disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              다음
            </button>
          </div>
        )}
      </motion.div>
    </div>
  );
}
