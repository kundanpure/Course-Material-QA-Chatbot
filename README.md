# Course Material QA Chatbot 🚀

# Jisko jo features add karna h jo karna h karo 
and abhi filhaal full architecture ke saath nhi h ( please ignore - `agents/` (Advanced microservice agents)
- `api/` (Complex router structure)
- `core/` (Deep infrastructure)
- `db/` (SQLAlchemy ORM models)
- `services/` (External service connectors)
- `workers/` (Celery background tasks) ) 
like working code of backend is in Production_agentic.py me h and frontend ( react with ts ) frontend folder me h #
#  if you want to change pipeline, want to experiment somthing pull the code in local implement run and pull #

> **Current Status:** this pipeline uses `production_agentic.py` (Standalone Agentic Server) which implements the full RAG pipeline without complex microservice dependencies.

## 🌟 Key Innovations

This project implements cutting-edge RAG techniques:
- **Agentic Pipeline:** Query Classifier → Retrieval Strategy → Answer Composer → Validator
- **Deep Research:** Hybrid search (Vector + Keyword)
- **Self-Healing:** Automatic retries and strategy adaptation
- **Semantic Caching:** Instant responses for similar queries
- **Data Persistence:** PostgreSQL storage for documents and history

---

## 🚀 Quick Start (Current Working Version)

Follow these steps to run the specialized agentic pipeline.

### 1. Backend Setup

The backend runs a standalone agentic server (`production_agentic.py`) that handles the entire RAG pipeline.

**Prerequisites:**
- Python 3.11+
- PostgreSQL (NeonDB is configured in `.env`)

**Installation:**
```bash
# 1. Navigate to backend root
cd backend

# 2. Install required libraries
pip install fastapi uvicorn google-generativeai pypdf python-dotenv asyncpg psycopg2-binary sqlalchemy

# 3. Security & Code Sanitization (Optional but recommended for Windows)
python sanitize_code.py

# 4. Run the Production Server
python production_agentic.py
```

The server will start at `http://localhost:8000`.
- **Docs:** `http://localhost:8000/docs`
- **Health:** `http://localhost:8000/api/v1/health`

### 2. Frontend Setup

The frontend is a modern React + Vite application located in the `frontend/` directory.

**Installation:**
```bash
# 1. Navigate to frontend (from backend root)
cd frontend

# 2. Install dependencies
npm install

# 3. Start Development Server
npm run dev
```

The frontend will start at `http://localhost:5173`.
*Make sure your Tailwind CSS is working and aligned with the needed version (v3.4+ recommended).*

---

## 📂 Project Structure Note

For the current working version, please **IGNORE** the following folders:
- `agents/` (Advanced microservice agents)
- `api/` (Complex router structure)
- `core/` (Deep infrastructure)
- `db/` (SQLAlchemy ORM models)
- `services/` (External service connectors)
- `workers/` (Celery background tasks)

These folders contain the **Advanced Enterprise Version** (Microservices Architecture) which is reserved for future scaling. For now, all logic is consolidated in `production_agentic.py` for ease of deployment and maintenance.

---

## 🏗️ Architecture (Visual)

```mermaid
graph TB
    User[User Question] --> Step1[1. Query Classifier]
    Step1 --> Step2[2. Retrieval Strategy]
    Step2 --> Step3[3. Document Retrieval (PostgreSQL)]
    Step3 --> Step4[4. Answer Composer (Gemini)]
    Step4 --> Step5[5. Validator & Confidence]
    Step5 --> Response[Final Response]
```

---

## 🔧 Configuration (.env)

Ensure your `.env` file in the `backend/` root has:
```env
GEMINI_API_KEY=AIzaSy...
POSTGRES_HOST=...
POSTGRES_USER=...
POSTGRES_PASSWORD=...
POSTGRES_DB=neondb
DATABASE_URL=postgresql://...
```
*(Credentials are pre-configured for the current environment)*
