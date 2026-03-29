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
import ReplyPreview from '../components/ReplyPreview';

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    confidence?: number;
    citations?: any[];
    mode?: PipelineMode;
    reply_to?: string | null;
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

const LOADING_TEXT: Record<PipelineMode, string> = {
    auto: 'Detecting best pipeline…',
    fast: 'Retrieving fast answer…',
    study: 'Building your study guide…',
    research: 'Deep research in progress…',
    chat: 'Thinking…',
};

interface ChatPageProps {
    sessionId: number | null;
    onSessionCreated: (session: ChatSession) => void;
}

export default function ChatPage({ sessionId, onSessionCreated }: ChatPageProps) {

    const [messages, setMessages] = useState<Message[]>([
        {
            id: Date.now().toString(),
            role: 'assistant',
            content: "Hi! I'm StudyAI — your intelligent study companion. 📚\n\nUpload a PDF and ask me anything, or just chat!\n\n**Modes available:**\n🤖 Auto · ⚡ Fast · 📚 Study · 🔬 Research · 💬 Chat",
            timestamp: new Date(),
        }
    ]);

    const [replyTo, setReplyTo] = useState<Message | null>(null);
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

    const currentMode = MODES.find(m => m.id === selectedMode)!;

    const handleSend = async () => {

        if (!input.trim() || loading) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: input,
            timestamp: new Date(),
            mode: selectedMode,
            reply_to: replyTo ? replyTo.id : null
        };

        setMessages(prev => [...prev, userMessage]);

        const currentInput = input;
        setInput('');
        setReplyTo(null);
        setLoading(true);

        try {

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
                id: (Date.now() + 1).toString(),
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
                id: (Date.now() + 2).toString(),
                role: 'assistant',
                content: '❌ Could not reach the backend. Make sure the server is running on http://localhost:8000',
                timestamp: new Date(),
                confidence: 0,
            }]);

        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="h-[calc(100vh-4rem)] flex flex-col">

            {/* Messages */}

            <div className="flex-1 overflow-y-auto p-6">
                <div className="max-w-4xl mx-auto space-y-6">

                    {messages.map((message, index) => (

                        <div
                            key={index}
                            id={`msg-${message.id}`}
                            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-slide-up`}
                        >

                            <div
                                className={`max-w-[80%] ${message.role === 'user'
                                    ? 'bg-primary-600 text-white rounded-2xl rounded-tr-sm'
                                    : 'bg-white dark:bg-dark-800 rounded-2xl rounded-tl-sm border border-gray-200 dark:border-dark-700'
                                    } p-4 shadow-lg`}
                            >

                                {message.reply_to && (
                                    <div
                                        className="bg-gray-200 text-xs p-2 border-l-4 border-blue-400 mb-2 cursor-pointer rounded"
                                        onClick={() => {
                                            const el = document.getElementById(`msg-${message.reply_to}`);
                                            if (el) el.scrollIntoView({ behavior: 'smooth' });
                                        }}
                                    >
                                        {messages.find(m => m.id === message.reply_to)?.content}
                                    </div>
                                )}

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

                                <div className="mt-2 text-right">
                                    <button
                                        onClick={() => setReplyTo(message)}
                                        className="text-xs text-blue-500 hover:underline"
                                    >
                                        Reply
                                    </button>
                                </div>

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

            {/* Input */}

            <div className="border-t border-gray-200 dark:border-dark-700 bg-white dark:bg-dark-800 p-4">

                <div className="max-w-4xl mx-auto space-y-3">

                    <ReplyPreview
                        replyTo={replyTo}
                        onCancel={() => setReplyTo(null)}
                    />

                    <div className="flex items-center space-x-3">

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