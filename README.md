# StudyAI — Intelligent Study Companion 🎓

> **AI-powered study platform** with PDF Q&A, multi-mode RAG pipeline, email verification, Google OAuth, and learning analytics.

<p align="center">
  <img src="screenshots/login.png" width="380" alt="Login Page" />
  <img src="screenshots/signup.png" width="380" alt="Signup Page" />
</p>
<p align="center">
  <img src="screenshots/otp_verify.png" width="380" alt="OTP Verification" />
</p>

---

## 🌟 Features

### 📚 Core — Agentic RAG Pipeline
- **5 Query Modes:** Auto, Fast, Study, Research, Chat
- **Hybrid Retrieval:** FAISS vector search + BM25 keyword search
- **Query Rewriting Agent:** Rewrites queries for better retrieval
- **Reflection Agent:** Validates and enhances generated answers
- **MMR Diversification:** Maximum Marginal Relevance for diverse results
- **Multilingual Support:** Auto language detection + translation
- **Advanced Confidence Scoring:** 6-factor scoring system

### 🔐 Authentication
- **Email + Password** registration with **OTP email verification** (6-digit code)
- **Google OAuth** — one-click "Sign in with Google"
- **JWT tokens** with 24h expiry
- Unverified accounts cannot login (OTP auto-resent)

### 📄 Document Processing
- PDF upload with hierarchical chunking
- Page-level and section-level context tracking
- FAISS + BM25 index building per document
- Multi-document support per session

### 📊 Dashboard & Analytics
- Learning progress tracking
- Topic mastery visualization
- Study streak tracking
- Weekly activity charts

---

## 🏗️ Architecture

```
backend/
├── production_agentic.py    # Main FastAPI app + RAG pipeline
├── auth.py                  # JWT auth + Google token verification
├── routes_auth.py           # Auth endpoints (register, login, verify, Google)
├── routes_chat_history.py   # Chat session CRUD
├── db_postgres.py           # PostgreSQL (NeonDB) integration
├── llm_provider.py          # LLM abstraction (Gemini / Groq)
├── email_service.py         # SMTP email sender for OTP
├── .env                     # Environment configuration
└── frontend/                # React + Vite + TypeScript frontend
    ├── src/
    │   ├── contexts/AuthContext.tsx    # Auth state management
    │   ├── services/api.ts            # API client
    │   ├── pages/
    │   │   ├── ChatPage.tsx           # Main chat interface
    │   │   ├── LoginPage.tsx          # Login + Google Sign-In
    │   │   ├── SignupPage.tsx         # Signup + OTP verification
    │   │   ├── DashboardPage.tsx      # Learning analytics
    │   │   └── StudyMaterialsPage.tsx # Auto-generated materials
    │   └── components/
    │       └── MarkdownRenderer.tsx   # Markdown + code highlighting
    └── index.html
```

### Pipeline Flow

```mermaid
graph TB
    User[User Query] --> A[0. Language Detection]
    A --> B[1. Query Classification]
    B --> C[2. Query Rewriting Agent]
    C --> D[3. Hybrid Retrieval - FAISS + BM25]
    D --> E[4. MMR Diversification]
    E --> F[5. Context Assembly]
    F --> G[6. Answer Generation - LLM]
    G --> H[7. Reflection Agent]
    H --> I[8. Confidence Scoring]
    I --> Response[Final Response]
```

### Auth Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant B as Backend
    participant E as Gmail SMTP
    participant G as Google OAuth

    Note over U,G: Email Registration Flow
    U->>F: Fill signup form
    F->>B: POST /auth/register
    B->>B: Hash password, create user
    B->>E: Send 6-digit OTP email
    B-->>F: { requires_verification: true }
    F->>U: Show OTP input screen
    U->>F: Enter 6-digit code
    F->>B: POST /auth/verify-email
    B->>B: Validate OTP, mark verified
    B-->>F: { token, user }
    F->>U: Redirect to chat

    Note over U,G: Google OAuth Flow
    U->>F: Click "Sign in with Google"
    F->>G: Google Identity Services popup
    G-->>F: ID token (credential)
    F->>B: POST /auth/google
    B->>G: Verify token via tokeninfo API
    B->>B: Create/link user (auto-verified)
    B-->>F: { token, user }
    F->>U: Redirect to chat
```

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **PostgreSQL** (NeonDB configured by default)

### 1. Backend Setup

```bash
# Navigate to backend
cd backend

# Install Python dependencies
pip install fastapi uvicorn google-generativeai pypdf python-dotenv asyncpg \
  python-jose passlib bcrypt sentence-transformers faiss-cpu rank-bm25 \
  langdetect deep-translator httpx aiosmtplib groq

