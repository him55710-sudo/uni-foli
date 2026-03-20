import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Send, Lock, Download, Sparkles, Bot, User } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useParams, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import confetti from 'canvas-confetti';
import { auth } from '../lib/firebase';
import { api } from '../lib/api';
import { saveArchiveItem } from '../lib/archiveStore';

interface Message {
  id: string;
  role: 'user' | 'poli';
  content: string;
  suggestedContent?: string;
}

function extractSuggestedContent(raw: string): { clean: string; suggestion?: string } {
  const match = raw.match(/\[CONTENT\]([\s\S]*?)\[\/CONTENT\]/i);
  if (!match) {
    return { clean: raw.trim() };
  }

  const clean = raw.replace(match[0], '').trim();
  return {
    clean: clean || '문서에 넣을 내용을 준비했어요.',
    suggestion: match[1].trim(),
  };
}

function localFallbackReply(input: string): string {
  return [
    '좋아요. 지금 요청을 바탕으로 보고서 문장 초안을 정리했어요.',
    '',
    '[CONTENT]',
    `- 주제: ${input}`,
    '- 탐구 동기: 사회적 맥락과 개인적 문제의식을 연결해 서술',
    '- 탐구 과정: 자료 수집 -> 분석 기준 설계 -> 결과 해석 순서로 구조화',
    '- 배운 점: 전공 연계 역량(문제정의, 근거기반 추론, 표현력) 강조',
    '[/CONTENT]',
    '',
    '위 문장을 문서에 바로 적용해볼까요?',
  ].join('\n');
}

