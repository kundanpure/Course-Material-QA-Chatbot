import { useState, useEffect } from 'react';
import {
    BookOpen,
    Sparkles,
    Brain,
    Network,
    Link2,
    HelpCircle,
    Loader2,
    RefreshCw,
    AlertCircle,
    Search,
    ChevronDown,
    ChevronRight,
    Check,
    X,
    FileText,
    Zap,
    GraduationCap,
    Youtube,
    Globe,
    BookMarked,
    Play,
    ArrowRight,
    Clock,
    Star,
} from 'lucide-react';
import {
    getTopicSuggestions,
    generateStudyMaterial,
    getUploadedDocuments,
    type TopicSuggestion,
    type StudyMaterialResult,
    type StudyTool,
    type FlashcardItem,
    type QuizQuestion,
    type ConceptNode,
    type ConceptMap,
    type ResourceItem,
} from '../services/api';
import MarkdownRenderer from '../components/MarkdownRenderer';

// ─── Tool Definitions ─────────────────────────────────────────────────────────

interface ToolDef {
    id: StudyTool;
    label: string;
    icon: React.ReactNode;
    color: string;
    description: string;
}

const TOOLS: ToolDef[] = [
    { id: 'guide', label: 'Study Guide', icon: <BookOpen size={18} />, color: 'from-blue-500 to-blue-600', description: 'Key concepts, formulas & learning path' },
    { id: 'flashcards', label: 'Flashcards', icon: <Sparkles size={18} />, color: 'from-purple-500 to-purple-600', description: 'Interactive Q&A cards for memorization' },
    { id: 'quiz', label: 'Practice Quiz', icon: <HelpCircle size={18} />, color: 'from-green-500 to-green-600', description: 'MCQs & short answers with scoring' },
    { id: 'concepts', label: 'Concept Map', icon: <Network size={18} />, color: 'from-orange-500 to-orange-600', description: 'Visual topic hierarchy & relationships' },
    { id: 'resources', label: 'Resources', icon: <Link2 size={18} />, color: 'from-pink-500 to-rose-600', description: 'Videos, courses, books & links' },
];

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function Skeleton({ className = '' }: { className?: string }) {
    return (
        <div className={`animate-pulse bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200 dark:from-dark-700 dark:via-dark-600 dark:to-dark-700 rounded-lg ${className}`} />
    );
}

// ─── Topic Pill ───────────────────────────────────────────────────────────────

function TopicPill({ topic, onClick, active }: { topic: TopicSuggestion; onClick: () => void; active: boolean }) {
    const sourceColor: Record<string, string> = {
        your_queries: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
        your_documents: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
        your_chats: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400',
        frequent_keywords: 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400',
        popular: 'bg-gray-100 dark:bg-dark-700 text-gray-600 dark:text-gray-400',
    };

    return (
        <button
            onClick={onClick}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all hover:scale-105 ${active
                ? 'bg-gradient-to-r from-primary-600 to-purple-600 text-white shadow-lg shadow-primary-600/30'
                : sourceColor[topic.source] || sourceColor.popular
                }`}
        >
            {topic.name}
            {topic.count > 0 && (
                <span className="ml-1 opacity-70 text-xs">({topic.count})</span>
            )}
        </button>
    );
}

// ─── Flashcard Component ──────────────────────────────────────────────────────

function FlashcardView({ cards }: { cards: FlashcardItem[] }) {
    const [flippedSet, setFlippedSet] = useState<Set<number>>(new Set());

    const toggleFlip = (i: number) => {
        setFlippedSet(prev => {
            const next = new Set(prev);
            if (next.has(i)) next.delete(i);
            else next.add(i);
            return next;
        });
    };

    const diffColors: Record<string, string> = {
        easy: 'text-green-600 bg-green-100 dark:bg-green-900/30 dark:text-green-400',
        medium: 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30 dark:text-yellow-400',
        hard: 'text-red-600 bg-red-100 dark:bg-red-900/30 dark:text-red-400',
    };

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {cards.map((card, i) => (
                <div
                    key={i}
                    className="perspective-1000 h-56 cursor-pointer animate-slide-up"
                    style={{ animationDelay: `${i * 60}ms` }}
                    onClick={() => toggleFlip(i)}
                >
                    <div className={`relative preserve-3d transition-transform duration-500 h-full ${flippedSet.has(i) ? 'rotate-y-180' : ''}`}>
                        {/* Front */}
                        <div className="absolute inset-0 backface-hidden bg-gradient-to-br from-primary-50 to-purple-50 dark:from-primary-900/20 dark:to-purple-900/20 border-2 border-primary-200 dark:border-primary-800 rounded-xl p-5 flex flex-col justify-between">
                            <div>
                                <div className="flex items-center justify-between mb-3">
                                    <span className="text-xs font-semibold text-primary-600 dark:text-primary-400 uppercase tracking-wide">Question</span>
                                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${diffColors[card.difficulty] || ''}`}>
                                        {card.difficulty}
                                    </span>
                                </div>
                                <p className="text-sm font-medium leading-relaxed line-clamp-5">{card.question}</p>
                            </div>
                            <p className="text-xs text-gray-400 dark:text-gray-500 text-center">Click to reveal answer</p>
                        </div>
                        {/* Back */}
                        <div className="absolute inset-0 backface-hidden rotate-y-180 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border-2 border-green-200 dark:border-green-800 rounded-xl p-5 flex flex-col justify-center overflow-y-auto">
                            <div className="flex items-center justify-between mb-3">
                                <span className="text-xs font-semibold text-green-600 dark:text-green-400 uppercase tracking-wide">Answer</span>
                            </div>
                            <p className="text-sm leading-relaxed">{card.answer}</p>
                        </div>
                    </div>
                </div>
            ))}
        </div>
    );
}