# Start the server
python production_agentic.py
```

Server starts at `http://localhost:8000`
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/v1/health

### 2. Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend starts at `http://localhost:5173`

---

## 🔧 Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# ===== LLM Provider =====
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.0-flash

LLM_PROVIDER=groq              # gemini or groq
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile

# ===== Database (PostgreSQL / NeonDB) =====
POSTGRES_HOST=your-host.neon.tech
POSTGRES_PORT=5432
POSTGRES_USER=your-user
POSTGRES_PASSWORD=your-password
DATABASE_URL=postgresql://user:pass@host/neondb?sslmode=require

# ===== Application =====
SECRET_KEY=your-random-secret-key
DEBUG=True
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8000
ALLOWED_ORIGINS=["http://localhost:5173", "http://localhost:3000"]

# ===== Email Verification (Gmail SMTP) =====
SMTP_EMAIL=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password

# ===== Google OAuth =====
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

### Setting Up Email Verification
1. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
2. Generate an App Password for "Mail"
3. Set `SMTP_EMAIL` and `SMTP_PASSWORD` in `.env`

### Setting Up Google OAuth
1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create an **OAuth 2.0 Client ID** (Web application)
3. Set **Authorized JavaScript origins:** `http://localhost:5173`
4. Set **Authorized redirect URIs:** `http://localhost:8000/api/v1/auth/google/callback`
5. Copy Client ID and Secret to `.env`
6. Update the `GOOGLE_CLIENT_ID` constant in `LoginPage.tsx` and `SignupPage.tsx`

---

## 📡 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/register` | Register with email + password → sends OTP |
| `POST` | `/api/v1/auth/verify-email` | Verify email with 6-digit OTP code |
| `POST` | `/api/v1/auth/resend-code` | Resend OTP to email |
| `POST` | `/api/v1/auth/login` | Login (requires verified email) |
| `POST` | `/api/v1/auth/google` | Login/register with Google ID token |
| `GET`  | `/api/v1/auth/me` | Get current user profile |

### RAG Pipeline
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/query/ask` | Ask a question (supports 5 modes) |
| `POST` | `/api/v1/documents/upload` | Upload PDF document |
| `GET`  | `/api/v1/documents` | List uploaded documents |

### Chat History
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/v1/chat/sessions` | List chat sessions |
| `POST` | `/api/v1/chat/sessions` | Create new session |
| `GET`  | `/api/v1/chat/sessions/{id}/messages` | Get session messages |
| `DELETE` | `/api/v1/chat/sessions/{id}` | Delete session |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/v1/health` | Health check |
| `GET`  | `/api/v1/analytics` | System analytics |

---

## 🛠️ Tech Stack

### Backend
| Technology | Purpose |
|-----------|---------|
| **FastAPI** | Web framework |
| **Uvicorn** | ASGI server |
| **asyncpg** | PostgreSQL driver |
| **Sentence-Transformers** | Embedding model (all-MiniLM-L6-v2) |
| **FAISS** | Vector similarity search |
| **rank-bm25** | BM25 keyword search |
| **Gemini / Groq** | LLM providers |
| **python-jose** | JWT authentication |
| **passlib + bcrypt** | Password hashing |
| **aiosmtplib** | Async email sending |
| **httpx** | Async HTTP (Google token verification) |

### Frontend
| Technology | Purpose |
|-----------|---------|
| **React 18** | UI framework |
| **TypeScript** | Type safety |
| **Vite** | Build tool |
| **TailwindCSS** | Styling |
| **Axios** | HTTP client |
| **React Router** | Navigation |
| **Lucide React** | Icons |
| **Framer Motion** | Animations |

---

## 📝 Query Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| 🤖 **Auto** | Intelligently detects the best pipeline | Default — let the AI decide |
| ⚡ **Fast** | Quick semantic retrieval, minimal processing | Quick fact lookup |
| 📚 **Study** | Generates study guide, key topics, reading plan | Exam preparation |
| 🔬 **Research** | Full hybrid retrieval + citations + reflection | Deep analysis |
| 💬 **Chat** | Conversational mode with document context | Casual discussion |

---

## 📂 Database Schema

The application uses PostgreSQL (NeonDB) with the following tables:

- **`users`** — User accounts (email, hashed password, Google ID, verification status)
- **`documents`** — Uploaded PDFs with metadata and embeddings
- **`queries`** — Query history with confidence scores and retrieval metrics
- **`feedback`** — User feedback on responses
- **`chat_sessions`** — Chat session management
- **`chat_messages`** — Individual chat messages with citations

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is part of an academic project at KIIT University.

---

<p align="center">
  Built with ❤️ for students · StudyAI © 2026
</p>