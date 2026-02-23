import React, { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Brain, Loader2, KeyRound, ArrowRight, Mail, RefreshCw, Eye, EyeOff, CheckCircle } from 'lucide-react';
import { forgotPassword, resetPassword } from '../services/api';

type Step = 'email' | 'otp' | 'newpass' | 'done';

export default function ForgotPasswordPage() {
    const navigate = useNavigate();
    const [step, setStep] = useState<Step>('email');
    const [email, setEmail] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    // OTP
    const [otpDigits, setOtpDigits] = useState(['', '', '', '', '', '']);
    const otpRefs = useRef<(HTMLInputElement | null)[]>([]);
    const [resendCooldown, setResendCooldown] = useState(0);
    const [resendLoading, setResendLoading] = useState(false);

    // New password
    const [newPassword, setNewPassword] = useState('');
    const [confirmPw, setConfirmPw] = useState('');
    const [showPw, setShowPw] = useState(false);
    const [otpCode, setOtpCode] = useState('');

    useEffect(() => {
        if (resendCooldown > 0) {
            const t = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000);
            return () => clearTimeout(t);
        }
    }, [resendCooldown]);

    // ── Step 1: Enter email ───────────────────────────────────────────────
    const handleEmailSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            await forgotPassword(email);
            setStep('otp');
            setResendCooldown(30);
            setTimeout(() => otpRefs.current[0]?.focus(), 100);
        } catch (err: any) {
            setError(err?.response?.data?.detail || 'Something went wrong');
        } finally {
            setLoading(false);
        }
    };

    // ── Step 2: Enter OTP ────────────────────────────────────────────────
    const handleOtpChange = (index: number, value: string) => {
        if (value.length > 1) value = value.slice(-1);
        if (value && !/^\d$/.test(value)) return;
        const d = [...otpDigits];
        d[index] = value;
        setOtpDigits(d);
        if (value && index < 5) otpRefs.current[index + 1]?.focus();
        if (d.every(x => x !== '') && d.join('').length === 6) {
            setOtpCode(d.join(''));
            setStep('newpass');
        }
    };

    const handleOtpKeyDown = (index: number, e: React.KeyboardEvent) => {
        if (e.key === 'Backspace' && !otpDigits[index] && index > 0) {
            otpRefs.current[index - 1]?.focus();
        }
    };

    const handleOtpPaste = (e: React.ClipboardEvent) => {
        e.preventDefault();
        const p = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
        if (p.length === 6) {
            setOtpDigits(p.split(''));
            setOtpCode(p);
            setStep('newpass');
        }
    };

    const handleResend = async () => {
        if (resendCooldown > 0) return;
        setResendLoading(true);
        try {
            await forgotPassword(email);
            setResendCooldown(30);
            setError('');
        } catch {
            setError('Failed to resend code');
        } finally {
            setResendLoading(false);
        }
    };

    // ── Step 3: Set new password ──────────────────────────────────────────
    const handleResetSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        if (newPassword !== confirmPw) { setError('Passwords do not match'); return; }
        if (newPassword.length < 6) { setError('Password must be at least 6 characters'); return; }

        setLoading(true);
        try {
            await resetPassword(email, otpCode, newPassword);
            setStep('done');
        } catch (err: any) {
            setError(err?.response?.data?.detail || 'Failed to reset password');
        } finally {
            setLoading(false);
        }
    };

    // ── Shared wrapper ────────────────────────────────────────────────────
    const Wrapper = ({ children }: { children: React.ReactNode }) => (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 via-blue-50 to-purple-50 dark:from-dark-900 dark:via-dark-900 dark:to-dark-800 px-4">
            <div className="w-full max-w-md">
                {children}
            </div>
        </div>
    );

    // ── Step 4: Success ───────────────────────────────────────────────────
    if (step === 'done') {
        return (
            <Wrapper>
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center p-4 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl shadow-lg mb-4">
                        <CheckCircle className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Password Reset!</h1>
                    <p className="text-gray-600 dark:text-gray-400 mt-2">Your password has been updated successfully.</p>
                </div>
                <button
                    onClick={() => navigate('/login')}
                    className="w-full btn btn-primary py-3 text-base font-semibold"
                >
                    Go to Login <ArrowRight className="w-4 h-4 ml-2" />
                </button>
            </Wrapper>
        );
    }

    // ── Step 3: New password form ─────────────────────────────────────────
    if (step === 'newpass') {
        return (
            <Wrapper>
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center p-4 bg-gradient-to-br from-primary-600 to-purple-600 rounded-2xl shadow-lg shadow-primary-600/30 mb-4">
                        <KeyRound className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Set new password</h1>
                    <p className="text-gray-600 dark:text-gray-400 mt-2">Choose a strong password for your account.</p>
                </div>
                <div className="bg-white dark:bg-dark-800 rounded-2xl shadow-xl p-8 border border-gray-200 dark:border-dark-700">
                    {error && (
                        <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm">{error}</div>
                    )}
                    <form onSubmit={handleResetSubmit} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">New Password</label>
                            <div className="relative">
                                <input type={showPw ? 'text' : 'password'} value={newPassword} onChange={e => setNewPassword(e.target.value)}
                                    className="input pr-10" placeholder="Min 6 characters" required minLength={6} autoFocus />
                                <button type="button" onClick={() => setShowPw(!showPw)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                                    {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
                                </button>
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Confirm Password</label>
                            <input type="password" value={confirmPw} onChange={e => setConfirmPw(e.target.value)}
                                className="input" placeholder="Re-enter password" required minLength={6} />
                        </div>
                        <button type="submit" disabled={loading} className="w-full btn btn-primary py-3 text-base font-semibold">
                            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <>Reset Password <ArrowRight className="w-4 h-4 ml-2" /></>}
                        </button>
                    </form>
                </div>
            </Wrapper>
        );
    }

    // ── Step 2: OTP screen ────────────────────────────────────────────────
    if (step === 'otp') {
        return (
            <Wrapper>
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center p-4 bg-gradient-to-br from-orange-500 to-red-500 rounded-2xl shadow-lg mb-4">
                        <Mail className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Check your email</h1>
                    <p className="text-gray-600 dark:text-gray-400 mt-2">
                        We sent a reset code to<br />
                        <span className="font-semibold text-primary-600 dark:text-primary-400">{email}</span>
                    </p>
                </div>
                <div className="bg-white dark:bg-dark-800 rounded-2xl shadow-xl p-8 border border-gray-200 dark:border-dark-700">
                    {error && (
                        <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm">{error}</div>
                    )}
                    <div className="flex justify-center gap-2 mb-6" onPaste={handleOtpPaste}>
                        {otpDigits.map((d, i) => (
                            <input key={i} ref={el => { otpRefs.current[i] = el; }} type="text" inputMode="numeric" maxLength={1}
                                value={d} onChange={e => handleOtpChange(i, e.target.value)} onKeyDown={e => handleOtpKeyDown(i, e)}
                                className="w-12 h-14 text-center text-2xl font-bold rounded-xl border-2 border-gray-200 dark:border-dark-600 bg-gray-50 dark:bg-dark-700 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 outline-none transition-all text-gray-900 dark:text-gray-100" />
                        ))}
                    </div>
                    <div className="text-center">
                        <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">Didn't receive the code?</p>
                        <button onClick={handleResend} disabled={resendCooldown > 0 || resendLoading}
                            className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary-600 hover:text-primary-700 dark:text-primary-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                            {resendLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                            {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend Code'}
                        </button>
                    </div>
                </div>
            </Wrapper>
        );
    }

    // ── Step 1: Email form ────────────────────────────────────────────────
    return (
        <Wrapper>
            <div className="text-center mb-8">
                <div className="inline-flex items-center space-x-3 mb-4">
                    <div className="p-3 bg-gradient-to-br from-primary-600 to-purple-600 rounded-xl shadow-lg shadow-primary-600/30">
                        <Brain className="w-8 h-8 text-white" />
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold bg-gradient-to-r from-primary-600 to-purple-600 bg-clip-text text-transparent">StudyAI</h1>
                        <p className="text-sm text-gray-500 dark:text-gray-400">Your Learning Companion</p>
                    </div>
                </div>
            </div>
            <div className="bg-white dark:bg-dark-800 rounded-2xl shadow-xl p-8 border border-gray-200 dark:border-dark-700">
                <div className="flex items-center space-x-2 mb-2">
                    <KeyRound className="w-5 h-5 text-primary-600" />
                    <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Forgot password?</h2>
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">Enter your email and we'll send you a code to reset it.</p>

                {error && (
                    <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm">{error}</div>
                )}

                <form onSubmit={handleEmailSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
                        <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                            className="input" placeholder="you@example.com" required autoFocus />
                    </div>
                    <button type="submit" disabled={loading} className="w-full btn btn-primary py-3 text-base font-semibold">
                        {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <>Send Reset Code <ArrowRight className="w-4 h-4 ml-2" /></>}
                    </button>
                </form>

                <p className="mt-6 text-center text-sm text-gray-600 dark:text-gray-400">
                    Remember your password?{' '}
                    <Link to="/login" className="font-semibold text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300">
                        Sign in &rarr;
                    </Link>
                </p>
            </div>
        </Wrapper>
    );
}
