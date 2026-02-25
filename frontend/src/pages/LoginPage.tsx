import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Brain, Loader2, Eye, EyeOff, Sparkles, ArrowRight, Mail, RefreshCw } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { resendCode } from '../services/api';

declare global {
    interface Window {
        google?: any;
    }
}

const GOOGLE_CLIENT_ID = '534786966901-g6ntt4l0pjdb9jagvrsn0g64v1c0h7u2.apps.googleusercontent.com';

export default function LoginPage() {
    const { login, verifyEmail, googleLogin } = useAuth();
    const navigate = useNavigate();

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPw, setShowPw] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    // OTP verification (when login returns 403 = email not verified)
    const [showOtp, setShowOtp] = useState(false);
    const [otpDigits, setOtpDigits] = useState(['', '', '', '', '', '']);
    const [verifyLoading, setVerifyLoading] = useState(false);
    const [verifyError, setVerifyError] = useState('');
    const [resendCooldown, setResendCooldown] = useState(0);
    const [resendLoading, setResendLoading] = useState(false);
    const otpRefs = useRef<(HTMLInputElement | null)[]>([]);

    // Google sign-in
    const googleBtnRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (window.google && googleBtnRef.current) {
            window.google.accounts.id.initialize({
                client_id: GOOGLE_CLIENT_ID,
                callback: handleGoogleResponse,
            });
            window.google.accounts.id.renderButton(googleBtnRef.current, {
                theme: 'outline',
                size: 'large',
                width: '100%',
                text: 'signin_with',
                shape: 'pill',
            });
        }
    }, []);

    const handleGoogleResponse = async (response: any) => {
        if (response.credential) {
            setLoading(true);
            setError('');
            try {
                await googleLogin(response.credential);
                navigate('/');
            } catch (err: any) {
                setError(err?.response?.data?.detail || 'Google sign-in failed');
            } finally {
                setLoading(false);
            }
        }
    };

    // Resend cooldown timer
    useEffect(() => {
        if (resendCooldown > 0) {
            const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000);
            return () => clearTimeout(timer);
        }
    }, [resendCooldown]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            await login(email, password);
            navigate('/');
        } catch (err: any) {
            const status = err?.response?.status;
            const msg = err?.response?.data?.detail || 'Login failed. Please try again.';

            if (status === 403 && msg.includes('not verified')) {
                // Email not verified — show OTP screen
                setShowOtp(true);
                setResendCooldown(30);
                setTimeout(() => otpRefs.current[0]?.focus(), 100);
            } else {
                setError(msg);
            }
        } finally {
            setLoading(false);
        }
    };

    const handleOtpChange = (index: number, value: string) => {
        if (value.length > 1) value = value.slice(-1);
        if (value && !/^\d$/.test(value)) return;
        const newDigits = [...otpDigits];
        newDigits[index] = value;
        setOtpDigits(newDigits);
        if (value && index < 5) otpRefs.current[index + 1]?.focus();
        if (newDigits.every(d => d !== '') && newDigits.join('').length === 6) {
            handleVerify(newDigits.join(''));
        }
    };

    const handleOtpKeyDown = (index: number, e: React.KeyboardEvent) => {
        if (e.key === 'Backspace' && !otpDigits[index] && index > 0) {
            otpRefs.current[index - 1]?.focus();
        }
    };

    const handleOtpPaste = (e: React.ClipboardEvent) => {
        e.preventDefault();
        const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
        if (pasted.length === 6) {
            setOtpDigits(pasted.split(''));
            otpRefs.current[5]?.focus();
            handleVerify(pasted);
        }
    };

    const handleVerify = async (code: string) => {
        setVerifyError('');
        setVerifyLoading(true);
        try {
            await verifyEmail(email, code);
            navigate('/');
        } catch (err: any) {
            setVerifyError(err?.response?.data?.detail || 'Invalid verification code');
            setOtpDigits(['', '', '', '', '', '']);
            otpRefs.current[0]?.focus();
        } finally {
            setVerifyLoading(false);
        }
    };

    const handleResend = async () => {
        if (resendCooldown > 0) return;
        setResendLoading(true);
        try {
            await resendCode(email);
            setResendCooldown(30);
            setVerifyError('');
        } catch {
            setVerifyError('Failed to resend code');
        } finally {
            setResendLoading(false);
        }
    };

    // ─── OTP Verification Screen ──────────────────────────────────────────────

    if (showOtp) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 via-blue-50 to-purple-50 dark:from-dark-900 dark:via-dark-900 dark:to-dark-800 px-4">
                <div className="w-full max-w-md">
                    <div className="text-center mb-8">
                        <div className="inline-flex items-center justify-center p-4 bg-gradient-to-br from-primary-600 to-purple-600 rounded-2xl shadow-lg shadow-primary-600/30 mb-4">
                            <Mail className="w-8 h-8 text-white" />
                        </div>
                        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Verify your email</h1>
                        <p className="text-gray-600 dark:text-gray-400 mt-2">
                            A verification code was sent to<br />
                            <span className="font-semibold text-primary-600 dark:text-primary-400">{email}</span>
                        </p>
                    </div>

                    <div className="bg-white dark:bg-dark-800 rounded-2xl shadow-xl p-8 border border-gray-200 dark:border-dark-700">
                        {verifyError && (
                            <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm">
                                {verifyError}
                            </div>
                        )}

                        <div className="flex justify-center gap-2 mb-6" onPaste={handleOtpPaste}>
                            {otpDigits.map((digit, i) => (
                                <input
                                    key={i}
                                    ref={el => { otpRefs.current[i] = el; }}
                                    type="text"
                                    inputMode="numeric"
                                    maxLength={1}
                                    value={digit}
                                    onChange={e => handleOtpChange(i, e.target.value)}
                                    onKeyDown={e => handleOtpKeyDown(i, e)}
                                    className="w-12 h-14 text-center text-2xl font-bold rounded-xl border-2 border-gray-200 dark:border-dark-600 bg-gray-50 dark:bg-dark-700 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 outline-none transition-all text-gray-900 dark:text-gray-100"
                                    disabled={verifyLoading}
                                />
                            ))}
                        </div>

                        {verifyLoading && (
                            <div className="flex items-center justify-center gap-2 mb-4 text-primary-600">
                                <Loader2 className="w-5 h-5 animate-spin" />
                                <span className="text-sm font-medium">Verifying…</span>
                            </div>
                        )}

                        <div className="text-center">
                            <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">Didn't receive the code?</p>
                            <button
                                onClick={handleResend}
                                disabled={resendCooldown > 0 || resendLoading}
                                className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary-600 hover:text-primary-700 dark:text-primary-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                                {resendLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                                {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend Code'}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // ─── Login Form ───────────────────────────────────────────────────────────

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 via-blue-50 to-purple-50 dark:from-dark-900 dark:via-dark-900 dark:to-dark-800 px-4">
            <div className="w-full max-w-md">
                {/* Logo */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center space-x-3 mb-4">
                        <div className="p-3 bg-gradient-to-br from-primary-600 to-purple-600 rounded-xl shadow-lg shadow-primary-600/30">
                            <Brain className="w-8 h-8 text-white" />
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold bg-gradient-to-r from-primary-600 to-purple-600 bg-clip-text text-transparent">
                                StudyAI
                            </h1>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Your Learning Companion</p>
                        </div>
                    </div>
                </div>

                {/* Card */}
                <div className="bg-white dark:bg-dark-800 rounded-2xl shadow-xl p-8 border border-gray-200 dark:border-dark-700">
                    <div className="flex items-center space-x-2 mb-6">
                        <Sparkles className="w-5 h-5 text-primary-600" />
                        <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Welcome back</h2>
                    </div>

                    {/* Google Sign-In */}
                    <div ref={googleBtnRef} className="mb-4" />

                    <div className="relative mb-4">
                        <div className="absolute inset-0 flex items-center">
                            <div className="w-full border-t border-gray-200 dark:border-dark-600"></div>
                        </div>
                        <div className="relative flex justify-center text-sm">
                            <span className="px-3 bg-white dark:bg-dark-800 text-gray-500 dark:text-gray-400">or sign in with email</span>
                        </div>
                    </div>

                    {error && (
                        <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm">
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Email
                            </label>
                            <input
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                className="input"
                                placeholder="you@example.com"
                                required
                                autoFocus
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Password
                            </label>
                            <div className="relative">
                                <input
                                    type={showPw ? 'text' : 'password'}
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="input pr-10"
                                    placeholder="••••••••"
                                    required
                                    minLength={6}
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPw(!showPw)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                                >
                                    {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
                                </button>
                            </div>
                        </div>

                        <div className="flex justify-end">
                            <Link
                                to="/forgot-password"
                                className="text-sm font-medium text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
                            >
                                Forgot password?
                            </Link>
                        </div>

                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full btn btn-primary py-3 text-base font-semibold"
                        >
                            {loading ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : (
                                <>
                                    Sign In
                                    <ArrowRight className="w-4 h-4 ml-2" />
                                </>
                            )}
                        </button>
                    </form>

                    <p className="mt-6 text-center text-sm text-gray-600 dark:text-gray-400">
                        Don't have an account?{' '}
                        <Link
                            to="/signup"
                            className="font-semibold text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
                        >
                            Create one →
                        </Link>
                    </p>
                </div>
            </div>
        </div>
    );
}