async function streamPoliReply(projectId: string, message: string): Promise<string> {
  const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const token = auth.currentUser ? await auth.currentUser.getIdToken() : null;
  const response = await fetch(`${baseUrl}/api/v1/projects/${projectId}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat stream failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let full = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';

    for (const event of events) {
      const line = event
        .split('\n')
        .find((entry) => entry.trim().startsWith('data:'));
      if (!line) continue;

      const payload = line.replace(/^data:\s*/, '');
      try {
        const parsed = JSON.parse(payload) as { token?: string; status?: string; error?: string };
        if (parsed.error) {
          throw new Error(parsed.error);
        }
        if (parsed.token) {
          full += parsed.token;
        }
      } catch {
        // Ignore malformed chunks and continue streaming.
      }
    }
  }

  return full.trim();
}

export function Workshop() {
  const { projectId } = useParams();
  const [searchParams] = useSearchParams();
  const initialMajor = searchParams.get('major') || '희망 전공';

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'poli',
      content: `${initialMajor} 중심으로 세특/탐구 보고서 초안을 같이 만들어볼까요? 키워드나 상황을 한 줄로 알려주세요.`,
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [flyingBlock, setFlyingBlock] = useState<{ id: string; content: string } | null>(null);
  const [documentContent, setDocumentContent] = useState<string>(
    [
      `# ${initialMajor} 탐구 보고서`,
      '',
      '## 1. 탐구 동기',
      '',
      '(여기에 내용이 채워집니다)',
    ].join('\n'),
  );

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const fileName = useMemo(() => {
    const safeMajor = initialMajor.replace(/[^\w\-\uAC00-\uD7A3]+/g, '_');
    return `${safeMajor || 'polio'}_보고서.hwpx`;
  }, [initialMajor]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const applyContentToDocument = (content: string) => {
    setFlyingBlock({ id: crypto.randomUUID(), content });
    setTimeout(() => {
      setDocumentContent((prev) => {
        if (prev.includes('(여기에 내용이 채워집니다)')) {
          return prev.replace('(여기에 내용이 채워집니다)', `${content}\n\n(여기에 내용이 채워집니다)`);
        }
        return `${prev}\n\n${content}`;
      });
      setFlyingBlock(null);
    }, 900);
  };

  const handleSend = async () => {
    if (!input.trim() || isTyping) return;

    const userText = input.trim();
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: userText,
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    const draftId = crypto.randomUUID();
    setMessages((prev) => [...prev, { id: draftId, role: 'poli', content: '' }]);

    try {
      const rawReply = projectId
        ? await streamPoliReply(projectId, userText)
        : localFallbackReply(userText);
      const parsed = extractSuggestedContent(rawReply || localFallbackReply(userText));

      setMessages((prev) =>
        prev.map((message) =>
          message.id === draftId
            ? {
                ...message,
                content: parsed.clean,
                suggestedContent: parsed.suggestion,
              }
            : message,
        ),
      );
    } catch (error) {
      console.error('Chat error:', error);
      const parsed = extractSuggestedContent(localFallbackReply(userText));
      setMessages((prev) =>
        prev.map((message) =>
          message.id === draftId
            ? {
                ...message,
                content: parsed.clean,
                suggestedContent: parsed.suggestion,
              }
            : message,
        ),
      );
      toast('서버 연결이 불안정해서 임시 초안으로 이어서 도와드릴게요.', {
        icon: '⚠️',
      });
    } finally {
      setIsTyping(false);
    }
  };

  const handleExport = async () => {
    if (isExporting) return;
    setIsExporting(true);
    const loadingId = toast.loading('문서를 내보내는 중입니다...');

    try {
      if (projectId) {
        const blob = await api.post<Blob>(
          `/api/v1/projects/${projectId}/export`,
          { content_markdown: documentContent },
          { responseType: 'blob' },
        );
        const url = window.URL.createObjectURL(new Blob([blob]));
        const link = document.createElement('a');
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      } else {
        const fallbackBlob = new Blob([documentContent], { type: 'text/plain;charset=utf-8' });
        const url = window.URL.createObjectURL(fallbackBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      }

      saveArchiveItem({
        id: crypto.randomUUID(),
        projectId: projectId ?? null,
        title: fileName.replace('.hwpx', ''),
        subject: initialMajor,
        createdAt: new Date().toISOString(),
        contentMarkdown: documentContent,
      });

      toast.success('내보내기 완료! 아카이브에서도 다시 받을 수 있어요.', { id: loadingId });
      confetti({
        particleCount: 140,
        spread: 70,
        origin: { y: 0.6 },
        colors: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'],
      });
    } catch (error) {
      console.error('Export error:', error);
      toast.error('내보내기에 실패했습니다. 잠시 후 다시 시도해주세요.', { id: loadingId });
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="mx-auto flex h-[calc(100vh-8rem)] max-w-7xl flex-col gap-6 overflow-hidden px-4 pb-8 sm:px-6 lg:flex-row lg:px-8">
      <div className="relative z-10 flex h-[50vh] w-full flex-col overflow-hidden rounded-3xl border border-slate-100 bg-white shadow-sm lg:h-full lg:w-2/5">
        <div className="sticky top-0 z-10 flex h-16 items-center border-b border-slate-100 bg-white/80 px-6 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-100 bg-blue-50 text-blue-500 shadow-sm">
              <Bot size={20} />
            </div>
            <div>
              <h2 className="text-base font-extrabold text-slate-800">Poli와 작성 중</h2>
              <p className="text-xs font-medium text-slate-500">
                {projectId ? '프로젝트 기반 초안 작성' : '게스트 모드 초안 작성'}
              </p>
            </div>
          </div>
        </div>

        <div className="hide-scrollbar flex-1 space-y-6 overflow-y-auto bg-slate-50/50 p-4 sm:p-6">
          <AnimatePresence>
            {messages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                <div
                  className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl shadow-sm ${
                    message.role === 'user'
                      ? 'border border-slate-200 bg-white text-slate-400'
                      : 'bg-blue-500 text-white shadow-blue-500/20'
                  }`}
                >
                  {message.role === 'user' ? <User size={20} /> : <span className="text-lg font-extrabold">P</span>}
                </div>

                <div
                  className={`max-w-[80%] rounded-2xl p-4 text-[15px] leading-relaxed shadow-sm sm:max-w-[75%] sm:p-5 ${
                    message.role === 'user'
                      ? 'rounded-tr-sm bg-slate-800 text-white'
                      : 'rounded-tl-sm border border-slate-100 bg-white text-slate-700'
                  }`}
                >
                  <div className="prose prose-sm max-w-none font-medium prose-p:m-0 prose-p:leading-relaxed">
                    <ReactMarkdown>{message.content || '...'}</ReactMarkdown>
                  </div>

                  {message.role === 'poli' && message.suggestedContent ? (
                    <div className="mt-4 flex justify-end border-t border-slate-100 pt-4">
                      <button
                        onClick={() => applyContentToDocument(message.suggestedContent!)}
                        className="flex items-center gap-1.5 rounded-xl border border-blue-100 bg-blue-50 px-3 py-2 text-xs font-extrabold text-blue-600 transition-colors hover:text-blue-700"
                      >
                        <Sparkles size={14} /> 문서에 적용하기
                      </button>
                    </div>
                  ) : null}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {isTyping ? (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500 text-white shadow-sm shadow-blue-500/20">
                <span className="text-lg font-extrabold">P</span>
              </div>
              <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm border border-slate-100 bg-white p-5 shadow-sm">
                <div className="h-2.5 w-2.5 animate-bounce rounded-full bg-blue-200" />
                <div className="h-2.5 w-2.5 animate-bounce rounded-full bg-blue-300 [animation-delay:150ms]" />
                <div className="h-2.5 w-2.5 animate-bounce rounded-full bg-blue-400 [animation-delay:300ms]" />
              </div>
            </motion.div>
          ) : null}
          <div ref={messagesEndRef} />
        </div>

        <div className="border-t border-slate-100 bg-white p-4">
          <div className="relative flex items-center">
            <input
              type="text"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') handleSend();
              }}
              placeholder="Poli에게 메시지 보내기..."
              className="w-full rounded-2xl border-2 border-slate-100 bg-slate-50 py-3.5 pl-5 pr-14 text-[15px] font-medium text-slate-700 shadow-sm transition-all placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-4 focus:ring-blue-100"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isTyping}
              className="absolute right-2 flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500 text-white shadow-sm shadow-blue-500/20 transition-all hover:bg-blue-600 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:opacity-50"
            >
              <Send size={18} className="ml-0.5" />
            </button>
          </div>
        </div>
      </div>

      <div className="relative flex h-[50vh] w-full flex-col overflow-hidden rounded-3xl border border-slate-700 bg-slate-800 shadow-sm lg:h-full lg:w-3/5">
        <div className="flex h-14 items-center justify-between border-b border-slate-700 bg-slate-900 px-6">
          <div className="flex items-center gap-2">
            <div className="h-3.5 w-3.5 rounded-full bg-red-400 shadow-sm" />
            <div className="h-3.5 w-3.5 rounded-full bg-amber-400 shadow-sm" />
            <div className="h-3.5 w-3.5 rounded-full bg-emerald-400 shadow-sm" />
          </div>
          <div className="rounded-xl border border-slate-700 bg-slate-800 px-4 py-1.5 text-xs font-bold text-slate-300 shadow-inner">
            {fileName}
          </div>
          <div className="w-16" />
        </div>

        <div className="hide-scrollbar relative flex flex-1 justify-center overflow-y-auto p-4 sm:p-8">
          <div className="relative z-0 min-h-[297mm] w-full max-w-[210mm] rounded-sm bg-white p-8 font-serif text-slate-800 shadow-2xl sm:p-12 md:p-16">
            <div className="prose prose-sm max-w-none prose-headings:font-extrabold prose-headings:text-slate-900 prose-p:leading-loose prose-p:text-slate-700 sm:prose-base">
              <ReactMarkdown>{documentContent}</ReactMarkdown>
            </div>
          </div>

          <AnimatePresence>
            {flyingBlock ? (
              <motion.div
                initial={{ opacity: 0, x: -300, y: 100, scale: 0.5 }}
                animate={{ opacity: 1, x: 0, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 1.1 }}
                transition={{ duration: 0.8, type: 'spring', bounce: 0.4 }}
                className="absolute z-50 max-w-xs rounded-2xl border-2 border-blue-200 bg-blue-50/95 p-5 text-[15px] font-extrabold text-blue-700 shadow-2xl backdrop-blur-md"
                style={{ top: '30%', left: '20%' }}
              >
                <Sparkles size={20} className="mb-1 mr-2 inline text-blue-500" />
                문서에 제안 내용을 반영하고 있어요!
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>

        <div className="absolute bottom-6 right-6 z-20">
          <button
            onClick={handleExport}
            disabled={isExporting}
            className={`group flex items-center gap-3 rounded-2xl border-2 border-slate-100 bg-white px-5 py-3.5 font-extrabold text-slate-800 shadow-xl transition-all hover:scale-105 hover:border-slate-200 hover:bg-slate-50 active:scale-95 sm:px-6 sm:py-4 ${isExporting ? 'cursor-not-allowed opacity-70' : ''}`}
          >
            <Download
              size={20}
              className={`${isExporting ? 'animate-bounce' : 'text-slate-400 group-hover:text-blue-500'} transition-colors`}
            />
            <span className="hidden sm:inline">{isExporting ? '문서 내보내는 중...' : '제출용 HWPX 다운로드'}</span>
            <span className="sm:hidden">{isExporting ? '내보내는 중' : '다운로드'}</span>
            <div className="ml-1 flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 transition-colors group-hover:bg-blue-50 sm:ml-2">
              <Lock size={14} className="text-slate-400 transition-colors group-hover:text-blue-500" />
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}
