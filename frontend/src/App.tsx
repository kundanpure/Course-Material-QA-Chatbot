import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom';
import {
  MessageSquare,
  BarChart3,
  BookOpen,
  Moon,
  Sun,
  Menu,
  X,
  Zap,
  Brain,
  Trophy,
  LogOut,
  Plus,
  Trash2,
  History,
  Loader2,
  FileText,

} from 'lucide-react';
import ChatPage from './pages/ChatPage';
import DashboardPage from './pages/DashboardPage.tsx';
import StudyMaterialsPage from './pages/StudyMaterialsPage.tsx';
import EvaluatePage from './pages/EvaluatePage';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { getSessions, createSession, deleteSession, type ChatSession } from './services/api';
import './index.css';

// ─── Protected Route Wrapper ──────────────────────────────────────────────────

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 via-blue-50 to-purple-50 dark:from-dark-900 dark:via-dark-900 dark:to-dark-800">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}


// ─── Main App Layout (shown when authenticated) ──────────────────────────────

function AppLayout() {
  const { user, logout } = useAuth();
  const [darkMode, setDarkMode] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Chat history state
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [loadingSessions, setLoadingSessions] = useState(false);

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [darkMode]);

  // Load chat sessions
  const loadSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const data = await getSessions();
      setSessions(data);
    } catch (err) {
      console.error('Failed to load sessions', err);
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const handleNewChat = async () => {
    try {
      const session = await createSession('New Chat');
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
    } catch (err) {
      console.error('Failed to create session', err);
    }
  };

  const handleDeleteSession = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (activeSessionId === id) {
        setActiveSessionId(null);
      }
    } catch (err) {
      console.error('Failed to delete session', err);
    }
  };

  const handleSelectSession = (id: number) => {
    setActiveSessionId(id);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-purple-50 dark:from-dark-900 dark:via-dark-900 dark:to-dark-800">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-white/80 dark:bg-dark-900/80 backdrop-blur-lg border-b border-gray-200 dark:border-dark-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center space-x-3">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-800 transition-colors"
              >
                {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
              </button>
              <div className="flex items-center space-x-2">
                <div className="p-2 bg-gradient-to-br from-primary-600 to-purple-600 rounded-lg">
                  <Brain className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold gradient-text">StudyAI</h1>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Your Learning Companion</p>
                </div>
              </div>
            </div>

            {/* Right side actions */}
            <div className="flex items-center space-x-3">
              <div className="hidden md:flex items-center space-x-2 px-3 py-1.5 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 rounded-full text-sm font-medium">
                <Zap size={14} />
                <span>100% Free</span>
              </div>

              <button
                onClick={() => setDarkMode(!darkMode)}
                className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-800 transition-colors"
              >
                {darkMode ? <Sun size={20} /> : <Moon size={20} />}
              </button>

              {/* User menu */}
              <div className="flex items-center space-x-2 pl-3 border-l border-gray-200 dark:border-dark-700">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-500 to-purple-500 flex items-center justify-center text-white text-sm font-bold">
                  {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
                </div>
                <span className="hidden sm:block text-sm font-medium text-gray-700 dark:text-gray-300 max-w-[120px] truncate">
                  {user?.full_name}
                </span>
                <button
                  onClick={logout}
                  className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-500 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                  title="Logout"
                >
                  <LogOut size={18} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-16 bottom-0 w-64 bg-white dark:bg-dark-800 border-r border-gray-200 dark:border-dark-700 transition-transform duration-300 z-40 flex flex-col ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
      >
        {/* Navigation */}
        <nav className="p-4 space-y-2">
          <NavLink to="/" icon={<MessageSquare size={20} />} label="Chat" />
          <NavLink to="/dashboard" icon={<BarChart3 size={20} />} label="Progress" badge="7 🔥" />
          <NavLink to="/study-materials" icon={<BookOpen size={20} />} label="Study Materials" />
          <NavLink to="/evaluate" icon={<FileText size={20} />} label="Evaluate Mode" />
        </nav>

        {/* Chat History */}
        <div className="flex-1 overflow-hidden flex flex-col border-t border-gray-200 dark:border-dark-700">
          <div className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center space-x-2 text-sm font-semibold text-gray-600 dark:text-gray-400">
              <History size={16} />
              <span>Chat History</span>
            </div>
            <button
              onClick={handleNewChat}
              className="p-1.5 rounded-lg hover:bg-primary-50 dark:hover:bg-primary-900/20 text-primary-600 transition-colors"
              title="New Chat"
            >
              <Plus size={16} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
            {loadingSessions ? (
              <div className="flex justify-center py-4">
                <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
              </div>
            ) : sessions.length === 0 ? (
              <p className="text-xs text-gray-400 dark:text-gray-500 text-center py-4">
                No conversations yet
              </p>
            ) : (
              sessions.map((session) => (
                <button
                  key={session.id}
                  onClick={() => handleSelectSession(session.id)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-left transition-colors group text-sm ${activeSessionId === session.id
                    ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-400'
                    : 'hover:bg-gray-100 dark:hover:bg-dark-700 text-gray-700 dark:text-gray-300'
                    }`}
                >
                  <span className="truncate flex-1">{session.title || 'Untitled'}</span>
                  <button
                    onClick={(e) => handleDeleteSession(session.id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-gray-400 hover:text-red-500 transition-all"
                    title="Delete"
                  >
                    <Trash2 size={14} />
                  </button>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Bottom Info */}
        <div className="p-4 border-t border-gray-200 dark:border-dark-700">
          <div className="card p-3 bg-gradient-to-br from-primary-50 to-purple-50 dark:from-primary-900/20 dark:to-purple-900/20 border-0">
            <div className="flex items-center space-x-2 mb-2">
              <Trophy className="w-5 h-5 text-primary-600" />
              <span className="font-semibold text-sm">Pro Tip</span>
            </div>
            <p className="text-xs text-gray-600 dark:text-gray-400">
              Ask follow-up questions! I remember our entire conversation.
            </p>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className={`pt-16 transition-all duration-300 ${sidebarOpen ? 'ml-64' : 'ml-0'}`}>
        <Routes>
          <Route
            path="/"
            element={
              <ChatPage
                sessionId={activeSessionId}
                onSessionCreated={(session: ChatSession) => {
                  setSessions((prev) => [session, ...prev]);
                  setActiveSessionId(session.id);
                }}
              />
            }
          />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/study-materials" element={<StudyMaterialsPage />} />
          <Route path="/evaluate" element={<EvaluatePage />} />
        </Routes>
      </main>
    </div>
  );
}

// ─── NavLink Component ────────────────────────────────────────────────────────

function NavLink({ to, icon, label, badge }: { to: string; icon: React.ReactNode; label: string; badge?: string }) {
  const isActive = window.location.pathname === to;

  return (
    <Link
      to={to}
      className={`flex items-center justify-between px-4 py-3 rounded-lg transition-all hover:bg-gray-100 dark:hover:bg-dark-700 group ${isActive ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600' : 'text-gray-700 dark:text-gray-300'
        }`}
    >
      <div className="flex items-center space-x-3">
        {icon}
        <span className="font-medium">{label}</span>
      </div>
      {badge && (
        <span className={`text-xs px-2 py-0.5 rounded-full ${isActive ? 'bg-primary-100 dark:bg-primary-900/40' : 'bg-gray-100 dark:bg-dark-700'
          }`}>
          {badge}
        </span>
      )}
    </Link>
  );
}


// ─── Root App ─────────────────────────────────────────────────────────────────

function App() {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />

          {/* Protected routes */}
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </Router>
  );
}

export default App;
