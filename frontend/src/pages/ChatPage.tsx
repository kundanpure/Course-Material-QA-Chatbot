import React, { useState, useRef, useEffect } from 'react';
import {
    Send,
    Upload,
    Sparkles,
    FileText,
    Loader2,
    Check,
    AlertCircle,
    Clock,
    MessageSquare
} from 'lucide-react';

interface Message {
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    confidence?: number;
    citations?: any[];
}

export default function ChatPage() {
    const [messages, setMessages] = useState<Message[]>([
        {
            role: 'assistant',
            content: "Hi! I'm your AI study companion. Upload a document and ask me anything! 📚✨",
            timestamp: new Date()
        }
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [document, setDocument] = useState<File | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim() || loading) return;

        const userMessage: Message = {
            role: 'user',
            content: input,
            timestamp: new Date()
        };

        setMessages(prev => [...prev, userMessage]);
        const currentInput = input;
        setInput('');
        setLoading(true);

        try {
            // Call the real backend API
            const { askQuestion } = await import('../services/api');

            const response = await askQuestion({
                query: currentInput,
                conversation_history: messages.map(m => ({
                    role: m.role,
                    content: m.content
                }))
            });

            const aiMessage: Message = {
                role: 'assistant',
                content: response.answer,
                timestamp: new Date(),
                confidence: response.confidence,
                citations: response.citations
            };

            setMessages(prev => [...prev, aiMessage]);
        } catch (error) {
            console.error('Failed to get response from backend:', error);

            const errorMessage: Message = {
                role: 'assistant',
                content: '❌ Sorry, I encountered an error connecting to the backend. Please make sure the server is running on http://localhost:8000',
                timestamp: new Date(),
                confidence: 0
            };

            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setLoading(false);
        }
    };

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            setDocument(file);

            // Show uploading message
            const uploadingMessage: Message = {
                role: 'assistant',
                content: `⏳ Uploading "${file.name}"... Please wait.`,
                timestamp: new Date()
            };
            setMessages(prev => [...prev, uploadingMessage]);

            try {
                // Call backend upload API
                const { uploadDocument } = await import('../services/api');
                const response = await uploadDocument(file);

                const successMessage: Message = {
                    role: 'assistant',
                    content: `✅ Successfully uploaded "${file.name}"!\n\n📄 Pages: ${response.pages}\n📦 Chunks created: ${response.chunks_created}\n⏱️ Processing time: ${(response.processing_time_ms / 1000).toFixed(2)}s\n\nYou can now ask me anything about this document!`,
                    timestamp: new Date()
                };

                // Replace the "uploading" message with success message
                setMessages(prev => [...prev.slice(0, -1), successMessage]);
            } catch (error) {
                console.error('Failed to upload document:', error);

                const errorMessage: Message = {
                    role: 'assistant',
                    content: `❌ Failed to upload "${file.name}". Please make sure the backend server is running.`,
                    timestamp: new Date()
                };

                // Replace the "uploading" message with error message
                setMessages(prev => [...prev.slice(0, -1), errorMessage]);
            }
        }
    };

    return (
        <div className="h-[calc(100vh-4rem)] flex flex-col">
            {/* Document Upload Bar */}
            {!document && (
                <div className="bg-gradient-to-r from-primary-600 to-purple-600 p-4">
                    <div className="max-w-4xl mx-auto flex items-center justify-between text-white">
                        <div className="flex items-center space-x-3">
                            <Sparkles className="w-5 h-5" />
                            <p className="font-medium">Upload a PDF to get started with contextual chat</p>
                        </div>
                        <label className="btn bg-white text-primary-600 hover:bg-gray-100 cursor-pointer">
                            <input
                                type="file"
                                accept=".pdf"
                                onChange={handleFileUpload}
                                className="hidden"
                            />
                            <Upload className="w-4 h-4 mr-2 inline" />
                            Upload PDF
                        </label>
                    </div>
                </div>
            )}

            {document && (
                <div className="bg-green-50 dark:bg-green-900/20 border-b border-green-200 dark:border-green-800 p-3">
                    <div className="max-w-4xl mx-auto flex items-center space-x-3">
                        <FileText className="w-5 h-5 text-green-600" />
                        <span className="font-medium text-green-700 dark:text-green-400">
                            {document.name}
                        </span>
                        <span className="text-xs text-green-600 dark:text-green-500">
                            • Active conversation
                        </span>
                    </div>
                </div>
            )}

            {/* Messages Area */}
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
                                    <div className="flex items-center space-x-2 mb-2 text-primary-600">
                                        <Sparkles className="w-4 h-4" />
                                        <span className="text-xs font-semibold">AI Assistant</span>
                                    </div>
                                )}

                                <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>

                                {message.confidence && (
                                    <div className="mt-3 pt-3 border-t border-gray-200 dark:border-dark-700 flex items-center justify-between text-xs">
                                        <span className="text-gray-500 dark:text-gray-400">
                                            Confidence: {(message.confidence * 100).toFixed(0)}%
                                        </span>
                                        <span className="text-gray-400 dark:text-gray-500">
                                            {message.timestamp.toLocaleTimeString()}
                                        </span>
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
                                    <span className="text-sm text-gray-600 dark:text-gray-400">Thinking...</span>
                                </div>
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* Input Area */}
            <div className="border-t border-gray-200 dark:border-dark-700 bg-white dark:bg-dark-800 p-4">
                <div className="max-w-4xl mx-auto">
                    <div className="flex items-center space-x-3">
                        <label className="btn btn-secondary cursor-pointer">
                            <Upload className="w-5 h-5" />
                            <input
                                type="file"
                                accept=".pdf"
                                onChange={handleFileUpload}
                                className="hidden"
                            />
                        </label>

                        <div className="flex-1 relative">
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                                placeholder="Ask anything about your course materials..."
                                className="input pr-12"
                                disabled={loading}
                            />
                            <button
                                onClick={handleSend}
                                disabled={!input.trim() || loading}
                                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95"
                            >
                                <Send className="w-5 h-5" />
                            </button>
                        </div>
                    </div>

                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 text-center">
                        💡 I remember our entire conversation! Ask follow-up questions anytime.
                    </p>
                </div>
            </div>
        </div>
    );
}
