import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts';
import { FolderOpen, AlertCircle, CheckCircle2, HelpCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../lib/api';

const radarData = [
  { subject: '진로 일관성', A: 85, fullMark: 100 },
  { subject: '전공적합성', A: 65, fullMark: 100 },
  { subject: '성장가능성', A: 90, fullMark: 100 },
  { subject: '인성', A: 95, fullMark: 100 },
  { subject: '탐구성', A: 75, fullMark: 100 },
  { subject: '리더십', A: 80, fullMark: 100 },
];

const subjects = [
  { name: '국어', status: 'safe', score: 92 },
  { name: '수학', status: 'warning', score: 68 },
  { name: '영어', status: 'safe', score: 88 },
  { name: '과학', status: 'danger', score: 55 },
  { name: '사회', status: 'safe', score: 95 },
] as const;

export function Record() {
  const navigate = useNavigate();
  const { user, isGuestSession } = useAuth();
  const [isUploading, setIsUploading] = useState(false);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file || isUploading) return;

      const targetMajor = window.prompt('목표 전공을 입력해주세요. (예: 컴퓨터공학과)', '컴퓨터공학과')?.trim() || '미정';
      setIsUploading(true);
      const loadingId = toast.loading('프로젝트를 만들고 PDF를 업로드하는 중입니다...');

      try {
        const project = await api.post<{ id: string }>('/api/v1/projects', {
          title: `${targetMajor} 기록 분석`,
          description: `업로드 파일: ${file.name}`,
          target_major: targetMajor,
        });

        const formData = new FormData();
        formData.append('file', file);
        await api.post(`/api/v1/projects/${project.id}/uploads`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });

        toast.success('업로드 완료! 워크숍으로 이동합니다.', { id: loadingId });
        navigate(`/workshop/${project.id}?major=${encodeURIComponent(targetMajor)}`);
      } catch (error) {
        console.error('Upload flow failed:', error);
        toast.error('업로드에 실패했습니다. 잠시 후 다시 시도해주세요.', { id: loadingId });
      } finally {
        setIsUploading(false);
      }
    },
    [isUploading, navigate],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: false,
    disabled: isUploading,
  });

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <div className="mb-8">
        <h1 className="mb-2 text-3xl font-extrabold text-slate-800">
          {user?.displayName || (isGuestSession ? '게스트' : '사용자')}님의 학생부 대시보드
        </h1>
        <p className="font-medium text-slate-500">
          파일을 업로드하면 프로젝트가 생성되고 워크숍으로 바로 연결됩니다.
        </p>
      </div>

      <div
        {...getRootProps()}
        className={`cursor-pointer border-2 border-dashed p-10 text-center transition-colors clay-card ${
          isDragActive ? 'border-blue-400 bg-blue-50' : 'border-blue-200 hover:border-blue-400 hover:bg-slate-50'
        } ${isUploading ? 'cursor-not-allowed opacity-70' : ''}`}
      >
        <input {...getInputProps()} />
        <div className="mx-auto mb-4 flex h-20 w-20 rotate-3 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-400 to-blue-600 shadow-lg shadow-blue-500/30">
          <FolderOpen size={36} className="text-white" />
        </div>
        <h3 className="mb-2 text-xl font-extrabold text-slate-800">NEIS 학생부 PDF를 업로드하세요</h3>
        <p className="font-medium text-slate-500">
          클릭 또는 드래그 앤 드롭 (PDF 1개, 최대 50MB)
          {isUploading ? ' · 업로드 진행 중...' : ''}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <div className="relative flex flex-col p-6 sm:p-8 clay-card">
          <h3 className="mb-6 text-xl font-extrabold text-slate-800">6대 역량 분석</h3>
          <div className="h-64 w-full sm:h-80">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                <PolarGrid stroke="#E2E8F0" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: '#475569', fontSize: 13, fontWeight: 700 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                <Radar name="Student" dataKey="A" stroke="#3B82F6" strokeWidth={3} fill="#60A5FA" fillOpacity={0.5} />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          <div
            className="absolute bottom-6 right-6 z-10 max-w-[220px] animate-bounce rounded-2xl rounded-br-sm border border-blue-100 bg-white p-4 shadow-xl"
            style={{ animationDuration: '3s' }}
          >
            <div className="mb-1 flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-500 text-xs font-bold text-white">P</div>
              <span className="text-xs font-extrabold text-blue-600">Poli 조언</span>
            </div>
            <p className="text-sm font-bold leading-tight text-slate-700">
              전공 적합성 파트를 보강하면 종합 점수를 빠르게 끌어올릴 수 있어요.
            </p>
          </div>
        </div>

        <div className="p-6 sm:p-8 clay-card">
          <h3 className="mb-6 text-xl font-extrabold text-slate-800">주요 과목 상태</h3>
          <div className="space-y-5">
            {subjects.map((subject) => (
              <div
                key={subject.name}
                className="flex items-center justify-between rounded-2xl border border-slate-100 bg-slate-50 p-4 transition-all hover:bg-white hover:shadow-md"
              >
                <div className="flex items-center gap-4">
                  <div
                    className={`flex h-12 w-12 items-center justify-center rounded-xl text-lg font-extrabold shadow-sm ${
                      subject.status === 'safe'
                        ? 'bg-emerald-100 text-emerald-600'
                        : subject.status === 'warning'
                          ? 'bg-amber-100 text-amber-600'
                          : 'bg-red-100 text-red-600'
                    }`}
                  >
                    {subject.name[0]}
                  </div>
                  <div>
                    <h4 className="font-extrabold text-slate-800">{subject.name}</h4>
                    <p className="text-xs font-bold text-slate-400">
                      {subject.status === 'safe'
                        ? '안정'
                        : subject.status === 'warning'
                          ? '보완 필요'
                          : '집중 보완'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="h-3 w-24 overflow-hidden rounded-full bg-slate-200 sm:w-32">
                    <div
                      className={`h-full rounded-full ${
                        subject.status === 'safe'
                          ? 'bg-emerald-400'
                          : subject.status === 'warning'
                            ? 'bg-amber-400'
                            : 'bg-red-400'
                      }`}
                      style={{ width: `${subject.score}%` }}
                    />
                  </div>
                  {subject.status === 'safe' ? (
                    <CheckCircle2 size={20} className="text-emerald-500" />
                  ) : subject.status === 'warning' ? (
                    <HelpCircle size={20} className="text-amber-500" />
                  ) : (
                    <AlertCircle size={20} className="text-red-500" />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
