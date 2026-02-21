import React, { useState, useRef, useEffect } from 'react';
import {
    Send,
    Upload,
    Sparkles,
    FileText,
    Loader2,
    Zap,
    BookOpen,
    FlaskConical,
    MessageCircle,
    Cpu,
} from 'lucide-react';
import { askQuestion, uploadDocument, createSession, getSessionMessages, type ChatSession } from '../services/api';
import MarkdownRenderer from '../components/MarkdownRenderer';

// ─── Types ─────────────────────────────────────────────────────────────────────

interface Message {
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    confidence?: number;
    citations?: any[];
    mode?: PipelineMode;
}

type PipelineMode = 'auto' | 'fast' | 'study' | 'research' | 'chat';

interface ModeConfig {
    id: PipelineMode;
    label: string;
    icon: React.ReactNode;
    description: string;
    color: string;
    badge: string;
}

// ─── Mode definitions ──────────────────────────────────────────────────────────

const MODES: ModeConfig[] = [
    {
        id: 'auto',
        label: 'Auto',
        icon: <Cpu size={14} />,
        description: 'Intelligently detects the best pipeline for your message',
        color: 'from-violet-500 to-purple-600',
        badge: '🤖 Smart',
    },
    {
        id: 'fast',
        label: 'Fast',
        icon: <Zap size={14} />,
        description: 'Quick answers from your PDF — no extra processing',
        color: 'from-amber-400 to-orange-500',
        badge: '⚡ Quick',
    },
    {
        id: 'study',
        label: 'Study',
        icon: <BookOpen size={14} />,
        description: 'Exam prep: study guide, key topics, reading plan',
        color: 'from-emerald-400 to-teal-500',
        badge: '📚 Deep',
    },
    {
        id: 'research',
        label: 'Research',
        icon: <FlaskConical size={14} />,
        description: 'Full analysis: hybrid retrieval, citations, reflection',
        color: 'from-blue-500 to-indigo-600',
        badge: '🔬 Thorough',
    },
    {
        id: 'chat',
        label: 'Chat',
        icon: <MessageCircle size={14} />,
        description: 'Casual conversation — no document retrieval',
        color: 'from-pink-400 to-rose-500',
        badge: '💬 Casual',
    },
];

// ─── Loading indicator text per mode ──────────────────────────────────────────

const LOADING_TEXT: Record<PipelineMode, string> = {
    auto: 'Detecting best pipeline…',
    fast: 'Retrieving fast answer…',
    study: 'Building your study guide…',
    research: 'Deep research in progress…',
    chat: 'Thinking…',
};

// ─── Props ─────────────────────────────────────────────────────────────────────

interface ChatPageProps {
    sessionId: number | null;
    onSessionCreated: (session: ChatSession) => void;
}

// ─── Main Component ────────────────────────────────────────────────────────────

