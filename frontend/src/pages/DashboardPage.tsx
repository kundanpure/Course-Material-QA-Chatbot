import { useState, useEffect } from 'react';
import {
    TrendingUp,
    Brain,
    Flame,
    Clock,
    Target,
    BarChart3,
    Zap,
    CheckCircle2,
    AlertCircle,
    BookOpen,
    Loader2,
    RefreshCw,
    Sparkles,
    ArrowUpRight,
} from 'lucide-react';
import {
    getLearningProgress,
    type ProgressData,
    type TopicProgress,
    type DailyActivity,
    type Recommendation,
} from '../services/api';

// ─── Shimmer Skeleton ─────────────────────────────────────────────────────────

function Skeleton({ className = '' }: { className?: string }) {
    return (
        <div
            className={`animate-pulse bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200 dark:from-dark-700 dark:via-dark-600 dark:to-dark-700 rounded-lg ${className}`}
            style={{
                backgroundSize: '200% 100%',
                animation: 'shimmer 1.5s ease-in-out infinite',
            }}
        />
    );
}

function StatCardSkeleton() {
    return (
        <div className="card">
            <div className="flex items-start justify-between">
                <div className="flex-1 space-y-3">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-8 w-16" />
                    <Skeleton className="h-3 w-20" />
                </div>
                <Skeleton className="h-12 w-12 rounded-lg" />
            </div>
        </div>
    );
}

// ─── Stat Card ────────────────────────────────────────────────────────────────

function StatCard({
    icon,
    label,
    value,
    subtext,
    color,
    delay = 0,
}: {
    icon: React.ReactNode;
    label: string;
    value: string;
    subtext: string;
    color: string;
    delay?: number;
}) {
    const colors: Record<string, string> = {
        blue: 'from-blue-500 to-blue-600',
        orange: 'from-orange-500 to-orange-600',
        purple: 'from-purple-500 to-purple-600',
        green: 'from-green-500 to-green-600',
    };

    const glowColors: Record<string, string> = {
        blue: 'shadow-blue-500/20',
        orange: 'shadow-orange-500/20',
        purple: 'shadow-purple-500/20',
        green: 'shadow-green-500/20',
    };

    return (
        <div
            className="card hover:shadow-xl transition-all duration-500 group cursor-default animate-slide-up"
            style={{ animationDelay: `${delay}ms` }}
        >
            <div className="flex items-start justify-between">
                <div className="flex-1">
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-1 font-medium">
                        {label}
                    </p>
                    <p className="text-3xl font-bold mb-1 tracking-tight">{value}</p>
                    <div className="flex items-center space-x-1 text-xs text-gray-500 dark:text-gray-500">
                        <ArrowUpRight size={12} className="text-green-500" />
                        <span>{subtext}</span>
                    </div>
                </div>
                <div
                    className={`p-3 bg-gradient-to-br ${colors[color] || colors.blue} rounded-xl text-white shadow-lg ${glowColors[color] || ''} group-hover:scale-110 transition-transform duration-300`}
                >
                    {icon}
                </div>
            </div>
        </div>
    );
}

// ─── Confidence Badge ─────────────────────────────────────────────────────────

function ConfidenceBadge({ value, size = 'sm' }: { value: number; size?: 'sm' | 'lg' }) {
    const percent = Math.round(value * 100);
    const colorClass =
        percent >= 75
            ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
            : percent >= 50
                ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400';

    return (
        <span
            className={`px-2 py-0.5 rounded-full font-semibold ${colorClass} ${size === 'lg' ? 'text-sm' : 'text-xs'}`}
        >
            {percent}% confidence
        </span>
    );
}

// ─── Progress Bar ─────────────────────────────────────────────────────────────

function AnimatedProgressBar({
    progress,
    color,
    delay = 0,
}: {
    progress: number;
    color: string;
    delay?: number;
}) {
    const [width, setWidth] = useState(0);

    useEffect(() => {
        const timer = setTimeout(() => setWidth(progress), 200 + delay);
        return () => clearTimeout(timer);
    }, [progress, delay]);

    const barColors: Record<string, string> = {
        green: 'from-green-400 to-green-600',
        yellow: 'from-yellow-400 to-yellow-600',
        red: 'from-red-400 to-red-600',
    };

    return (
        <div className="w-full bg-gray-200 dark:bg-dark-700 rounded-full h-2.5 overflow-hidden">
            <div
                className={`h-full rounded-full bg-gradient-to-r ${barColors[color] || barColors.green} transition-all duration-1000 ease-out`}
                style={{ width: `${width}%` }}
            />
        </div>
    );
}

