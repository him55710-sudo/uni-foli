import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AnimatePresence, motion } from 'motion/react';
import { Building2, CheckCircle2, MessageSquare, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';
import { useAuthStore } from '../store/authStore';
import { submitInquiry, type InquiryErrors, type InquiryPayload, validateInquiry } from '../lib/inquiries';

interface B2BPartnershipModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const initialForm: InquiryPayload = {
  inquiry_type: 'partnership',
  institution_name: '',
  name: '',
  phone: '',
  email: '',
  institution_type: 'school',
  message: '',
  source_path: '/app?source=partnership-modal',
  metadata: {
    entry_point: 'app_partnership_modal',
  },
};

export function B2BPartnershipModal({ isOpen, onClose }: B2BPartnershipModalProps) {
  const authUser = useAuth().user;
  const dbUser = useAuthStore(state => state.user);
  const [form, setForm] = useState<InquiryPayload>(initialForm);
  const [errors, setErrors] = useState<InquiryErrors>({});
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    setSubmitted(false);
    setErrors({});
    setForm({
      ...initialForm,
      name: dbUser?.name || authUser?.displayName || '',
      email: dbUser?.email || authUser?.email || '',
    });
  }, [authUser?.displayName, authUser?.email, dbUser?.email, dbUser?.name, isOpen]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    const validation = validateInquiry(form);
    setErrors(validation);
    if (Object.keys(validation).length > 0) {
      toast.error('필수 항목을 확인해 주세요.');
      return;
    }

    setIsSubmitting(true);
    const loadingId = toast.loading('협업 문의를 접수하고 있습니다...');

    try {
      await submitInquiry(form);
      setSubmitted(true);
      setErrors({});
      toast.success('협업 문의가 접수되었습니다. 남겨주신 연락처로 확인 후 안내드리겠습니다.', { id: loadingId });
    } catch (error) {
      console.error('Partnership inquiry failed:', error);
      toast.error('문의 접수에 실패했습니다. 잠시 후 다시 시도해 주세요.', { id: loadingId });
    } finally {
      setIsSubmitting(false);
    }
  };

  const closeModal = () => {
    setSubmitted(false);
    setErrors({});
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeModal}
            className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="relative w-full max-w-xl overflow-hidden rounded-[2.5rem] bg-white shadow-2xl"
          >
            <div className="p-8 md:p-10">
              <button
                onClick={closeModal}
                className="absolute right-6 top-6 rounded-full p-2 text-slate-400 transition-colors hover:bg-slate-50 hover:text-slate-600"
                aria-label="협업 문의 모달 닫기"
              >
                <X size={20} />
              </button>

              {!submitted ? (
                <>
                  <div className="mb-8">
                    <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-blue-100 bg-blue-50 text-blue-600 shadow-sm">
                      <Building2 size={24} />
                    </div>
                    <h2 className="text-2xl font-black tracking-tight text-slate-800">학교·학원 협업 문의</h2>
                    <p className="mt-2 text-sm font-medium leading-6 text-slate-500">
                      공개 문의 허브와 같은 실제 접수 API로 연결됩니다. 빠르게 남기고, 더 자세한 내용은 지원 허브에서 이어서 작성할 수 있습니다.
                    </p>
                  </div>

                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <Field
                        id="partnership-org"
                        label="기관명"
                        required
                        error={errors.institution_name}
                        value={form.institution_name ?? ''}
                        onChange={value => setForm(prev => ({ ...prev, institution_name: value }))}
                      />
                      <Field
                        id="partnership-name"
                        label="담당자명"
                        required
                        error={errors.name}
                        value={form.name ?? ''}
                        onChange={value => setForm(prev => ({ ...prev, name: value }))}
                      />
                      <Field
                        id="partnership-phone"
                        label="연락처"
                        required
                        error={errors.phone}
                        value={form.phone ?? ''}
                        onChange={value => setForm(prev => ({ ...prev, phone: value }))}
                      />
                      <Field
                        id="partnership-email"
                        label="이메일"
                        required
                        type="email"
                        error={errors.email}
                        value={form.email}
                        onChange={value => setForm(prev => ({ ...prev, email: value }))}
                      />
                    </div>

                    <div className="space-y-2">
                      <label htmlFor="partnership-type" className="block text-sm font-black text-slate-700">
                        기관 유형<span className="ml-1 text-blue-600">*</span>
                      </label>
                      <select
                        id="partnership-type"
                        value={form.institution_type ?? 'school'}
                        onChange={event =>
                          setForm(prev => ({
                            ...prev,
                            institution_type: event.target.value as InquiryPayload['institution_type'],
                          }))
                        }
                        className={`w-full rounded-2xl border bg-slate-50 px-4 py-3.5 text-sm font-medium text-slate-700 outline-none ${
                          errors.institution_type ? 'border-red-200 focus:border-red-400' : 'border-slate-200 focus:border-blue-500'
                        }`}
                      >
                        <option value="school">학교</option>
                        <option value="academy">학원</option>
                        <option value="other">기타</option>
                      </select>
                      {errors.institution_type ? <p className="text-xs font-bold text-red-600">{errors.institution_type}</p> : null}
                    </div>

                    <div className="space-y-2">
                      <label htmlFor="partnership-message" className="block text-sm font-black text-slate-700">
                        문의 내용<span className="ml-1 text-blue-600">*</span>
                      </label>
                      <textarea
                        id="partnership-message"
                        rows={5}
                        value={form.message}
                        onChange={event => setForm(prev => ({ ...prev, message: event.target.value }))}
                        placeholder="도입 목적, 운영 대상, 확인하고 싶은 범위를 남겨 주세요."
                        className={`w-full rounded-2xl border bg-slate-50 px-4 py-3.5 text-sm font-medium text-slate-700 outline-none ${
                          errors.message ? 'border-red-200 focus:border-red-400' : 'border-slate-200 focus:border-blue-500'
                        }`}
                      />
                      {errors.message ? <p className="text-xs font-bold text-red-600">{errors.message}</p> : null}
                    </div>

                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl bg-blue-600 py-4 text-sm font-black text-white shadow-lg shadow-blue-500/20 transition-all hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <MessageSquare size={18} />
                      {isSubmitting ? '접수 중...' : '협업 문의 보내기'}
                    </button>

                    <div className="flex flex-col items-center gap-2 pt-2 text-center">
                      <p className="text-[11px] font-medium text-slate-400">
                        더 자세한 협업 정보나 다른 문의 유형은 공개 지원 허브에서 이어서 남길 수 있습니다.
                      </p>
                      <Link to="/contact?type=partnership" onClick={closeModal} className="text-xs font-bold text-blue-600 hover:text-blue-700">
                        지원 허브로 이동
                      </Link>
                    </div>
                  </form>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center py-10 text-center">
                  <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full border border-emerald-100 bg-emerald-50 text-emerald-500 shadow-sm">
                    <CheckCircle2 size={32} />
                  </div>
                  <h3 className="text-2xl font-black tracking-tight text-slate-800">협업 문의 접수 완료</h3>
                  <p className="mt-2 max-w-[320px] text-sm font-medium leading-6 text-slate-500">
                    남겨주신 연락처와 기관 정보를 기준으로 검토 후 안내드리겠습니다. 더 자세한 정보는 지원 허브에서 추가로 남길 수 있습니다.
                  </p>
                  <div className="mt-8 flex flex-wrap justify-center gap-3">
                    <Link
                      to="/contact?type=partnership"
                      onClick={closeModal}
                      className="rounded-2xl border border-slate-200 bg-white px-6 py-3 text-sm font-black text-slate-700 hover:bg-slate-50"
                    >
                      지원 허브 보기
                    </Link>
                    <button
                      onClick={closeModal}
                      className="rounded-2xl bg-slate-900 px-6 py-3 text-sm font-black text-white hover:bg-black"
                    >
                      닫기
                    </button>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        </div>
      ) : null}
    </AnimatePresence>
  );
}

function Field({
  id,
  label,
  required = false,
  error,
  value,
  type = 'text',
  onChange,
}: {
  id: string;
  label: string;
  required?: boolean;
  error?: string;
  value: string;
  type?: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="block text-sm font-black text-slate-700">
        {label}
        {required ? <span className="ml-1 text-blue-600">*</span> : null}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={event => onChange(event.target.value)}
        className={`w-full rounded-2xl border bg-slate-50 px-4 py-3.5 text-sm font-medium text-slate-700 outline-none ${
          error ? 'border-red-200 focus:border-red-400' : 'border-slate-200 focus:border-blue-500'
        }`}
      />
      {error ? <p className="text-xs font-bold text-red-600">{error}</p> : null}
    </div>
  );
}
