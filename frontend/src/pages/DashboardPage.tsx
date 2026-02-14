import React from 'react';
import {
    TrendingUp,
    Brain,
    Flame,
    Clock,
    Target,
    Award,
    BarChart3,
    Zap,
    CheckCircle2,
    AlertCircle
} from 'lucide-react';

export default function DashboardPage() {
    const stats = {
        totalQuestions: 47,
        studyStreak: 7,
        totalTime: 124,
        avgConfidence: 0.85,
        topicsDiscussed: 12
    };

    const topics = [
        { name: 'Supervised Learning', progress: 92, confidence: 0.91, color: 'green' },
        { name: 'Neural Networks', progress: 65, confidence: 0.68, color: 'yellow' },
        { name: 'Gradient Descent', progress: 88, confidence: 0.87, color: 'green' },
        { name: 'Back propagation', progress: 45, confidence: 0.52, color: 'red' }
    ];

    const recommendations = [
        { type: 'review', message: 'Review Back propagation - confidence is low', priority: 'high' },
        { type: 'continue', message: 'Great progress on Supervised Learning!', priority: 'low' },
        { type: 'streak', message: 'Study today to maintain your 7-day streak 🔥', priority: 'medium' }
    ];

    return (
        <div className="min-h-screen p-6">
            <div className="max-w-7xl mx-auto space-y-6">
                {/* Page Header */}
                <div className="animate-slide-up">
                    <h1 className="text-3xl font-bold gradient-text mb-2">Learning Progress</h1>
                    <p className="text-gray-600 dark:text-gray-400">
                        Track your learning journey and identify areas for improvement
                    </p>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <StatCard
                        icon={<Brain className="w-6 h-6" />}
                        label="Questions Asked"
                        value={stats.totalQuestions.toString()}
                        subtext="+12 this week"
                        color="blue"
                    />
                    <StatCard
                        icon={<Flame className="w-6 h-6" />}
                        label="Study Streak"
                        value={`${stats.studyStreak} Days`}
                        subtext="Keep it up! 🔥"
                        color="orange"
                    />
                    <StatCard
                        icon={<Clock className="w-6 h-6" />}
                        label="Time Studied"
                        value={`${stats.totalTime}m`}
                        subtext="This month"
                        color="purple"
                    />
                    <StatCard
                        icon={<Target className="w-6 h-6" />}
                        label="Avg Confidence"
                        value={`${(stats.avgConfidence * 100).toFixed(0)}%`}
                        subtext="Excellent!"
                        color="green"
                    />
                </div>

                {/* Main Content Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Topics Progress */}
                    <div className="lg:col-span-2 card animate-slide-up">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold">Topics Mastery</h2>
                            <BarChart3 className="w-5 h-5 text-gray-400" />
                        </div>

                        <div className="space-y-4">
                            {topics.map((topic, index) => (
                                <div key={index} className="space-y-2">
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="font-medium">{topic.name}</span>
                                        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${topic.color === 'green' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                                                topic.color === 'yellow' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' :
                                                    'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                                            }`}>
                                            {(topic.confidence * 100).toFixed(0)}% confidence
                                        </span>
                                    </div>
                                    <div className="w-full bg-gray-200 dark:bg-dark-700 rounded-full h-2.5 overflow-hidden">
                                        <div
                                            className={`h-full rounded-full transition-all duration-1000 ${topic.color === 'green' ? 'bg-green-500' :
                                                    topic.color === 'yellow' ? 'bg-yellow-500' :
                                                        'bg-red-500'
                                                }`}
                                            style={{ width: `${topic.progress}%` }}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Recommendations */}
                    <div className="card animate-slide-up">
                        <h2 className="text-xl font-bold mb-6">Study Recommendations</h2>

                        <div className="space-y-3">
                            {recommendations.map((rec, index) => (
                                <div
                                    key={index}
                                    className={`p-3 rounded-lg border-l-4 ${rec.priority === 'high' ? 'bg-red-50 dark:bg-red-900/10 border-red-500' :
                                            rec.priority === 'medium' ? 'bg-yellow-50 dark:bg-yellow-900/10 border-yellow-500' :
                                                'bg-green-50 dark:bg-green-900/10 border-green-500'
                                        }`}
                                >
                                    <div className="flex items-start space-x-2">
                                        {rec.priority === 'high' ? (
                                            <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
                                        ) : (
                                            <CheckCircle2 className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
                                        )}
                                        <p className="text-sm text-gray-700 dark:text-gray-300">{rec.message}</p>
                                    </div>
                                </div>
                            ))}
                        </div>

                        <button className="btn btn-primary w-full mt-4">
                            <Zap className="w-4 h-4 mr-2" />
                            Generate Practice Test
                        </button>
                    </div>
                </div>

                {/* Weekly Activity */}
                <div className="card animate-slide-up">
                    <h2 className="text-xl font-bold mb-6">Weekly Activity</h2>

                    <div className="flex items-end justify-between h-48 gap-2">
                        {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, index) => {
                            const height = [60, 80, 75, 90, 85, 70, 95][index];
                            return (
                                <div key={day} className="flex-1 flex flex-col items-center">
                                    <div className="w-full bg-gradient-to-t from-primary-600 to-purple-600 rounded-t-lg transition-all hover:opacity-80"
                                        style={{ height: `${height}%` }}
                                    />
                                    <span className="text-xs text-gray-500 dark:text-gray-400 mt-2">{day}</span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
}

function StatCard({ icon, label, value, subtext, color }: any) {
    const colors = {
        blue: 'from-blue-500 to-blue-600',
        orange: 'from-orange-500 to-orange-600',
        purple: 'from-purple-500 to-purple-600',
        green: 'from-green-500 to-green-600'
    };

    return (
        <div className="card hover:shadow-xl transition-all duration-300 animate-slide-up">
            <div className="flex items-start justify-between">
                <div className="flex-1">
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">{label}</p>
                    <p className="text-3xl font-bold mb-1">{value}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-500">{subtext}</p>
                </div>
                <div className={`p-3 bg-gradient-to-br ${colors[color as keyof typeof colors]} rounded-lg text-white`}>
                    {icon}
                </div>
            </div>
        </div>
    );
}