// ─── Weekly Activity Chart ────────────────────────────────────────────────────

function WeeklyChart({ data }: { data: DailyActivity[] }) {
    const maxQ = Math.max(...data.map((d) => d.questions), 1);

    return (
        <div className="flex items-end justify-between h-48 gap-2 px-2">
            {data.map((day, index) => {
                const height = (day.questions / maxQ) * 100;
                const isToday = index === data.length - 1;

                return (
                    <div key={day.date} className="flex-1 flex flex-col items-center group">
                        {/* Tooltip */}
                        <div className="opacity-0 group-hover:opacity-100 transition-opacity mb-2 text-xs font-medium text-gray-600 dark:text-gray-400">
                            {day.questions}
                        </div>

                        {/* Bar */}
                        <div className="w-full flex flex-col justify-end" style={{ height: '100%' }}>
                            <div
                                className={`w-full rounded-t-lg transition-all duration-700 ease-out ${isToday
                                    ? 'bg-gradient-to-t from-primary-600 to-purple-500 shadow-lg shadow-primary-600/30'
                                    : day.questions > 0
                                        ? 'bg-gradient-to-t from-primary-600/80 to-purple-500/80'
                                        : 'bg-gray-200 dark:bg-dark-700'
                                    }`}
                                style={{
                                    height: `${Math.max(height, day.questions > 0 ? 8 : 4)}%`,
                                    animationDelay: `${index * 100}ms`,
                                }}
                            />
                        </div>

                        {/* Label */}
                        <span
                            className={`text-xs mt-2 font-medium ${isToday ? 'text-primary-600 dark:text-primary-400' : 'text-gray-500 dark:text-gray-400'}`}
                        >
                            {day.day}
                        </span>
                    </div>
                );
            })}
        </div>
    );
}

// ─── Empty State ──────────────────────────────────────────────────────────────

function EmptyState() {
    return (
        <div className="flex flex-col items-center justify-center py-16 text-center animate-slide-up">
            <div className="p-6 bg-gradient-to-br from-primary-100 to-purple-100 dark:from-primary-900/30 dark:to-purple-900/30 rounded-full mb-6">
                <Sparkles className="w-12 h-12 text-primary-600 dark:text-primary-400" />
            </div>
            <h2 className="text-2xl font-bold mb-2">Start Your Learning Journey</h2>
            <p className="text-gray-500 dark:text-gray-400 max-w-md mb-6">
                Upload a PDF and ask questions to begin tracking your progress. Your study
                streak, topic mastery, and confidence scores will appear here.
            </p>
            <div className="flex items-center space-x-2 text-sm text-primary-600 dark:text-primary-400">
                <BookOpen size={16} />
                <span>Go to Chat to get started</span>
            </div>
        </div>
    );
}

// ─── Main Dashboard Page ──────────────────────────────────────────────────────

