import axios from 'axios';

// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Create axios instance with default configuration
const apiClient = axios.create({
    baseURL: API_BASE_URL,
    timeout: 120000, // 120s — study/research modes can take longer
    headers: {
        'Content-Type': 'application/json',
    },
    withCredentials: false,
});

// Request interceptor - Add auth tokens, request ID, etc.
apiClient.interceptors.request.use(
    (config) => {
        // Add JWT token if available
        const token = localStorage.getItem('auth_token');
        if (token) {
            config.headers['Authorization'] = `Bearer ${token}`;
        }
        config.headers['X-Request-ID'] = `req-${Date.now()}-${Math.random().toString(36).substring(7)}`;
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Response interceptor - Handle errors consistently
apiClient.interceptors.response.use(
    (response) => {
        return response;
    },
    (error) => {
        if (error.response) {
            console.error('API Error:', error.response.status, error.response.data);
            if (error.response.status === 401) {
                console.error('Unauthorized - Please login');
                // Don't auto-redirect here; let the AuthContext handle it
            }
        } else if (error.request) {
            console.error('Network Error: No response from server');
        } else {
            console.error('Request Error:', error.message);
        }
        return Promise.reject(error);
    }
);

export default apiClient;

// ============================================
// Type Definitions
// ============================================

export interface Message {
    role: 'user' | 'assistant';
    content: string;
}

export type PipelineMode = 'auto' | 'fast' | 'study' | 'research' | 'chat';

export interface QueryRequest {
    query: string;
    conversation_history?: Message[];
    options?: Record<string, any>;
    mode?: PipelineMode;
    session_id?: number;
    doc_ids?: string[];
}

export interface Citation {
    text: string;
    source: string;
    page?: number;
    confidence: number;
}

export interface QueryMetadata {
    query_type?: string;
    retrieval_strategy: string;
    pipeline_mode?: PipelineMode;
    chunks_retrieved: number;
    chunks_used: number;
    attempts: number;
    tokens_used: number;
    retrieval_time_ms: number;
    generation_time_ms: number;
    total_time_ms: number;
}

export interface QueryResponse {
    answer: string;
    citations: Citation[];
    confidence: number;
    metadata: QueryMetadata;
    cached: boolean;
    cache_hit_similarity?: number;
}

// ============================================
// Auth API
// ============================================

export const loginUser = async (email: string, password: string) => {
    const res = await apiClient.post('/api/v1/auth/login', { email, password });
    return res.data;
};

export const registerUser = async (email: string, password: string, full_name: string) => {
    const res = await apiClient.post('/api/v1/auth/register', { email, password, full_name });
    return res.data;
};

export const getCurrentUser = async () => {
    const res = await apiClient.get('/api/v1/auth/me');
    return res.data;
};

export const verifyEmail = async (email: string, code: string) => {
    const res = await apiClient.post('/api/v1/auth/verify-email', { email, code });
    return res.data;
};

export const resendCode = async (email: string) => {
    const res = await apiClient.post('/api/v1/auth/resend-code', { email });
    return res.data;
};

export const googleLogin = async (credential: string) => {
    const res = await apiClient.post('/api/v1/auth/google', { credential });
    return res.data;
};

export const forgotPassword = async (email: string) => {
    const res = await apiClient.post('/api/v1/auth/forgot-password', { email });
    return res.data;
};

export const resetPassword = async (email: string, code: string, new_password: string) => {
    const res = await apiClient.post('/api/v1/auth/reset-password', { email, code, new_password });
    return res.data;
};

// ============================================
// Chat History API
// ============================================

export interface ChatSession {
    id: number;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
}

export interface ChatMessage {
    id: number;
    role: 'user' | 'assistant';
    content: string;
    mode?: string;
    confidence?: number;
    citations?: any[];
    created_at: string;
}

export const getSessions = async (): Promise<ChatSession[]> => {
    const res = await apiClient.get('/api/v1/chat/sessions');
    return res.data.sessions;
};

export const createSession = async (title?: string): Promise<ChatSession> => {
    const res = await apiClient.post('/api/v1/chat/sessions', { title: title || 'New Chat' });
    return res.data;
};

export const getSessionMessages = async (sessionId: number): Promise<ChatMessage[]> => {
    const res = await apiClient.get(`/api/v1/chat/sessions/${sessionId}/messages`);
    return res.data.messages;
};

export const deleteSession = async (sessionId: number): Promise<void> => {
    await apiClient.delete(`/api/v1/chat/sessions/${sessionId}`);
};

// ============================================
// Core API Functions
// ============================================

/**
 * Ask a question to the AI assistant
 */
export const askQuestion = async (request: QueryRequest): Promise<QueryResponse> => {
    const response = await apiClient.post<QueryResponse>('/api/v1/query/ask', request);
    return response.data;
};

/**
 * Upload a PDF document
 */
export const uploadDocument = async (file: File, sessionId?: number, tenantId?: string): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    if (tenantId) {
        formData.append('tenant_id', tenantId);
    }

    // Send session_id as URL query param (Form param is unreliable with multipart)
    const params = sessionId ? `?session_id=${sessionId}` : '';

    const response = await apiClient.post(`/api/v1/documents/upload${params}`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });

    return response.data;
};

/**
 * Get learning progress statistics
 */
export const getLearningProgress = async (): Promise<any> => {
    const response = await apiClient.get('/api/v1/progress');
    return response.data;
};

/**
 * Submit feedback on an answer
 */
export const submitFeedback = async (
    queryId: string,
    helpful: boolean,
    comment?: string
): Promise<any> => {
    const response = await apiClient.post('/api/v1/feedback', {
        query_id: queryId,
        helpful,
        comment,
    });
    return response.data;
};

/**
 * Health check
 */
export const healthCheck = async (): Promise<any> => {
    const response = await apiClient.get('/api/v1/health');
    return response.data;
};
