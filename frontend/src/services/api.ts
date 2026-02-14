import axios from 'axios';

// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Create axios instance with default configuration
const apiClient = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000, // 30 seconds for document uploads
    headers: {
        'Content-Type': 'application/json',
    },
    withCredentials: false, // Disabled for CORS compatibility
});

// Request interceptor - Add auth tokens, request ID, etc.
apiClient.interceptors.request.use(
    (config) => {
        // Add tenant/user context (mock for now, replace with real auth)
        config.headers['X-Tenant-ID'] = 'demo-tenant';
        config.headers['X-User-ID'] = 'demo-user';

        // Add request ID for tracing
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
        // Handle common errors
        if (error.response) {
            // Server responded with error status
            console.error('API Error:', error.response.status, error.response.data);

            if (error.response.status === 401) {
                // Handle unauthorized - redirect to login, etc.
                console.error('Unauthorized - Please login');
            }
        } else if (error.request) {
            // Request made but no response
            console.error('Network Error: No response from server');
        } else {
            // Something else happened
            console.error('Request Error:', error.message);
        }

        return Promise.reject(error);
    }
);

export default apiClient;

// ============================================
// API Service Functions
// ============================================

export interface Message {
    role: 'user' | 'assistant';
    content: string;
}

export interface QueryRequest {
    query: string;
    conversation_history?: Message[];
    options?: Record<string, any>;
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
export const uploadDocument = async (file: File, tenantId?: string): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    if (tenantId) {
        formData.append('tenant_id', tenantId);
    }

    const response = await apiClient.post('/api/v1/documents/upload', formData, {
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