export default function DashboardPage() {
    const [progress, setProgress] = useState<ProgressData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [refreshing, setRefreshing] = useState(false);

    const fetchProgress = async (isRefresh = false) => {
        if (isRefresh) setRefreshing(true);
        else setLoading(true);
        setError(null);

        try {
            const data = await getLearningProgress();
            setProgress(data);
        } catch (err: any) {
            console.error('Failed to load progress:', err);
            setError(err?.response?.data?.detail || 'Failed to load progress');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchProgress();
    }, []);

    // ── Loading State
    if (loading) {
        return (
            <div className="min-h-screen p-6">
                <div className="max-w-7xl mx-auto space-y-6">
                    <div className="space-y-2">
                        <Skeleton className="h-8 w-64" />
                        <Skeleton className="h-5 w-96" />
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                        {[...Array(4)].map((_, i) => (
                            <StatCardSkeleton key={i} />
                        ))}
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <div className="lg:col-span-2 card">
                            <Skeleton className="h-6 w-40 mb-6" />
                            <div className="space-y-6">
                                {[...Array(4)].map((_, i) => (
                                    <div key={i} className="space-y-2">
                                        <Skeleton className="h-4 w-full" />
                                        <Skeleton className="h-2.5 w-full rounded-full" />
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div className="card">
                            <Skeleton className="h-6 w-48 mb-6" />
                            <div className="space-y-3">
                                {[...Array(3)].map((_, i) => (
                                    <Skeleton key={i} className="h-16 w-full" />
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // ── Error State
    if (error) {
        return (
            <div className="min-h-screen p-6 flex items-center justify-center">
                <div className="card text-center max-w-md animate-slide-up">
                    <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
                    <h2 className="text-xl font-bold mb-2">Failed to Load Progress</h2>
                    <p className="text-gray-500 dark:text-gray-400 mb-4">{error}</p>
                    <button onClick={() => fetchProgress()} className="btn btn-primary">
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    const data = progress!;
    const isNewUser = data.total_questions === 0;

    return (
        <div className="min-h-screen p-6">
            <div className="max-w-7xl mx-auto space-y-6">
                {/* Page Header */}
                <div className="flex items-center justify-between animate-slide-up">
                    <div>
                        <h1 className="text-3xl font-bold gradient-text mb-2">
                            Learning Progress
                        </h1>
                        <p className="text-gray-600 dark:text-gray-400">
                            Track your learning journey and identify areas for improvement
                        </p>
                    </div>
                    <button
                        onClick={() => fetchProgress(true)}
                        disabled={refreshing}
                        className="btn btn-secondary"
                    >
                        <RefreshCw
                            className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`}
                        />
                        Refresh
                    </button>
                </div>

                {isNewUser ? (
                    <EmptyState />
                ) : (
                    <>
                        {/* Stats Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                            <StatCard
                                icon={<Brain className="w-6 h-6" />}
                                label="Questions Asked"
                                value={data.total_questions.toString()}
                                subtext="Total queries"
                                color="blue"
                                delay={0}
                            />
                            <StatCard
                                icon={<Flame className="w-6 h-6" />}
                                label="Study Streak"
                                value={
                                    data.study_streak > 0
                                        ? `${data.study_streak} Day${data.study_streak !== 1 ? 's' : ''}`
                                        : 'Start today!'
                                }
                                subtext={data.study_streak > 0 ? 'Keep it up! 🔥' : 'Begin your streak'}
                                color="orange"
                                delay={100}
                            />
                            <StatCard
                                icon={<Clock className="w-6 h-6" />}
                                label="Time Studied"
                                value={
                                    data.total_study_time_min >= 60
                                        ? `${Math.floor(data.total_study_time_min / 60)}h ${data.total_study_time_min % 60}m`
                                        : `${data.total_study_time_min}m`
                                }
                                subtext="Estimated total"
                                color="purple"
                                delay={200}
                            />
                            <StatCard
                                icon={<Target className="w-6 h-6" />}
                                label="Avg Confidence"
                                value={`${Math.round(data.avg_confidence * 100)}%`}
                                subtext={
                                    data.avg_confidence >= 0.8
                                        ? 'Excellent!'
                                        : data.avg_confidence >= 0.6
                                            ? 'Good progress'
                                            : 'Room to grow'
                                }
                                color="green"
                                delay={300}
                            />
                        </div>

                        {/* Main Content Grid */}
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            {/* Topics Mastery */}
                            <div
                                className="lg:col-span-2 card animate-slide-up"
                                style={{ animationDelay: '200ms' }}
                            >
                                <div className="flex items-center justify-between mb-6">
                                    <div className="flex items-center space-x-2">
                                        <BarChart3 className="w-5 h-5 text-primary-600" />
                                        <h2 className="text-xl font-bold">Topics Mastery</h2>
                                    </div>
                                    <span className="text-sm text-gray-500 dark:text-gray-400">
                                        {data.topics.length} topic{data.topics.length !== 1 ? 's' : ''}
                                    </span>
                                </div>

                                {data.topics.length === 0 ? (
                                    <div className="flex flex-col items-center py-8 text-gray-400 dark:text-gray-500">
                                        <TrendingUp className="w-10 h-10 mb-3 opacity-50" />
                                        <p className="text-sm">Ask more questions to see topic mastery</p>
                                    </div>
                                ) : (
                                    <div className="space-y-5">
                                        {data.topics.map((topic: TopicProgress, index: number) => (
                                            <div key={topic.name} className="space-y-2">
                                                <div className="flex items-center justify-between text-sm">
                                                    <div className="flex items-center space-x-2">
                                                        <span className="font-medium">{topic.name}</span>
                                                        <span className="text-xs text-gray-400 dark:text-gray-500">
                                                            ({topic.question_count} Q)
                                                        </span>
                                                    </div>
                                                    <ConfidenceBadge value={topic.avg_confidence} />
                                                </div>
                                                <AnimatedProgressBar
                                                    progress={topic.progress}
                                                    color={topic.color}
                                                    delay={index * 100}
                                                />
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>

                            {/* Recommendations */}
                            <div
                                className="card animate-slide-up"
                                style={{ animationDelay: '300ms' }}
                            >
                                <div className="flex items-center space-x-2 mb-6">
                                    <Sparkles className="w-5 h-5 text-purple-500" />
                                    <h2 className="text-xl font-bold">Study Recommendations</h2>
                                </div>

                                <div className="space-y-3">
                                    {data.recommendations.map(
                                        (rec: Recommendation, index: number) => (
                                            <div
                                                key={index}
                                                className={`p-3 rounded-xl border-l-4 transition-all hover:scale-[1.01] ${rec.priority === 'high'
                                                    ? 'bg-red-50 dark:bg-red-900/10 border-red-500'
                                                    : rec.priority === 'medium'
                                                        ? 'bg-yellow-50 dark:bg-yellow-900/10 border-yellow-500'
                                                        : 'bg-green-50 dark:bg-green-900/10 border-green-500'
                                                    }`}
                                            >
                                                <div className="flex items-start space-x-2">
                                                    {rec.priority === 'high' ? (
                                                        <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
                                                    ) : rec.priority === 'medium' ? (
                                                        <Flame className="w-5 h-5 text-yellow-500 mt-0.5 flex-shrink-0" />
                                                    ) : (
                                                        <CheckCircle2 className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
                                                    )}
                                                    <p className="text-sm text-gray-700 dark:text-gray-300">
                                                        {rec.message}
                                                    </p>
                                                </div>
                                            </div>
                                        )
                                    )}
                                </div>

                                <button
                                    onClick={() => (window.location.href = '/evaluate')}
                                    className="btn btn-primary w-full mt-5"
                                >
                                    <Zap className="w-4 h-4 mr-2" />
                                    Take a Practice Test
                                </button>
                            </div>
                        </div>

                        {/* Weekly Activity */}
                        <div
                            className="card animate-slide-up"
                            style={{ animationDelay: '400ms' }}
                        >
                            <div className="flex items-center justify-between mb-6">
                                <div className="flex items-center space-x-2">
                                    <TrendingUp className="w-5 h-5 text-primary-600" />
                                    <h2 className="text-xl font-bold">Weekly Activity</h2>
                                </div>
                                <div className="flex items-center space-x-2 text-sm text-gray-500 dark:text-gray-400">
                                    <span>Last 7 days</span>
                                    <span className="inline-block w-3 h-3 rounded-sm bg-gradient-to-t from-primary-600 to-purple-500" />
                                </div>
                            </div>

                            {data.weekly_activity.every((d: DailyActivity) => d.questions === 0) ? (
                                <div className="flex flex-col items-center py-12 text-gray-400 dark:text-gray-500">
                                    <BarChart3 className="w-10 h-10 mb-3 opacity-50" />
                                    <p className="text-sm">No activity this week yet. Ask some questions!</p>
                                </div>
                            ) : (
                                <WeeklyChart data={data.weekly_activity} />
                            )}
                        </div>

                        {/* Quick Stats Footer */}
                        <div
                            className="grid grid-cols-2 md:grid-cols-3 gap-4 animate-slide-up"
                            style={{ animationDelay: '500ms' }}
                        >
                            <div className="card p-4 bg-gradient-to-br from-primary-50 to-purple-50 dark:from-primary-900/20 dark:to-purple-900/20 border-0">
                                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                                    Documents Uploaded
                                </p>
                                <p className="text-2xl font-bold">{data.documents_uploaded}</p>
                            </div>
                            <div className="card p-4 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border-0">
                                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                                    Reflection Rate
                                </p>
                                <p className="text-2xl font-bold">
                                    {Math.round(data.reflection_rate * 100)}%
                                </p>
                            </div>
                            <div className="card p-4 bg-gradient-to-br from-orange-50 to-amber-50 dark:from-orange-900/20 dark:to-amber-900/20 border-0 col-span-2 md:col-span-1">
                                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                                    Topic Areas
                                </p>
                                <p className="text-2xl font-bold">{data.topics.length}</p>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
