import React, { useEffect } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { auth, isFirebaseConfigured } from '../lib/firebase';
import { signInWithCustomToken } from 'firebase/auth';
import { api } from '../lib/api';
import { motion } from 'motion/react';
import { Bot } from 'lucide-react';
import toast from 'react-hot-toast';

export function AuthCallback() {
  const { provider } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');

    if (code && state && provider) {
      void handleSocialLogin(provider, code, state);
    }
  }, [provider, searchParams]);

  const handleSocialLogin = async (providerName: string, code: string, state: string) => {
    try {
      if (!auth || !isFirebaseConfigured) {
        throw new Error('소셜 로그인은 Firebase 설정이 필요합니다.');
      }

      const response = await api.post<{ firebase_custom_token: string }>('/api/v1/auth/social', {
        provider: providerName,
        code,
        state,
      });

      await signInWithCustomToken(auth, response.firebase_custom_token);
      toast.success('로그인이 완료되었습니다.');
      navigate('/app');
    } catch (error) {
      console.error('Social login failed:', error);
      toast.error('로그인에 실패했습니다. 다시 시도해 주세요.');
      navigate('/auth');
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <motion.div
        initial={{ opacity: 0, scale: 0.94 }}
        animate={{ opacity: 1, scale: 1 }}
        className="rounded-[32px] border border-slate-200 bg-white p-10 text-center shadow-xl"
      >
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-[28px] bg-blue-500 shadow-lg shadow-blue-500/20">
          <Bot size={40} className="animate-pulse text-white" />
        </div>
        <h2 className="mt-6 text-2xl font-extrabold text-slate-800">로그인 정보를 확인하고 있습니다.</h2>
        <p className="mt-3 text-sm font-medium text-slate-500">잠시만 기다려 주세요.</p>
      </motion.div>
    </div>
  );
}