// ─── Quiz Component ───────────────────────────────────────────────────────────

function QuizView({ questions }: { questions: QuizQuestion[] }) {
    const [answers, setAnswers] = useState<Record<number, string>>({});
    const [submitted, setSubmitted] = useState(false);

    const handleSelect = (qId: number, value: string) => {
        if (submitted) return;
        setAnswers(prev => ({ ...prev, [qId]: value }));
    };

    const handleSubmit = () => setSubmitted(true);
    const handleReset = () => { setAnswers({}); setSubmitted(false); };

    const score = submitted
        ? questions.filter(q => {
            const userAns = answers[q.id] || '';
            if (q.type === 'mcq') return userAns === q.correct_answer;
            return userAns.toLowerCase().trim().includes(q.correct_answer.toLowerCase().trim().slice(0, 20));
        }).length
        : 0;

    return (
        <div className="space-y-6">
            {submitted && (
                <div className={`card p-5 text-center border-0 ${score >= questions.length * 0.7
                    ? 'bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20'
                    : 'bg-gradient-to-r from-orange-50 to-amber-50 dark:from-orange-900/20 dark:to-amber-900/20'
                    }`}>
                    <GraduationCap className="w-10 h-10 mx-auto mb-2 text-primary-600" />
                    <p className="text-2xl font-bold">{score} / {questions.length}</p>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        {score >= questions.length * 0.7 ? 'Great job! 🎉' : 'Keep practicing! 💪'}
                    </p>
                    <button onClick={handleReset} className="btn btn-secondary mt-3">
                        <RefreshCw className="w-4 h-4 mr-2" /> Retry
                    </button>
                </div>
            )}

            {questions.map((q, idx) => {
                const userAns = answers[q.id] || '';
                const isCorrect = submitted && (
                    q.type === 'mcq'
                        ? userAns === q.correct_answer
                        : userAns.toLowerCase().trim().includes(q.correct_answer.toLowerCase().trim().slice(0, 20))
                );

                return (
                    <div
                        key={q.id}
                        className={`card animate-slide-up ${submitted ? (isCorrect ? 'border-green-300 dark:border-green-700' : 'border-red-300 dark:border-red-700') : ''}`}
                        style={{ animationDelay: `${idx * 60}ms` }}
                    >
                        <div className="flex items-start space-x-3 mb-4">
                            <span className="flex-shrink-0 w-7 h-7 rounded-full bg-primary-100 dark:bg-primary-900/30 text-primary-600 flex items-center justify-center text-sm font-bold">
                                {q.id}
                            </span>
                            <div className="flex-1">
                                <div className="flex items-center space-x-2 mb-1">
                                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${q.difficulty === 'easy' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                                        q.difficulty === 'medium' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' :
                                            'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'}`}>
                                        {q.difficulty}
                                    </span>
                                    <span className="text-xs text-gray-400">{q.type === 'mcq' ? 'Multiple Choice' : 'Short Answer'}</span>
                                </div>
                                <p className="font-medium">{q.question}</p>
                            </div>
                        </div>

                        {q.type === 'mcq' && q.options ? (
                            <div className="space-y-2 ml-10">
                                {q.options.map((opt, oi) => {
                                    const letter = String.fromCharCode(65 + oi); // A, B, C, D
                                    const isSelected = userAns === letter;
                                    const isRight = submitted && letter === q.correct_answer;
                                    const isWrong = submitted && isSelected && letter !== q.correct_answer;

                                    return (
                                        <button
                                            key={oi}
                                            onClick={() => handleSelect(q.id, letter)}
                                            className={`w-full text-left p-3 rounded-lg border transition-all text-sm ${isRight ? 'border-green-500 bg-green-50 dark:bg-green-900/20' :
                                                isWrong ? 'border-red-500 bg-red-50 dark:bg-red-900/20' :
                                                    isSelected ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20' :
                                                        'border-gray-200 dark:border-dark-600 hover:border-primary-300 dark:hover:border-primary-700'
                                                }`}
                                        >
                                            <div className="flex items-center space-x-2">
                                                {isRight && <Check className="w-4 h-4 text-green-600 flex-shrink-0" />}
                                                {isWrong && <X className="w-4 h-4 text-red-600 flex-shrink-0" />}
                                                {!submitted && isSelected && <div className="w-3 h-3 rounded-full bg-primary-600 flex-shrink-0" />}
                                                {!submitted && !isSelected && <div className="w-3 h-3 rounded-full border-2 border-gray-300 dark:border-dark-500 flex-shrink-0" />}
                                                <span>{opt}</span>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        ) : (
                            <div className="ml-10">
                                <input
                                    type="text"
                                    value={userAns}
                                    onChange={e => handleSelect(q.id, e.target.value)}
                                    placeholder="Type your answer…"
                                    className="input text-sm"
                                    disabled={submitted}
                                />
                            </div>
                        )}

                        {submitted && (
                            <div className={`mt-3 ml-10 p-3 rounded-lg text-sm ${isCorrect ? 'bg-green-50 dark:bg-green-900/10 text-green-700 dark:text-green-400' : 'bg-orange-50 dark:bg-orange-900/10 text-orange-700 dark:text-orange-400'}`}>
                                <p className="font-medium mb-1">{isCorrect ? '✅ Correct!' : `❌ Correct answer: ${q.correct_answer}`}</p>
                                <p className="opacity-80">{q.explanation}</p>
                            </div>
                        )}
                    </div>
                );
            })}

            {!submitted && questions.length > 0 && (
                <button onClick={handleSubmit} className="btn btn-primary w-full py-3">
                    <Check className="w-5 h-5 mr-2" /> Submit Quiz
                </button>
            )}
        </div>
    );
}

// ─── Concept Map Component ────────────────────────────────────────────────────

function ConceptMapView({ data }: { data: ConceptMap }) {
    return (
        <div className="card space-y-4 animate-slide-up">
            <div className="text-center mb-6">
                <div className="inline-flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-primary-600 to-purple-600 text-white rounded-full font-bold text-lg">
                    <Brain className="w-5 h-5" />
                    <span>{data.root}</span>
                </div>
            </div>
            <div className="space-y-3">
                {data.children.map((child, i) => (
                    <ConceptBranch key={i} node={child} depth={0} index={i} />
                ))}
            </div>
        </div>
    );
}

function ConceptBranch({ node, depth, index }: { node: ConceptNode; depth: number; index: number }) {
    const [expanded, setExpanded] = useState(depth < 1);
    const hasChildren = node.children && node.children.length > 0;

    const depthColors = [
        'border-l-blue-500 bg-blue-50/50 dark:bg-blue-900/10',
        'border-l-purple-500 bg-purple-50/50 dark:bg-purple-900/10',
        'border-l-green-500 bg-green-50/50 dark:bg-green-900/10',
    ];

    return (
        <div className="animate-slide-up" style={{ animationDelay: `${index * 80}ms`, marginLeft: `${depth * 20}px` }}>
            <button
                onClick={() => setExpanded(!expanded)}
                className={`w-full text-left p-3 rounded-lg border-l-4 transition-all hover:shadow-md ${depthColors[depth % depthColors.length]}`}
            >
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                        {hasChildren && (
                            expanded
                                ? <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0" />
                                : <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        )}
                        {!hasChildren && <div className="w-4 h-4 flex-shrink-0 flex items-center justify-center"><div className="w-2 h-2 rounded-full bg-gray-300 dark:bg-gray-600" /></div>}
                        <span className="font-semibold text-sm">{node.name}</span>
                    </div>
                </div>
                {node.description && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-6">{node.description}</p>
                )}
            </button>
            {expanded && hasChildren && (
                <div className="mt-2 space-y-2">
                    {node.children.map((child, ci) => (
                        <ConceptBranch key={ci} node={child} depth={depth + 1} index={ci} />
                    ))}
                </div>
            )}
        </div>
    );
}

// ─── Resources View ───────────────────────────────────────────────────────────

function ResourcesView({ resources }: { resources: ResourceItem[] }) {
    const typeIcons: Record<string, React.ReactNode> = {
        video: <Youtube className="w-5 h-5" />,
        course: <GraduationCap className="w-5 h-5" />,
        documentation: <Globe className="w-5 h-5" />,
        book: <BookMarked className="w-5 h-5" />,
        interactive: <Play className="w-5 h-5" />,
    };

    const typeColors: Record<string, string> = {
        video: 'from-red-500 to-red-600',
        course: 'from-blue-500 to-blue-600',
        documentation: 'from-green-500 to-green-600',
        book: 'from-purple-500 to-purple-600',
        interactive: 'from-orange-500 to-orange-600',
    };

    const levelBadge: Record<string, string> = {
        beginner: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
        intermediate: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
        advanced: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    };

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {resources.map((res, i) => (
                <a
                    key={i}
                    href={res.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="card hover:shadow-xl transition-all group animate-slide-up border-0 bg-white dark:bg-dark-800"
                    style={{ animationDelay: `${i * 60}ms` }}
                >
                    <div className="flex items-start space-x-4">
                        <div className={`p-3 bg-gradient-to-br ${typeColors[res.type] || typeColors.documentation} rounded-xl text-white flex-shrink-0 group-hover:scale-110 transition-transform`}>
                            {typeIcons[res.type] || <Globe className="w-5 h-5" />}
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center space-x-2 mb-1">
                                <h3 className="font-bold text-sm truncate group-hover:text-primary-600 transition-colors">{res.title}</h3>
                                <ArrowRight className="w-4 h-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                            </div>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mb-2 line-clamp-2">{res.description}</p>
                            <div className="flex items-center space-x-2">
                                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${levelBadge[res.level] || ''}`}>
                                    {res.level}
                                </span>
                                <span className="text-xs text-gray-400 capitalize">{res.type}</span>
                            </div>
                        </div>
                    </div>
                </a>
            ))}
        </div>
    );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function StudyMaterialsPage() {
    const [topic, setTopic] = useState('');
    const [selectedTool, setSelectedTool] = useState<StudyTool>('guide');
    const [suggestions, setSuggestions] = useState<TopicSuggestion[]>([]);
    const [documents, setDocuments] = useState<any[]>([]);
    const [selectedDoc, setSelectedDoc] = useState<string>('');
    const [result, setResult] = useState<StudyMaterialResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [loadingSuggestions, setLoadingSuggestions] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Load suggestions + documents on mount
    useEffect(() => {
        (async () => {
            try {
                const [topics, docs] = await Promise.all([
                    getTopicSuggestions(),
                    getUploadedDocuments().catch(() => []),
                ]);
                setSuggestions(topics);
                setDocuments(docs);
            } catch (err) {
                console.error('Failed to load suggestions:', err);
            } finally {
                setLoadingSuggestions(false);
            }
        })();
    }, []);

    const handleGenerate = async () => {
        if (!topic.trim()) return;
        setLoading(true);
        setError(null);
        setResult(null);

        try {
            const data = await generateStudyMaterial(topic.trim(), selectedTool, selectedDoc || undefined);
            setResult(data);
        } catch (err: any) {
            console.error('Generation failed:', err);
            setError(err?.response?.data?.detail || 'Generation failed. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const handleTopicClick = (name: string) => {
        setTopic(name);
        setResult(null);
    };

    const currentTool = TOOLS.find(t => t.id === selectedTool)!;

    return (
        <div className="min-h-screen p-6">
            <div className="max-w-6xl mx-auto space-y-6">
                {/* Header */}
                <div className="animate-slide-up">
                    <h1 className="text-3xl font-bold gradient-text mb-2">Study Materials</h1>
                    <p className="text-gray-600 dark:text-gray-400">
                        Enter any topic and generate comprehensive study materials with AI
                    </p>
                </div>

                {/* Topic Input Section */}
                <div className="card animate-slide-up" style={{ animationDelay: '100ms' }}>
                    <div className="space-y-4">
                        {/* Input row */}
                        <div className="flex items-center space-x-3">
                            <div className="flex-1 relative">
                                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                                <input
                                    type="text"
                                    value={topic}
                                    onChange={e => { setTopic(e.target.value); setResult(null); }}
                                    onKeyDown={e => e.key === 'Enter' && handleGenerate()}
                                    placeholder="What do you want to study? e.g. Machine Learning, Data Structures…"
                                    className="input pl-12 pr-4 py-3 text-base"
                                />
                            </div>
                            <button
                                onClick={handleGenerate}
                                disabled={!topic.trim() || loading}
                                className="btn btn-primary py-3 px-6 whitespace-nowrap"
                            >
                                {loading ? (
                                    <><Loader2 className="w-5 h-5 mr-2 animate-spin" /> Generating…</>
                                ) : (
                                    <><Zap className="w-5 h-5 mr-2" /> Generate</>
                                )}
                            </button>
                        </div>

                        {/* Optional PDF context */}
                        {documents.length > 0 && (
                            <div className="flex items-center space-x-2 text-sm">
                                <FileText className="w-4 h-4 text-gray-400" />
                                <span className="text-gray-500 dark:text-gray-400">Enhance with PDF:</span>
                                <select
                                    value={selectedDoc}
                                    onChange={e => setSelectedDoc(e.target.value)}
                                    className="text-sm bg-gray-100 dark:bg-dark-700 border-0 rounded-lg px-3 py-1.5 text-gray-700 dark:text-gray-300 outline-none"
                                >
                                    <option value="">None (use AI knowledge only)</option>
                                    {documents.map((doc: any) => (
                                        <option key={doc.doc_id} value={doc.doc_id}>
                                            {doc.filename} ({doc.page_count}p)
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}

                        {/* Dynamic topic suggestions */}
                        <div>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mb-2 font-medium">
                                {suggestions.some(s => s.source !== 'popular') ? '✨ Suggested for you' : '🔥 Popular topics'}
                            </p>
                            <div className="flex flex-wrap gap-2">
                                {loadingSuggestions ? (
                                    [...Array(6)].map((_, i) => <Skeleton key={i} className="h-8 w-28 rounded-full" />)
                                ) : (
                                    suggestions.map((s, i) => (
                                        <TopicPill
                                            key={i}
                                            topic={s}
                                            onClick={() => handleTopicClick(s.name)}
                                            active={topic === s.name}
                                        />
                                    ))
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Tool Selector */}
                <div className="flex items-center space-x-2 overflow-x-auto pb-1 animate-slide-up" style={{ animationDelay: '200ms' }}>
                    {TOOLS.map(tool => (
                        <button
                            key={tool.id}
                            onClick={() => { setSelectedTool(tool.id); setResult(null); }}
                            className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-sm font-semibold whitespace-nowrap transition-all ${selectedTool === tool.id
                                ? `bg-gradient-to-r ${tool.color} text-white shadow-lg scale-105`
                                : 'bg-white dark:bg-dark-800 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-dark-700 border border-gray-200 dark:border-dark-700'
                                }`}
                        >
                            {tool.icon}
                            <span>{tool.label}</span>
                        </button>
                    ))}
                </div>

                {/* Tool Description */}
                <div className="flex items-center space-x-2 text-sm text-gray-500 dark:text-gray-400 animate-slide-up" style={{ animationDelay: '250ms' }}>
                    {currentTool.icon}
                    <span>{currentTool.description}</span>
                </div>

                {/* Error State */}
                {error && (
                    <div className="card border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/10 animate-slide-up">
                        <div className="flex items-center space-x-3">
                            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
                            <div>
                                <p className="font-medium text-red-700 dark:text-red-400">Generation Failed</p>
                                <p className="text-sm text-red-600 dark:text-red-400/80">{error}</p>
                            </div>
                            <button onClick={handleGenerate} className="btn btn-secondary ml-auto whitespace-nowrap">
                                <RefreshCw className="w-4 h-4 mr-1" /> Retry
                            </button>
                        </div>
                    </div>
                )}

                {/* Loading State */}
                {loading && (
                    <div className="card text-center py-16 animate-slide-up">
                        <div className="flex flex-col items-center space-y-4">
                            <div className="relative">
                                <div className="w-16 h-16 rounded-full bg-gradient-to-r from-primary-600 to-purple-600 animate-pulse flex items-center justify-center">
                                    <Brain className="w-8 h-8 text-white" />
                                </div>
                                <div className="absolute inset-0 w-16 h-16 rounded-full border-2 border-primary-400 border-t-transparent animate-spin" />
                            </div>
                            <div>
                                <p className="font-bold text-lg">Generating {currentTool.label}…</p>
                                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                                    AI is creating a {currentTool.label.toLowerCase()} on "{topic}"
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Result Area */}
                {result && !loading && (
                    <div className="animate-slide-up">
                        {/* Meta bar */}
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-xl font-bold">
                                {currentTool.label}: <span className="gradient-text">{result.topic}</span>
                            </h2>
                            <div className="flex items-center space-x-3 text-xs text-gray-400">
                                <span className="flex items-center space-x-1">
                                    <Clock className="w-3 h-3" />
                                    <span>{(result.generation_time_ms / 1000).toFixed(1)}s</span>
                                </span>
                                <span className="flex items-center space-x-1">
                                    <Star className="w-3 h-3" />
                                    <span>{result.tokens_used} tokens</span>
                                </span>
                            </div>
                        </div>

                        {/* Render based on tool type */}
                        {result.tool === 'guide' && (
                            <div className="card prose prose-sm dark:prose-invert max-w-none">
                                <MarkdownRenderer content={result.content as string} />
                            </div>
                        )}

                        {result.tool === 'flashcards' && (
                            <FlashcardView cards={result.content as FlashcardItem[]} />
                        )}

                        {result.tool === 'quiz' && (
                            <QuizView questions={result.content as QuizQuestion[]} />
                        )}

                        {result.tool === 'concepts' && (
                            <ConceptMapView data={result.content as ConceptMap} />
                        )}

                        {result.tool === 'resources' && (
                            <ResourcesView resources={result.content as ResourceItem[]} />
                        )}
                    </div>
                )}

                {/* Empty State — No result yet, no loading */}
                {!result && !loading && !error && (
                    <div className="card text-center py-16 animate-slide-up" style={{ animationDelay: '300ms' }}>
                        <div className="flex flex-col items-center space-y-4">
                            <div className="p-5 bg-gradient-to-br from-primary-100 to-purple-100 dark:from-primary-900/30 dark:to-purple-900/30 rounded-full">
                                <GraduationCap className="w-12 h-12 text-primary-600 dark:text-primary-400" />
                            </div>
                            <div>
                                <h2 className="text-xl font-bold mb-1">Ready to Study</h2>
                                <p className="text-gray-500 dark:text-gray-400 max-w-md">
                                    Type a topic above or click a suggestion, then hit Generate to create your personalized study materials.
                                </p>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
