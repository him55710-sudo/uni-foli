import React from 'react';
import { ErrorBoundary, FallbackProps } from 'react-error-boundary';
import { AlertCircle, RotateCcw } from 'lucide-react';

function ErrorFallback({ error, resetErrorBoundary }: { error: any; resetErrorBoundary: () => void }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-lg overflow-hidden rounded-[2rem] border border-red-100 bg-white shadow-2xl">
        <div className="bg-red-50 p-8 text-center sm:p-12">
          <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-red-100 shadow-inner">
            <AlertCircle size={40} className="text-red-500" />
          </div>
          <h2 className="mb-4 text-3xl font-black tracking-tight text-slate-800">
            앱 실행 중 오류가 발생했습니다.
          </h2>
          <p className="mb-8 font-medium text-slate-500 leading-relaxed">
            일시적인 시스템 오류이거나 네트워크 문제일 수 있습니다. 작업하시던 데이터는 안전하게 보관되니 안심하고 새로고침 해주세요.
          </p>
          <div className="mb-8 overflow-hidden rounded-xl border border-red-100 bg-red-50/50 p-4 text-left">
            <p className="text-xs font-mono text-red-800 break-all">{error.message}</p>
          </div>
          <button
            onClick={resetErrorBoundary}
            className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-8 py-4 text-lg font-extrabold text-white shadow-lg transition-transform hover:scale-105 active:scale-95"
          >
            <RotateCcw size={20} />
            다시 시도하기
          </button>
        </div>
      </div>
    </div>
  );
}

export function GlobalErrorBoundary({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary
      FallbackComponent={ErrorFallback}
      onReset={() => {
        window.location.reload();
      }}
    >
      {children}
    </ErrorBoundary>
  );
}
