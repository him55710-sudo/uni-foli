import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Send, Lock, Download, Sparkles, Bot, User } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { api } from '../lib/api';

interface Message {
  id: string;
  role: 'user' | 'poli';
  content: string;
  isConfirmed?: boolean;
}

export function Workshop() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'poli',
      content: '안녕! 오늘 어떤 과목의 세특을 작성해볼까? 주제나 키워드를 알려주면 내가 뼈대를 잡아줄게. ✨',
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [documentContent, setDocumentContent] = useState<string>('# 생명과학 II 탐구 보고서\n\n## 1. 탐구 동기\n\n(여기에 내용이 채워집니다)');
  const [flyingBlock, setFlyingBlock] = useState<{ id: string; content: string } | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      // Call Backend API instead of direct Gemini call
      const response = await api.post('/api/v1/drafts/chat', { 
        message: input 
      });

      const poliMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'poli',
        content: response.response || '오류가 발생했어요. 다시 시도해볼까요?',
        isConfirmed: input.includes('추가') || input.includes('넣어줘') || input.includes('좋아'), // Simple heuristic
      };

      setMessages((prev) => [...prev, poliMessage]);

      // Trigger flying animation if content is confirmed
      if (poliMessage.isConfirmed) {
        triggerFlyingBlock(poliMessage.id, input);
      }

    } catch (error) {
      console.error('Gemini API Error:', error);
      setMessages((prev) => [...prev, {
        id: Date.now().toString(),
        role: 'poli',
        content: '앗! 서버에 잠깐 과부하가 걸렸나 봐요. Poli가 얼른 고치고 올게요! 🤕',
      }]);
    } finally {
      setIsTyping(false);
    }
  };

  const triggerFlyingBlock = (id: string, content: string) => {
    setFlyingBlock({ id, content });
    
    // Update document after animation
    setTimeout(() => {
      setDocumentContent((prev) => prev.replace('(여기에 내용이 채워집니다)', content + '\n\n(여기에 내용이 채워집니다)'));
      setFlyingBlock(null);
    }, 1000);
  };

  return (
    <div className="flex flex-col lg:flex-row h-[calc(100vh-8rem)] gap-6 overflow-hidden max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-8">
      {/* Left Panel: Chat (40%) */}
      <div className="w-full lg:w-2/5 flex flex-col bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden relative z-10 h-[50vh] lg:h-full">
        {/* Chat Header */}
        <div className="h-16 border-b border-slate-100 flex items-center px-6 bg-white/80 backdrop-blur-sm z-10 sticky top-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center text-blue-500 shadow-sm border border-blue-100">
              <Bot size={20} />
            </div>
            <div>
              <h2 className="font-extrabold text-slate-800 text-base">Poli와 대화 중</h2>
              <p className="text-xs text-slate-500 font-medium">언제든 편하게 물어보세요!</p>
            </div>
          </div>
        </div>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 bg-slate-50/50 hide-scrollbar">
          <AnimatePresence>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                {/* Avatar */}
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm ${
                  msg.role === 'user' ? 'bg-white border border-slate-200 text-slate-400' : 'bg-blue-500 text-white shadow-blue-500/20'
                }`}>
                  {msg.role === 'user' ? <User size={20} /> : <span className="font-extrabold text-lg">P</span>}
                </div>

                {/* Bubble */}
                <div className={`max-w-[80%] sm:max-w-[75%] rounded-2xl p-4 sm:p-5 text-[15px] leading-relaxed shadow-sm ${
                  msg.role === 'user' 
                    ? 'bg-slate-800 text-white rounded-tr-sm' 
                    : 'bg-white text-slate-700 border border-slate-100 rounded-tl-sm'
                }`}>
                <div className="prose prose-sm max-w-none prose-p:leading-relaxed prose-p:m-0 font-medium">
                  <ReactMarkdown>
                    {msg.content}
                  </ReactMarkdown>
                </div>
                  
                  {/* Action Button for Poli's suggestions */}
                  {msg.role === 'poli' && msg.isConfirmed && (
                    <div className="mt-4 pt-4 border-t border-slate-100 flex justify-end">
                      <button 
                        onClick={() => triggerFlyingBlock(msg.id, "추가된 내용입니다.")}
                        className="text-xs font-extrabold text-blue-600 flex items-center gap-1.5 hover:text-blue-700 transition-colors bg-blue-50 px-3 py-2 rounded-xl border border-blue-100"
                      >
                        <Sparkles size={14} /> 문서에 바로 적용하기
                      </button>
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
          
          {isTyping && (
            <motion.div 
              initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="flex gap-3"
            >
              <div className="w-10 h-10 bg-blue-500 text-white rounded-xl flex items-center justify-center shadow-sm shadow-blue-500/20">
                <span className="font-extrabold text-lg">P</span>
              </div>
              <div className="bg-white border border-slate-100 rounded-2xl rounded-tl-sm p-5 shadow-sm flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 bg-blue-200 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2.5 h-2.5 bg-blue-300 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2.5 h-2.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-white border-t border-slate-100">
          <div className="relative flex items-center">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Poli에게 메시지 보내기..."
              className="w-full bg-slate-50 border-2 border-slate-100 rounded-2xl py-3.5 pl-5 pr-14 text-[15px] font-medium text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100 transition-all shadow-sm"
            />
            <button 
              onClick={handleSend}
              disabled={!input.trim() || isTyping}
              className="absolute right-2 w-10 h-10 bg-blue-500 text-white rounded-xl flex items-center justify-center disabled:opacity-50 disabled:bg-slate-300 transition-all hover:bg-blue-600 shadow-sm shadow-blue-500/20"
            >
              <Send size={18} className="ml-0.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Right Panel: Live Document (60%) */}
      <div className="w-full lg:w-3/5 bg-slate-800 rounded-3xl overflow-hidden relative flex flex-col h-[50vh] lg:h-full shadow-sm border border-slate-700">
        {/* Toolbar */}
        <div className="h-14 bg-slate-900 border-b border-slate-700 flex items-center justify-between px-6">
          <div className="flex items-center gap-2">
            <div className="w-3.5 h-3.5 rounded-full bg-red-400 shadow-sm" />
            <div className="w-3.5 h-3.5 rounded-full bg-amber-400 shadow-sm" />
            <div className="w-3.5 h-3.5 rounded-full bg-emerald-400 shadow-sm" />
          </div>
          <div className="text-slate-300 text-xs font-bold bg-slate-800 px-4 py-1.5 rounded-xl border border-slate-700 shadow-inner">
            생명과학_탐구보고서_최종.hwpx
          </div>
          <div className="w-16" /> {/* Spacer */}
        </div>

        {/* Canvas Area */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-8 flex justify-center relative hide-scrollbar">
          {/* The A4 Paper */}
          <div className="w-full max-w-[210mm] min-h-[297mm] bg-white shadow-2xl p-8 sm:p-12 md:p-16 text-slate-800 font-serif relative z-0 rounded-sm">
            <div className="prose prose-sm sm:prose-base max-w-none prose-headings:font-extrabold prose-headings:text-slate-900 prose-p:text-slate-700 prose-p:leading-loose">
              <ReactMarkdown>
                {documentContent}
              </ReactMarkdown>
            </div>
          </div>

          {/* Flying Block Animation */}
          <AnimatePresence>
            {flyingBlock && (
              <motion.div
                initial={{ opacity: 0, x: -300, y: 100, scale: 0.5 }}
                animate={{ opacity: 1, x: 0, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 1.1 }}
                transition={{ duration: 0.8, type: 'spring', bounce: 0.4 }}
                className="absolute z-50 bg-blue-50/95 backdrop-blur-md border-2 border-blue-200 text-blue-700 p-5 rounded-2xl shadow-2xl max-w-xs text-[15px] font-extrabold"
                style={{ top: '30%', left: '20%' }}
              >
                <Sparkles size={20} className="inline mr-2 mb-1 text-blue-500" />
                문서에 내용이 추가되고 있어요!
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Floating Download Button */}
        <div className="absolute bottom-6 right-6 z-20">
          <button className="bg-white text-slate-800 px-5 sm:px-6 py-3.5 sm:py-4 rounded-2xl font-extrabold shadow-xl hover:bg-slate-50 transition-all flex items-center gap-3 group border-2 border-slate-100 hover:border-slate-200 hover:scale-105 active:scale-95">
            <Download size={20} className="text-slate-400 group-hover:text-blue-500 transition-colors" />
            <span className="hidden sm:inline">선생님 제출용 HWPX 다운로드</span>
            <span className="sm:hidden">다운로드</span>
            <div className="w-7 h-7 bg-slate-100 rounded-full flex items-center justify-center ml-1 sm:ml-2 group-hover:bg-blue-50 transition-colors">
              <Lock size={14} className="text-slate-400 group-hover:text-blue-500 transition-colors" />
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}
