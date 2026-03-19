import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';
import { FolderOpen, AlertCircle, CheckCircle2, HelpCircle } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const radarData = [
  { subject: '학업역량', A: 85, fullMark: 100 },
  { subject: '전공적합성', A: 65, fullMark: 100 },
  { subject: '발전가능성', A: 90, fullMark: 100 },
  { subject: '인성', A: 95, fullMark: 100 },
  { subject: '탐구력', A: 75, fullMark: 100 },
  { subject: '리더십', A: 80, fullMark: 100 },
];

const subjects = [
  { name: '국어', status: 'safe', score: 92 },
  { name: '수학', status: 'warning', score: 68 },
  { name: '영어', status: 'safe', score: 88 },
  { name: '과학', status: 'danger', score: 55 },
  { name: '사회', status: 'safe', score: 95 },
];

export function Record() {
  const { user } = useAuth();

  const onDrop = useCallback((acceptedFiles: File[]) => {
    console.log(acceptedFiles);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop, accept: { 'application/pdf': ['.pdf'] } });

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div className="mb-8">
        <h1 className="text-3xl font-extrabold text-slate-800 mb-2">{user?.displayName || '학생'}님의 생기부 대시보드</h1>
        <p className="text-slate-500 font-medium">업로드된 데이터를 바탕으로 분석된 나의 현재 위치입니다.</p>
      </div>

      {/* Top: Upload View */}
      <div {...getRootProps()} className={`clay-card border-2 border-dashed p-10 text-center cursor-pointer transition-colors ${isDragActive ? 'border-blue-400 bg-blue-50' : 'border-blue-200 hover:border-blue-400 hover:bg-slate-50'}`}>
        <input {...getInputProps()} />
        <div className="w-20 h-20 mx-auto bg-gradient-to-br from-blue-400 to-blue-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/30 mb-4 transform rotate-3">
          <FolderOpen size={36} className="text-white" />
        </div>
        <h3 className="text-xl font-extrabold text-slate-800 mb-2">나이스(NEIS) 생기부 PDF를 끌어다 놓으세요</h3>
        <p className="text-slate-500 font-medium">또는 클릭하여 파일을 선택해주세요 (최대 50MB)</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Middle: Radar Chart */}
        <div className="clay-card p-6 sm:p-8 flex flex-col relative">
          <h3 className="text-xl font-extrabold text-slate-800 mb-6">6대 핵심 역량 분석</h3>
          <div className="h-64 sm:h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                <PolarGrid stroke="#E2E8F0" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: '#475569', fontSize: 13, fontWeight: 700 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                <Radar name="Student" dataKey="A" stroke="#3B82F6" strokeWidth={3} fill="#60A5FA" fillOpacity={0.5} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
          
          {/* Poli's Advice Bubble */}
          <div className="absolute bottom-6 right-6 sm:bottom-8 sm:right-8 bg-white border border-blue-100 shadow-xl rounded-2xl rounded-br-sm p-4 max-w-[200px] z-10 animate-bounce" style={{ animationDuration: '3s' }}>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center text-white text-xs font-bold">P</div>
              <span className="text-xs font-extrabold text-blue-600">Poli의 조언</span>
            </div>
            <p className="text-sm font-bold text-slate-700 leading-tight">전공 연계 탐구가 부족해요! 과학 과목 세특을 보완해볼까요?</p>
          </div>
        </div>

        {/* Bottom: Subject Status */}
        <div className="clay-card p-6 sm:p-8">
          <h3 className="text-xl font-extrabold text-slate-800 mb-6">주요 과목 세특 완성도</h3>
          <div className="space-y-5">
            {subjects.map((sub, idx) => (
              <div key={idx} className="flex items-center justify-between p-4 rounded-2xl bg-slate-50 border border-slate-100 hover:bg-white hover:shadow-md transition-all">
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center font-extrabold text-lg shadow-sm
                    ${sub.status === 'safe' ? 'bg-emerald-100 text-emerald-600' : 
                      sub.status === 'warning' ? 'bg-amber-100 text-amber-600' : 
                      'bg-red-100 text-red-600'}`}>
                    {sub.name[0]}
                  </div>
                  <div>
                    <h4 className="font-extrabold text-slate-800">{sub.name}</h4>
                    <p className="text-xs font-bold text-slate-400">
                      {sub.status === 'safe' ? '안정적' : sub.status === 'warning' ? '보완 필요' : '위험'}
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center gap-3">
                  <div className="w-24 sm:w-32 h-3 bg-slate-200 rounded-full overflow-hidden">
                    <div 
                      className={`h-full rounded-full ${
                        sub.status === 'safe' ? 'bg-emerald-400' : 
                        sub.status === 'warning' ? 'bg-amber-400' : 
                        'bg-red-400'
                      }`}
                      style={{ width: `${sub.score}%` }}
                    />
                  </div>
                  {sub.status === 'safe' ? <CheckCircle2 size={20} className="text-emerald-500" /> : 
                   sub.status === 'warning' ? <HelpCircle size={20} className="text-amber-500" /> : 
                   <AlertCircle size={20} className="text-red-500" />}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
