import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useNavigate } from 'react-router-dom';
import {
  MessageSquare,
  BarChart3,
  BookOpen,
  Sparkles,
  Moon,
  Sun,
  Menu,
  X,
  Zap,
  Brain,
  Trophy
} from 'lucide-react';
import ChatPage from './pages/ChatPage';
import DashboardPage from './pages/DashboardPage.tsx';
import StudyMaterialsPage from './pages/StudyMaterialsPage.tsx';
import './index.css';

function App() {
  const [darkMode, setDarkMode] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [darkMode]);

  return (
    <Router>
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
              </div>
            </div>
          </div>
        </header>

        {/* Sidebar */}
        <aside
          className={`fixed left-0 top-16 bottom-0 w-64 bg-white dark:bg-dark-800 border-r border-gray-200 dark:border-dark-700 transition-transform duration-300 z-40 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'
            }`}
        >
          <nav className="p-4 space-y-2">
            <NavLink to="/" icon={<MessageSquare size={20} />} label="Chat" />
            <NavLink to="/dashboard" icon={<BarChart3 size={20} />} label="Progress" badge="7 🔥" />
            <NavLink to="/study-materials" icon={<BookOpen size={20} />} label="Study Materials" badge="15" />
          </nav>

          {/* Bottom Info */}
          <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-200 dark:border-dark-700">
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
            <Route path="/" element={<ChatPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/study-materials" element={<StudyMaterialsPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

// NavLink Component
function NavLink({ to, icon, label, badge }: { to: string; icon: React.ReactNode; label: string; badge?: string }) {
  const navigate = useNavigate();
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

export default App;
