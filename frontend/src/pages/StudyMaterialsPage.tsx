import React from 'react';
import {
    FileText,
    Download,
    Sparkles,
    BookOpen,
    ClipboardList,
    Network,
    Zap
} from 'lucide-react';

export default function StudyMaterialsPage() {
    const flashcards = [
        { question: 'What is supervised learning?', answer: 'Machine learning with labeled data...', confidence: 0.92 },
        { question: 'Explain gradient descent', answer: 'An optimization algorithm...', confidence: 0.88 },
        { question: 'What are neural networks?', answer: 'Computing systems inspired by...', confidence: 0.75 }
    ];

    return (
        <div className="min-h-screen p-6">
            <div className="max-w-7xl mx-auto space-y-6">
                {/* Header */}
                <div className="animate-slide-up">
                    <h1 className="text-3xl font-bold gradient-text mb-2">Study Materials</h1>
                    <p className="text-gray-600 dark:text-gray-400">
                        Auto-generated from your conversations
                    </p>
                </div>

                {/* Action Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <ActionCard
                        icon={<FileText />}
                        title="Flashcards"
                        count={15}
                        description="Ready to export"
                        color="blue"
                        action="Export to Anki"
                    />
                    <ActionCard
                        icon={<ClipboardList />}
                        title="Practice Tests"
                        count={3}
                        description="Auto-generated"
                        color="green"
                        action="Take Test"
                    />
                    <ActionCard
                        icon={<Network />}
                        title="Concept Maps"
                        count={5}
                        description="Visual learning"
                        color="purple"
                        action="View Maps"
                    />
                    <ActionCard
                        icon={<BookOpen />}
                        title="Summaries"
                        count={8}
                        description="Quick reviews"
                        color="orange"
                        action="Read Now"
                    />
                </div>

                {/* Flashcards Preview */}
                <div className="card animate-slide-up">
                    <div className="flex items-center justify-between mb-6">
                        <div>
                            <h2 className="text-xl font-bold">Recent Flashcards</h2>
                            <p className="text-sm text-gray-500 dark:text-gray-400">
                                Auto-created from your Q&A sessions
                            </p>
                        </div>
                        <div className="flex space-x-2">
                            <button className="btn btn-secondary">
                                <Download className="w-4 h-4 mr-2" />
                                Export PDF
                            </button>
                            <button className="btn btn-primary">
                                <Sparkles className="w-4 h-4 mr-2" />
                                Export to Anki
                            </button>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {flashcards.map((card, index) => (
                            <div
                                key={index}
                                className="group perspective-1000 h-48 cursor-pointer"
                            >
                                <div className="relative preserve-3d transition-transform duration-500 hover:rotate-y-180 h-full">
                                    {/* Front */}
                                    <div className="absolute inset-0 backface-hidden bg-gradient-to-br from-primary-50 to-purple-50 dark:from-primary-900/20 dark:to-purple-900/20 border-2 border-primary-200 dark:border-primary-800 rounded-xl p-6 flex flex-col justify-between">
                                        <div>
                                            <div className="flex items-center justify-between mb-3">
                                                <span className="text-xs font-semibold text-primary-600 dark:text-primary-400">
                                                    QUESTION
                                                </span>
                                                <Sparkles className="w-4 h-4 text-primary-600" />
                                            </div>
                                            <p className="text-sm font-medium leading-relaxed">
                                                {card.question}
                                            </p>
                                        </div>
                                        <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
                                            Hover to see answer
                                        </p>
                                    </div>

                                    {/* Back */}
                                    <div className="absolute inset-0 backface-hidden rotate-y-180 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border-2 border-green-200 dark:border-green-800 rounded-xl p-6 flex flex-col justify-between">
                                        <div>
                                            <div className="flex items-center justify-between mb-3">
                                                <span className="text-xs font-semibold text-green-600 dark:text-green-400">
                                                    ANSWER
                                                </span>
                                                <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400">
                                                    {(card.confidence * 100).toFixed(0)}% confidence
                                                </span>
                                            </div>
                                            <p className="text-sm leading-relaxed">
                                                {card.answer}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Generate More Section */}
                <div className="card bg-gradient-to-br from-primary-600 to-purple-600 text-white animate-slide-up">
                    <div className="flex items-center justify-between">
                        <div>
                            <h3 className="text-2xl font-bold mb-2">Want more study materials?</h3>
                            <p className="text-primary-100">
                                Just keep chatting! I'll automatically create flashcards, practice questions, and summaries.
                            </p>
                        </div>
                        <button className="btn bg-white text-primary-600 hover:bg-gray-100">
                            <Zap className="w-5 h-5 mr-2" />
                            Go to Chat
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

function ActionCard({ icon, title, count, description, color, action }: any) {
    const colors = {
        blue: 'from-blue-500 to-blue-600',
        green: 'from-green-500 to-green-600',
        purple: 'from-purple-500 to-purple-600',
        orange: 'from-orange-500 to-orange-600'
    };

    return (
        <div className="card hover:shadow-xl transition-all duration-300 group animate-slide-up">
            <div className={`p-3 bg-gradient-to-br ${colors[color as keyof typeof colors]} rounded-lg text-white w-fit mb-4`}>
                {icon}
            </div>

            <h3 className="font-bold text-lg mb-1">{title}</h3>
            <div className="flex items-baseline space-x-2 mb-2">
                <span className="text-3xl font-bold gradient-text">{count}</span>
                <span className="text-sm text-gray-500 dark:text-gray-400">{description}</span>
            </div>

            <button className="btn btn-secondary w-full mt-3 group-hover:btn-primary transition-all">
                {action}
            </button>
        </div>
    );
}
