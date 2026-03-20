import React, { useEffect } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { auth } from '../lib/firebase';
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
    if (code && provider) {
      handleSocialLogin(provider, code);
    }
  }, [provider, searchParams]);

  const handleSocialLogin = async (provider: string, code: string) => {
    try {
      const response = await api.post('/api/v1/auth/social', {
        provider,
        code,
      });

      const { firebase_custom_token } = response;
      await signInWithCustomToken(auth, firebase_custom_token);

      toast.success('Poli에 오신 것을 환영합니다! 🎉');
      navigate('/');
    } catch (error) {
      console.error('Social login failed:', error);
      toast.error('로그인에 실패했습니다. 다시 시도해 주세요.');
      navigate('/auth');
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-slate-50">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="text-center"
      >
        <div className="w-20 h-20 bg-blue-500 rounded-3xl flex items-center justify-center mb-6 mx-auto shadow-lg shadow-blue-500/20">
          <Bot size={40} className="text-white animate-pulse" />
        </div>
        <h2 className="text-2xl font-extrabold text-slate-800 mb-2">Poli가 로그인하는 중...</h2>
        <p className="text-slate-500 font-medium">잠시만 기다려 주세요.</p>
      </motion.div>
    </div>
  );
}