export default function ChatPage({ sessionId, onSessionCreated }: ChatPageProps) {
    const [messages, setMessages] = useState<Message[]>([
        {
            role: 'assistant',
            content: "Hi! I'm StudyAI — your intelligent study companion. 📚\n\nUpload a PDF and ask me anything, or just chat!\n\n**Modes available:**\n🤖 Auto · ⚡ Fast · 📚 Study · 🔬 Research · 💬 Chat",
            timestamp: new Date(),
        }
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [uploadedFile, setUploadedFile] = useState<File | null>(null);
    const [selectedMode, setSelectedMode] = useState<PipelineMode>('auto');
    const [showModeMenu, setShowModeMenu] = useState(false);
    const [currentSessionId, setCurrentSessionId] = useState<number | null>(sessionId);
    const [uploadedDocIds, setUploadedDocIds] = useState<string[]>([]);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const modeMenuRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // Load messages when session changes
    useEffect(() => {
        setCurrentSessionId(sessionId);
        setUploadedFile(null);  // Reset uploaded file banner when switching chats
        setUploadedDocIds([]);  // Reset doc list for new session
        if (sessionId) {
            getSessionMessages(sessionId)
                .then((msgs) => {
                    if (msgs.length > 0) {
                        setMessages(
                            msgs.map((m) => ({
                                role: m.role as 'user' | 'assistant',
                                content: m.content,
                                timestamp: new Date(m.created_at),
                                confidence: m.confidence ?? undefined,
                                citations: m.citations ?? undefined,
                                mode: (m.mode as PipelineMode) ?? undefined,
                            }))
                        );
                    } else {
                        // Empty session — show welcome
                        setMessages([{
                            role: 'assistant',
                            content: "Hi! I'm StudyAI — your intelligent study companion. 📚\n\nUpload a PDF and ask me anything, or just chat!",
                            timestamp: new Date(),
                        }]);
                    }
                })
                .catch(() => {
                    // Couldn't load — show fresh chat
                });
        } else {
            // No session selected — fresh chat
            setMessages([{
                role: 'assistant',
                content: "Hi! I'm StudyAI — your intelligent study companion. 📚\n\nUpload a PDF and ask me anything, or just chat!\n\n**Modes available:**\n🤖 Auto · ⚡ Fast · 📚 Study · 🔬 Research · 💬 Chat",
                timestamp: new Date(),
            }]);
        }
    }, [sessionId]);

    // Close mode dropdown when clicking outside
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (modeMenuRef.current && !modeMenuRef.current.contains(e.target as Node)) {
                setShowModeMenu(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    const currentMode = MODES.find(m => m.id === selectedMode)!;

    const handleSend = async () => {
        if (!input.trim() || loading) return;

        const userMessage: Message = {
            role: 'user',
            content: input,
            timestamp: new Date(),
            mode: selectedMode,
        };

        setMessages(prev => [...prev, userMessage]);
        const currentInput = input;
        setInput('');
        setLoading(true);

        try {
            // Auto-create a session if none exists
            let sid = currentSessionId;
            if (!sid) {
                try {
                    const title = currentInput.slice(0, 60) + (currentInput.length > 60 ? '…' : '');
                    const session = await createSession(title);
                    sid = session.id;
                    setCurrentSessionId(sid);
                    onSessionCreated(session);
                } catch (err) {
                    console.error('Could not create session', err);
                }
            }

            const response = await askQuestion({
                query: currentInput,
                conversation_history: messages.map(m => ({ role: m.role, content: m.content })),
                mode: selectedMode,
                session_id: sid ?? undefined,
                doc_ids: uploadedDocIds.length > 0 ? uploadedDocIds : undefined,
            });

            const aiMessage: Message = {
                role: 'assistant',
                content: response.answer,
                timestamp: new Date(),
                confidence: response.confidence,
                citations: response.citations,
                mode: (response.metadata as any)?.pipeline_mode || selectedMode,
            };

            setMessages(prev => [...prev, aiMessage]);
        } catch (error) {
            console.error('Backend error:', error);
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: '❌ Could not reach the backend. Make sure the server is running on http://localhost:8000',
                timestamp: new Date(),
                confidence: 0,
            }]);
        } finally {
            setLoading(false);
        }
    };

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setUploadedFile(file);

        setMessages(prev => [...prev, {
            role: 'assistant',
            content: `⏳ Uploading "${file.name}"…`,
            timestamp: new Date(),
        }]);

        try {
            // Auto-create session if none exists
            let sid = currentSessionId;
            if (!sid) {
                try {
                    const session = await createSession(file.name);
                    sid = session.id;
                    setCurrentSessionId(sid);
                    onSessionCreated(session);
                } catch (err) {
                    console.error('Could not create session for upload', err);
                }
            }

            const res = await uploadDocument(file, sid ?? undefined);
            // Track this doc_id so all queries in this session search it
            if (res.document_id) {
                setUploadedDocIds(prev => [...prev, res.document_id]);
            }
            setMessages(prev => [...prev.slice(0, -1), {
                role: 'assistant',
                content: `✅ **${file.name}** uploaded!\n\n📄 Pages: ${res.pages}\n📦 Chunks: ${res.chunks_created}\n⏱️ Time: ${(res.processing_time_ms / 1000).toFixed(1)}s\n\nAsk me anything — try **Study mode** for an exam plan! 🎓`,
                timestamp: new Date(),
            }]);
        } catch {
            setMessages(prev => [...prev.slice(0, -1), {
                role: 'assistant',
                content: `❌ Upload failed for "${file.name}". Is the server running?`,
                timestamp: new Date(),
            }]);
        }
    };

    return (
        <div className="h-[calc(100vh-4rem)] flex flex-col">

            {/* ── Upload Banner ─────────────────────────────────────────── */}
            {!uploadedFile && (
                <div className="bg-gradient-to-r from-primary-600 to-purple-600 p-4">
                    <div className="max-w-4xl mx-auto flex items-center justify-between text-white">
                        <div className="flex items-center space-x-3">
                            <Sparkles className="w-5 h-5" />
                            <p className="font-medium">Upload a PDF to unlock Study, Fast & Research modes</p>
                        </div>
                        <label className="btn bg-white text-primary-600 hover:bg-gray-100 cursor-pointer">
                            <input type="file" accept=".pdf" onChange={handleFileUpload} className="hidden" />
                            <Upload className="w-4 h-4 mr-2 inline" />
                            Upload PDF
                        </label>
                    </div>
                </div>
            )}

            {uploadedFile && (
                <div className="bg-green-50 dark:bg-green-900/20 border-b border-green-200 dark:border-green-800 p-3">
                    <div className="max-w-4xl mx-auto flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                            <FileText className="w-5 h-5 text-green-600" />
                            <span className="font-medium text-green-700 dark:text-green-400">{uploadedFile.name}</span>
                            <span className="text-xs text-green-600 dark:text-green-500">• Ready</span>
                        </div>
                        <label className="text-xs text-green-600 hover:text-green-800 cursor-pointer underline">
                            <input type="file" accept=".pdf" onChange={handleFileUpload} className="hidden" />
                            Change PDF
                        </label>
                    </div>
                </div>
            )}

            {/* ── Messages ──────────────────────────────────────────────── */}
            <div className="flex-1 overflow-y-auto p-6">
                <div className="max-w-4xl mx-auto space-y-6">
                    {messages.map((message, index) => (
                        <div
                            key={index}
                            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-slide-up`}
                        >
                            <div
                                className={`max-w-[80%] ${message.role === 'user'
                                    ? 'bg-primary-600 text-white rounded-2xl rounded-tr-sm'
                                    : 'bg-white dark:bg-dark-800 rounded-2xl rounded-tl-sm border border-gray-200 dark:border-dark-700'
                                    } p-4 shadow-lg`}
                            >
                                {message.role === 'assistant' && (
                                    <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center space-x-2 text-primary-600">
                                            <Sparkles className="w-4 h-4" />
                                            <span className="text-xs font-semibold">StudyAI</span>
                                        </div>
                                        {message.mode && message.mode !== 'auto' && (
                                            <ModeBadge mode={message.mode} />
                                        )}
                                    </div>
                                )}

                                <MarkdownRenderer content={message.content} />

                                {message.confidence != null && (
                                    <div className="mt-3 pt-3 border-t border-gray-200 dark:border-dark-700 flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                                        <span>Confidence: {(message.confidence * 100).toFixed(0)}%</span>
                                        {message.citations && message.citations.length > 0 && (
                                            <span>{message.citations.length} source{message.citations.length !== 1 ? 's' : ''}</span>
                                        )}
                                        <span>{message.timestamp.toLocaleTimeString()}</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}

                    {loading && (
                        <div className="flex justify-start animate-slide-up">
                            <div className="bg-white dark:bg-dark-800 rounded-2xl rounded-tl-sm border border-gray-200 dark:border-dark-700 p-4 shadow-lg">
                                <div className="flex items-center space-x-3">
                                    <Loader2 className="w-5 h-5 animate-spin text-primary-600" />
                                    <span className="text-sm text-gray-600 dark:text-gray-400">
                                        {LOADING_TEXT[selectedMode]}
                                    </span>
                                </div>
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* ── Input Area ────────────────────────────────────────────── */}
            <div className="border-t border-gray-200 dark:border-dark-700 bg-white dark:bg-dark-800 p-4">
                <div className="max-w-4xl mx-auto space-y-3">

                    {/* Mode Selector Row */}
                    <div className="flex items-center space-x-2 overflow-x-auto pb-1 scrollbar-hide">
                        {MODES.map(mode => (
                            <button
                                key={mode.id}
                                onClick={() => setSelectedMode(mode.id)}
                                title={mode.description}
                                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-all
                                    ${selectedMode === mode.id
                                        ? `bg-gradient-to-r ${mode.color} text-white shadow-md scale-105`
                                        : 'bg-gray-100 dark:bg-dark-700 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-dark-600'
                                    }`}
                            >
                                {mode.icon}
                                <span>{mode.label}</span>
                            </button>
                        ))}
                    </div>

                    {/* Active mode description */}
                    <p className="text-xs text-gray-400 dark:text-gray-500 pl-1">
                        {currentMode.badge} · {currentMode.description}
                    </p>

                    {/* Input Row */}
                    <div className="flex items-center space-x-3">
                        <label className="btn btn-secondary cursor-pointer flex-shrink-0">
                            <Upload className="w-5 h-5" />
                            <input type="file" accept=".pdf" onChange={handleFileUpload} className="hidden" />
                        </label>

                        <div className="flex-1 relative">
                            <input
                                type="text"
                                value={input}
                                onChange={e => setInput(e.target.value)}
                                onKeyPress={e => e.key === 'Enter' && handleSend()}
                                placeholder={getPlaceholder(selectedMode)}
                                className="input pr-12"
                                disabled={loading}
                            />
                            <button
                                onClick={handleSend}
                                disabled={!input.trim() || loading}
                                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95"
                            >
                                <Send className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

// ─── Helper Components ─────────────────────────────────────────────────────────

function ModeBadge({ mode }: { mode: PipelineMode }) {
    const cfg = MODES.find(m => m.id === mode);
    if (!cfg) return null;
    return (
        <span className={`text-xs px-2 py-0.5 rounded-full bg-gradient-to-r ${cfg.color} text-white font-medium`}>
            {cfg.label}
        </span>
    );
}

function getPlaceholder(mode: PipelineMode): string {
    switch (mode) {
        case 'auto': return 'Ask anything — I\'ll pick the right mode…';
        case 'fast': return 'Quick question about your PDF…';
        case 'study': return 'Help me study this PDF for the exam…';
        case 'research': return 'Deeply explain this concept with citations…';
        case 'chat': return 'Just chatting…';
    }
}
