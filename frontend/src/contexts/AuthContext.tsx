import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import apiClient from '../services/api';
import { verifyEmail as verifyEmailApi, googleLogin as googleLoginApi } from '../services/api';

// ─── Types ─────────────────────────────────────────────────────────────────────

interface User {
    id: number;
    email: string;
    full_name: string;
    provider: string;
    avatar_url?: string;
    created_at: string;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    login: (email: string, password: string) => Promise<void>;
    register: (email: string, password: string, fullName: string) => Promise<{ requiresVerification: boolean; email: string }>;
    verifyEmail: (email: string, code: string) => Promise<void>;
    googleLogin: (credential: string) => Promise<void>;
    logout: () => void;
}

// ─── Context ───────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function useAuth(): AuthContextType {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within AuthProvider');
    return ctx;
}

// ─── Provider ──────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    // Load token from localStorage on mount
    useEffect(() => {
        const savedToken = localStorage.getItem('auth_token');
        if (savedToken) {
            setToken(savedToken);
            // Fetch user profile
            apiClient.get('/api/v1/auth/me', {
                headers: { Authorization: `Bearer ${savedToken}` },
            })
                .then((res) => {
                    setUser(res.data);
                })
                .catch(() => {
                    // Token expired or invalid
                    localStorage.removeItem('auth_token');
                    setToken(null);
                })
                .finally(() => setIsLoading(false));
        } else {
            setIsLoading(false);
        }
    }, []);

    // Update axios default header when token changes
    useEffect(() => {
        if (token) {
            apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        } else {
            delete apiClient.defaults.headers.common['Authorization'];
        }
    }, [token]);

    const login = useCallback(async (email: string, password: string) => {
        const res = await apiClient.post('/api/v1/auth/login', { email, password });
        const { token: newToken, user: userData } = res.data;
        localStorage.setItem('auth_token', newToken);
        setToken(newToken);
        setUser(userData);
    }, []);

    const register = useCallback(async (email: string, password: string, fullName: string) => {
        const res = await apiClient.post('/api/v1/auth/register', {
            email,
            password,
            full_name: fullName,
        });
        // Registration now returns { requires_verification, email, message }
        // Do NOT auto-login — user must verify email first
        return {
            requiresVerification: res.data.requires_verification || false,
            email: res.data.email || email,
        };
    }, []);

    const verifyEmail = useCallback(async (email: string, code: string) => {
        const res = await verifyEmailApi(email, code);
        const { token: newToken, user: userData } = res;
        localStorage.setItem('auth_token', newToken);
        setToken(newToken);
        setUser(userData);
    }, []);

    const handleGoogleLogin = useCallback(async (credential: string) => {
        const res = await googleLoginApi(credential);
        const { token: newToken, user: userData } = res;
        localStorage.setItem('auth_token', newToken);
        setToken(newToken);
        setUser(userData);
    }, []);

    const logout = useCallback(() => {
        localStorage.removeItem('auth_token');
        setToken(null);
        setUser(null);
    }, []);

    return (
        <AuthContext.Provider
            value={{
                user,
                token,
                isAuthenticated: !!user,
                isLoading,
                login,
                register,
                verifyEmail,
                googleLogin: handleGoogleLogin,
                logout,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}

export default AuthContext;
