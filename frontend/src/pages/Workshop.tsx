import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  Bot,
  Download,
  FlaskConical,
  Send,
  Sparkles,
  Target,
  ToggleLeft,
  ToggleRight,
  User,
  WandSparkles,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { useLocation, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import confetti from 'canvas-confetti';
import { auth } from '../lib/firebase';
import { api } from '../lib/api';
import { saveArchiveItem } from '../lib/archiveStore';
import { type QuestStartPayload, readQuestStart } from '../lib/questStart';
import { AdvancedPreview } from '../components/AdvancedPreview';
import { ReferenceSearchPanel } from '../components/ReferenceSearchPanel';

export type QualityLevel = 'low' | 'mid' | 'high';
type MessageRole = 'user' | 'foli';

interface Message {
  id: string;
  role: MessageRole;
  content: string;
  suggestedContent?: string;
}

interface DraftArtifact {
  report_markdown: string;
  visual_specs: any[];
  math_expressions: any[];
}

interface WorkshopSessionResponse {
  id: string;
  project_id: string;
  quest_id: string | null;
  status: string;
  quality_level: QualityLevel;
  turns?: any[];
}

interface WorkshopStateResponse {
  session: WorkshopSessionResponse;
  starter_choices: any[];
  followup_choices: any[];
  message: string | null;
  latest_artifact: DraftArtifact | null;
}

const QUALITY_META_MAP: Record<string, any> = {
  low: { bg: 'bg-emerald-50', text: 'text-emerald-600' },
  mid: { bg: 'bg-blue-50', text: 'text-blue-600' },
  high: { bg: 'bg-indigo-50', text: 'text-indigo-600' },
};

function getApiBaseUrl() {
  return import.meta.env.VITE_API_URL || 'http://localhost:8000';
}

async function streamFoliReply(projectId: string | undefined, message: string, onDelta?: (d: string) => void) {
  const baseUrl = getApiBaseUrl();
  const token = auth?.currentUser ? await auth.currentUser.getIdToken() : null;
  const res = await fetch(`${baseUrl}/api/v1/drafts/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ project_id: projectId, message, reference_materials: [] }),
  });
  if (!res.ok || !res.body) throw new Error('STREAM_FAIL');
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let full = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    const events = chunk.split('\n\n');
    for (const e of events) {
      const line = e.split('\n').find(l => l.startsWith('data:'));
      if (line) {
        try {
          const p = JSON.parse(line.replace(/^data:\s*/, ''));
          if (p.token) { full += p.token; onDelta?.(p.token); }
        } catch {}
      }
    }
  }
  return full.trim();
}

export function Workshop() {
  const { projectId } = useParams<{ projectId: string }>();
  const location = useLocation();
  const [workshopState, setWorkshopState] = useState<WorkshopStateResponse | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isSessionLoading, setIsSessionLoading] = useState(true);
  const [documentContent, setDocumentContent] = useState('');
  const [qualityLevel, setQualityLevel] = useState<QualityLevel>('mid');
  const [advancedMode, setAdvancedMode] = useState(false);
  const [renderArtifact, setRenderArtifact] = useState<DraftArtifact | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const questStart = useMemo(() => readQuestStart(), []);
  const initialMajor = useMemo(() => (location.state as any)?.major || '미설정', [location.state]);
  const isProjectBacked = !!projectId && projectId !== 'demo';
  const fileName = useMemo(() => `${(questStart?.title || '초안').replace(/\s+/g,'_')}.hwpx`, [questStart]);

  useEffect(() => {
    // Safety check for localStorage quality level
    const savedLevel = localStorage.getItem('folia_quality_level');
    if (savedLevel === 'low' || savedLevel === 'mid' || savedLevel === 'high') {
      setQualityLevel(savedLevel as QualityLevel);
    }

    setDocumentContent(questStart?.document_seed_markdown || `# [탐구 초안] ${questStart?.title || '주제'}\n\n**전공:** ${initialMajor}\n\n## 1. 탐구 동기`);
    
    if (isProjectBacked) {
       initWorkshop();
    } else {
       setIsSessionLoading(false);
       setMessages([{ id: 'init', role: 'foli', content: '체험 모드입니다. 자유롭게 대화해 보세요!' }]);
    }
  }, [projectId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const initWorkshop = async () => {
    setIsSessionLoading(true);
    try {
      const sessions = await api.get<WorkshopSessionResponse[]>(`/api/v1/workshops?project_id=${projectId}`);
      const active = sessions.find(s => s.status !== 'completed');
      const state = active 
        ? await api.get<WorkshopStateResponse>(`/api/v1/workshops/${active.id}`) 
        : await api.post<WorkshopStateResponse>('/api/v1/workshops', { project_id: projectId, quality_level: qualityLevel });
      
      setWorkshopState(state);
      setQualityLevel(state.session.quality_level);
      if (state.latest_artifact) {
        setRenderArtifact(state.latest_artifact);
        setDocumentContent(state.latest_artifact.report_markdown);
      }
      
      const turns = state.session.turns || [];
      const msgs: Message[] = turns.map(t => ({
        id: t.id,
        role: (t.turn_type === 'user' ? 'user' : 'foli'),
        content: t.turn_type === 'user' ? (t.query || '') : (t.response || '')
      }));
      setMessages(msgs.length ? msgs : [{ id: 'w', role: 'foli', content: state.message || '반갑습니다! 탐구를 시작해볼까요?' }]);
    } catch (e) {
      toast.error('세션 로딩 실패');
    } finally {
      setIsSessionLoading(false);
    }
  };

  const handleSend = async (overText?: string) => {
    const text = (overText ?? input).trim();
    if (!text || isTyping) return;
    if (!overText) setInput('');

    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'user', content: text }]);
    setIsTyping(true);
    
    const foliId = crypto.randomUUID();
    setMessages(prev => [...prev, { id: foliId, role: 'foli', content: '' }]);
    
    let accumulated = '';
    try {
      const raw = await streamFoliReply(projectId, text, delta => {
        accumulated += delta;
        setMessages(ps => ps.map(m => m.id === foliId ? { ...m, content: accumulated } : m));
      });

      // Simple tag parsing
      const tagMatch = raw.match(/\[CONTENT\]([\s\S]*?)\[\/CONTENT\]/);
      if (tagMatch) {
         setMessages(ps => ps.map(m => m.id === foliId ? { 
           ...m, 
           content: raw.replace(/\[CONTENT\][\s\S]*?\[\/CONTENT\]/, '').trim(),
           suggestedContent: tagMatch[1].trim()
         } : m));
      }

      if (isProjectBacked && workshopState) {
        const updated = await api.post<WorkshopStateResponse>(`/api/v1/workshops/${workshopState.session.id}/messages`, { message: text });
        setWorkshopState(updated);
        if (updated.message) {
           setMessages(p => [...p, { id: crypto.randomUUID(), role: 'foli', content: updated.message! }]);
        }
      }
    } catch (e) {
      toast.error('답변 생성 실패');
    } finally {
      setIsTyping(false);
    }
  };

  const qMeta = QUALITY_META_MAP[qualityLevel] || QUALITY_META_MAP.mid;

  return (
    <div className="mx-auto flex h-[calc(100vh-8rem)] max-w-7xl flex-col gap-6 p-4 lg:flex-row lg:px-8">
      {/* Left Panel: Chat */}
      <div className="flex h-[50vh] w-full flex-col rounded-3xl border bg-white shadow-sm lg:h-full lg:w-[40%] overflow-hidden relative">
        <div className="p-4 border-b flex items-center justify-between bg-white z-10">
          <div className="flex items-center gap-2">
            <Bot size={20} className="text-blue-500" />
            <h2 className="text-sm font-black text-slate-800">Foli 작업실</h2>
          </div>
          <div className={`px-2.5 py-1 rounded-lg text-[10px] font-black ${qMeta.bg} ${qMeta.text}`}>
            {qualityLevel.toUpperCase()} LEVEL
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/20">
          {messages.map(m => (
            <div key={m.id} className={`flex gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${m.role === 'user' ? 'bg-slate-100 text-slate-400' : 'bg-blue-500 text-white font-bold'}`}>
                {m.role === 'user' ? <User size={14} /> : 'F'}
              </div>
              <div className={`max-w-[85%] p-3 rounded-2xl text-[14px] leading-relaxed shadow-sm ${m.role === 'user' ? 'bg-slate-800 text-white' : 'bg-white text-slate-700 border border-slate-100'}`}>
                <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                   {String(m.content || '')}
                </ReactMarkdown>
                {m.suggestedContent && (
                  <button 
                    onClick={() => {
                       setDocumentContent(prev => prev.includes(m.suggestedContent!) ? prev : `${prev}\n\n### [AI 제안]\n${m.suggestedContent}`);
                       toast.success('문서에 추가됨');
                    }}
                    className="mt-3 w-full py-2 bg-blue-50 text-blue-600 rounded-xl text-[11px] font-black border border-blue-100 hover:bg-blue-100 transition-colors"
                  >
                    이 내용을 보고서에 추가
                  </button>
                )}
              </div>
            </div>
          ))}
          {isTyping && (
             <div className="flex gap-1.5 p-2">
               <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" />
               <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0.2s]" />
               <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0.4s]" />
             </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="p-4 border-t bg-white space-y-3">
          {isProjectBacked && advancedMode && (
            <ReferenceSearchPanel 
               isAdvancedMode={advancedMode} 
               onPinReference={async (text, source) => {
                  if (!workshopState) return;
                  const res = await api.post<WorkshopStateResponse>(`/api/v1/workshops/${workshopState.session.id}/references/pin`, { text_content: text, source_type: source });
                  setWorkshopState(res);
                  toast.success('자료를 고정했습니다.');
               }} 
            />
          )}

          <div className="flex items-center gap-2">
            <button onClick={() => toast.success('준비 중')} className="p-2.5 bg-slate-50 text-slate-400 rounded-xl hover:bg-slate-100">
               <Download size={18} className="rotate-180" />
            </button>
            <input 
              value={input} 
              onChange={e => setInput(e.target.value)} 
              onKeyDown={e => e.key === 'Enter' && handleSend()} 
              placeholder="메시지를 입력하세요..." 
              className="flex-1 px-4 py-2.5 bg-slate-50 border border-transparent rounded-2xl text-sm focus:outline-none focus:border-blue-400 transition-colors"
            />
            <button 
              onClick={() => handleSend()} 
              disabled={!input.trim() || isTyping}
              className="p-2.5 bg-blue-500 text-white rounded-xl disabled:bg-slate-200 transition-colors"
            >
              <Send size={18} />
            </button>
          </div>

          <div className="flex items-center justify-between px-2 pt-1">
             <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Advanced Features</span>
             <button onClick={() => setAdvancedMode(!advancedMode)} className={`transition-colors ${advancedMode ? 'text-blue-500' : 'text-slate-200'}`}>
                {advancedMode ? <ToggleRight size={24} /> : <ToggleLeft size={24} />}
             </button>
          </div>
        </div>
      </div>

      {/* Right Panel: Document */}
      <div className="flex-1 flex flex-col rounded-3xl border border-slate-700 bg-slate-800 overflow-hidden shadow-2xl min-h-[50vh]">
        <div className="h-14 px-6 flex items-center justify-between bg-slate-900 border-b border-slate-700">
          <div className="flex items-center gap-2">
             <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
             <span className="text-xs text-slate-400 font-bold truncate max-w-[200px]">{fileName}</span>
          </div>
          <div className="flex gap-2">
            <button 
              onClick={async () => {
                if (!workshopState || isRendering) return;
                setIsRendering(true);
                try {
                  await api.post(`/api/v1/workshops/${workshopState.session.id}/render`);
                  toast.success('초안 생성을 예약했습니다.');
                } finally {
                  setIsRendering(false);
                }
              }}
              className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-600 text-white text-[11px] font-black rounded-xl hover:bg-blue-700 transition-colors"
            >
              <WandSparkles size={14} /> {isRendering ? '생성 중...' : '전문화 초안'}
            </button>
            <button 
                onClick={() => {
                  saveArchiveItem({
                    id: crypto.randomUUID(),
                    projectId: projectId ?? null,
                    title: fileName.replace('.hwpx', ''),
                    subject: initialMajor,
                    createdAt: new Date().toISOString(),
                    contentMarkdown: documentContent
                  });
                  toast.success('아카이브에 저장되었습니다.');
                  confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
                }}
                className="px-4 py-1.5 bg-white text-slate-900 text-[11px] font-black rounded-xl hover:bg-slate-50 transition-colors"
            >
               저장
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 sm:p-10 bg-slate-800/40">
           <div className="mx-auto max-w-[210mm] bg-white p-12 shadow-2xl min-h-[297mm] rounded-sm">
             <div className="prose prose-sm prose-slate max-w-none prose-headings:font-black">
               <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                 {String(documentContent || '')}
               </ReactMarkdown>
             </div>
           </div>
           
           <div className="mt-8">
              <AdvancedPreview 
                isAdvancedMode={advancedMode} 
                visualSpecs={renderArtifact?.visual_specs ?? []} 
                mathExpressions={renderArtifact?.math_expressions ?? []} 
              />
           </div>
        </div>
      </div>
    </div>
  );
}
