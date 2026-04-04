"""
PostgreSQL Database Integration - v4.0.0
Supports: documents with embeddings, v4 query analytics, feedback
NeonDB (asyncpg) compatible
"""
import asyncpg
import json
import pickle
import numpy as np
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()

# Database connection pool
db_pool: Optional[asyncpg.Pool] = None

# ─── Schema ────────────────────────────────────────────────────────────────────

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id              SERIAL PRIMARY KEY,
    doc_id          VARCHAR(50) UNIQUE NOT NULL,
    filename        VARCHAR(255) NOT NULL,
    text_content    TEXT NOT NULL,
    chunks          JSONB NOT NULL,
    embeddings      BYTEA,
    page_count      INTEGER NOT NULL,
    uploaded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS queries (
    id                    SERIAL PRIMARY KEY,
    query_text            TEXT NOT NULL,
    query_type            VARCHAR(50),
    retrieval_strategy    VARCHAR(50),
    answer                TEXT,
    citations             JSONB,
    confidence            FLOAT,
    chunks_retrieved      INTEGER,
    chunks_used           INTEGER,
    tokens_used           INTEGER,
    retrieval_time_ms     FLOAT,
    generation_time_ms    FLOAT,
    total_time_ms         FLOAT,
    mmr_diversity_score   FLOAT,
    avg_retrieval_score   FLOAT,
    reflection_validated  BOOLEAN,
    language_detected     VARCHAR(20),
    original_query        TEXT,
    rewritten_query       TEXT,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feedback (
    id          SERIAL PRIMARY KEY,
    query_id    INTEGER REFERENCES queries(id),
    helpful     BOOLEAN NOT NULL,
    comment     TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id                    SERIAL PRIMARY KEY,
    email                 VARCHAR(255) UNIQUE NOT NULL,
    full_name             VARCHAR(255) NOT NULL,
    hashed_pw             VARCHAR(255) NOT NULL DEFAULT '',
    provider              VARCHAR(50) DEFAULT 'local',
    avatar_url            TEXT,
    is_active             BOOLEAN DEFAULT TRUE,
    is_verified           BOOLEAN DEFAULT FALSE,
    verification_code     VARCHAR(6),
    verification_expires  TIMESTAMP,
    google_id             VARCHAR(255) UNIQUE,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login            TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(255),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id              SERIAL PRIMARY KEY,
    session_id      INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL,
    content         TEXT NOT NULL,
    mode            VARCHAR(20),
    confidence      FLOAT,
    citations       JSONB DEFAULT '[]',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS session_documents (
    id          SERIAL PRIMARY KEY,
    session_id  INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE,
    doc_id      VARCHAR(50) NOT NULL,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, doc_id)
);

CREATE INDEX IF NOT EXISTS idx_documents_doc_id      ON documents(doc_id);
CREATE INDEX IF NOT EXISTS idx_queries_created_at    ON queries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_users_email           ON users(email);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user    ON chat_sessions(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_session_docs          ON session_documents(session_id);
"""

# Migration SQL — run once to add v4 columns to existing tables
MIGRATE_V4_SQL = """
DO $$
BEGIN
    -- documents.embeddings
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='documents' AND column_name='embeddings'
    ) THEN
        ALTER TABLE documents ADD COLUMN embeddings BYTEA;
    END IF;

    -- queries v4 columns
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='queries' AND column_name='mmr_diversity_score'
    ) THEN
        ALTER TABLE queries ADD COLUMN mmr_diversity_score  FLOAT;
        ALTER TABLE queries ADD COLUMN avg_retrieval_score  FLOAT;
        ALTER TABLE queries ADD COLUMN reflection_validated BOOLEAN;
        ALTER TABLE queries ADD COLUMN language_detected    VARCHAR(20);
        ALTER TABLE queries ADD COLUMN original_query       TEXT;
        ALTER TABLE queries ADD COLUMN rewritten_query      TEXT;
    END IF;

    -- queries: per-user tracking
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='queries' AND column_name='user_id'
    ) THEN
        ALTER TABLE queries ADD COLUMN user_id INTEGER REFERENCES users(id);
        CREATE INDEX IF NOT EXISTS idx_queries_user_id ON queries(user_id, created_at DESC);
    END IF;

    -- users: email verification + google oauth columns
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='users' AND column_name='is_verified'
    ) THEN
        ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='users' AND column_name='verification_code'
    ) THEN
        ALTER TABLE users ADD COLUMN verification_code VARCHAR(6);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='users' AND column_name='verification_expires'
    ) THEN
        ALTER TABLE users ADD COLUMN verification_expires TIMESTAMP;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='users' AND column_name='google_id'
    ) THEN
        ALTER TABLE users ADD COLUMN google_id VARCHAR(255) UNIQUE;
    END IF;
END
$$;
"""

# ─── Connection ────────────────────────────────────────────────────────────────

async def init_db() -> bool:
    """Initialize database connection pool and create / migrate tables."""
    global db_pool

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("[DB] Warning: DATABASE_URL not found, skipping database init")
        return False

    try:
        db_pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )

        async with db_pool.acquire() as conn:
            await conn.execute(CREATE_TABLES_SQL)
            await conn.execute(MIGRATE_V4_SQL)

        print("[DB] [OK] PostgreSQL (NeonDB) connected — v4 schema ready")
        return True

    except Exception as e:
        print(f"[DB] [ERROR] Failed to initialize database: {e}")
        db_pool = None
        return False


async def close_db():
    """Close database connection pool."""
    global db_pool
    if db_pool:
        await db_pool.close()
        print("[DB] Connection closed")

# ─── Document Operations ───────────────────────────────────────────────────────

async def save_document(
    doc_id: str,
    filename: str,
    text: str,
    chunks: List[Dict],
    page_count: int,
    embeddings: Optional[np.ndarray] = None,
) -> bool:
    """Save document + optional embeddings to NeonDB."""
    if not db_pool:
        return False

    try:
        embeddings_bytes = pickle.dumps(embeddings) if embeddings is not None else None

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO documents (doc_id, filename, text_content, chunks, page_count, embeddings)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (doc_id) DO UPDATE
                SET filename      = $2,
                    text_content  = $3,
                    chunks        = $4,
                    page_count    = $5,
                    embeddings    = $6
                """,
                doc_id, filename, text, json.dumps(chunks), page_count, embeddings_bytes,
            )
        return True
    except Exception as e:
        print(f"[DB] Error saving document: {e}")
        return False


async def get_all_documents() -> Dict[str, Dict]:
    """Load all documents (with embeddings) from NeonDB."""
    if not db_pool:
        return {}

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM documents ORDER BY uploaded_at DESC"
            )

            documents: Dict[str, Dict] = {}
            for row in rows:
                emb = None
                if row["embeddings"]:
                    try:
                        emb = pickle.loads(row["embeddings"])
                    except Exception:
                        emb = None

                documents[row["doc_id"]] = {
                    "filename":    row["filename"],
                    "text":        row["text_content"],
                    "chunks":      json.loads(row["chunks"]),
                    "page_count":  row["page_count"],
                    "embeddings":  emb,
                    "uploaded_at": row["uploaded_at"].timestamp(),
                }

            return documents

    except Exception as e:
        print(f"[DB] Error loading documents: {e}")
        return {}


async def delete_document(doc_id: str) -> bool:
    """Delete document from NeonDB."""
    if not db_pool:
        return False

    try:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM documents WHERE doc_id = $1", doc_id)
        return True
    except Exception as e:
        print(f"[DB] Error deleting document: {e}")
        return False

# ─── Query Operations ──────────────────────────────────────────────────────────

async def save_query(
    query_text: str,
    query_type: str,
    strategy: str,
    answer: str,
    citations: List[Dict],
    confidence: float,
    chunks_retrieved: int,
    chunks_used: int,
    tokens_used: int,
    retrieval_time_ms: float,
    generation_time_ms: float,
    total_time_ms: float,
    # v4 extras
    mmr_diversity_score: float = 0.0,
    avg_retrieval_score: float = 0.0,
    reflection_validated: bool = False,
    language_detected: str = "en",
    original_query: str = "",
    rewritten_query: str = "",
    # per-user tracking
    user_id: Optional[int] = None,
) -> Optional[int]:
    """Save query (with v4 analytics) to NeonDB and return row ID."""
    if not db_pool:
        return None

    try:
        async with db_pool.acquire() as conn:
            query_id = await conn.fetchval(
                """
                INSERT INTO queries (
                    query_text, query_type, retrieval_strategy, answer, citations,
                    confidence, chunks_retrieved, chunks_used, tokens_used,
                    retrieval_time_ms, generation_time_ms, total_time_ms,
                    mmr_diversity_score, avg_retrieval_score, reflection_validated,
                    language_detected, original_query, rewritten_query,
                    user_id
                ) VALUES (
                    $1,  $2,  $3,  $4,  $5,
                    $6,  $7,  $8,  $9,
                    $10, $11, $12,
                    $13, $14, $15,
                    $16, $17, $18,
                    $19
                )
                RETURNING id
                """,
                query_text, query_type, strategy, answer, json.dumps(citations),
                confidence, chunks_retrieved, chunks_used, tokens_used,
                retrieval_time_ms, generation_time_ms, total_time_ms,
                mmr_diversity_score, avg_retrieval_score, reflection_validated,
                language_detected, original_query, rewritten_query,
                user_id,
            )
        return query_id
    except Exception as e:
        print(f"[DB] Error saving query: {e}")
        return None


async def get_query_history(limit: int = 50) -> List[Dict]:
    """Get recent query history from NeonDB."""
    if not db_pool:
        return []

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, query_text, query_type, answer, confidence,
                       reflection_validated, language_detected, created_at
                FROM queries
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
            return [dict(row) for row in rows]

    except Exception as e:
        print(f"[DB] Error loading query history: {e}")
        return []

# ─── Feedback Operations ───────────────────────────────────────────────────────

async def save_feedback(
    query_id: int, helpful: bool, comment: Optional[str] = None
) -> bool:
    """Save user feedback to NeonDB."""
    if not db_pool:
        return False

    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO feedback (query_id, helpful, comment) VALUES ($1, $2, $3)",
                query_id, helpful, comment,
            )
        return True
    except Exception as e:
        print(f"[DB] Error saving feedback: {e}")
        return False

# ─── Analytics ────────────────────────────────────────────────────────────────

async def get_analytics() -> Dict[str, Any]:
    """Get usage analytics from NeonDB."""
    if not db_pool:
        return {}

    try:
        async with db_pool.acquire() as conn:
            stats: Dict[str, Any] = {}

            stats["total_queries"]    = await conn.fetchval("SELECT COUNT(*) FROM queries")
            stats["avg_confidence"]   = await conn.fetchval(
                "SELECT AVG(confidence) FROM queries WHERE confidence > 0"
            ) or 0.0
            stats["total_documents"]  = await conn.fetchval("SELECT COUNT(*) FROM documents")
            stats["reflection_rate"]  = await conn.fetchval(
                "SELECT AVG(CASE WHEN reflection_validated THEN 1.0 ELSE 0.0 END) FROM queries"
            ) or 0.0
            stats["avg_retrieval_score"] = await conn.fetchval(
                "SELECT AVG(avg_retrieval_score) FROM queries WHERE avg_retrieval_score > 0"
            ) or 0.0

            type_dist = await conn.fetch(
                "SELECT query_type, COUNT(*) as count FROM queries GROUP BY query_type"
            )
            stats["query_types"] = {r["query_type"]: r["count"] for r in type_dist}

            lang_dist = await conn.fetch(
                "SELECT language_detected, COUNT(*) as count FROM queries GROUP BY language_detected"
            )
            stats["languages"] = {r["language_detected"]: r["count"] for r in lang_dist}

            return stats

    except Exception as e:
        print(f"[DB] Error getting analytics: {e}")
        return {}


# ─── User Operations ──────────────────────────────────────────────────────────

async def create_user(
    email: str, full_name: str, hashed_pw: str, provider: str = "local"
) -> Optional[Dict]:
    """Create a new user. Returns user dict or None if email taken."""
    if not db_pool:
        return None
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (email, full_name, hashed_pw, provider)
                VALUES ($1, $2, $3, $4)
                RETURNING id, email, full_name, provider, avatar_url, is_active, created_at
                """,
                email, full_name, hashed_pw, provider,
            )
            return dict(row) if row else None
    except asyncpg.UniqueViolationError:
        return None
    except Exception as e:
        print(f"[DB] Error creating user: {e}")
        return None


async def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email (includes hashed_pw for verification)."""
    if not db_pool:
        return None
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE email = $1 AND is_active = TRUE", email
            )
            return dict(row) if row else None
    except Exception as e:
        print(f"[DB] Error getting user: {e}")
        return None


async def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by ID."""
    if not db_pool:
        return None
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, full_name, provider, avatar_url, is_active, created_at FROM users WHERE id = $1",
                user_id,
            )
            return dict(row) if row else None
    except Exception as e:
        print(f"[DB] Error getting user by id: {e}")
        return None


async def update_last_login(user_id: int):
    """Update last_login timestamp."""
    if not db_pool:
        return
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = $1", user_id
            )
    except Exception as e:
        print(f"[DB] Error updating last_login: {e}")


async def set_verification_code(email: str, code: str, expires_at) -> bool:
    """Store OTP code and expiry for a user."""
    if not db_pool:
        return False
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET verification_code = $1, verification_expires = $2 WHERE email = $3",
                code, expires_at, email,
            )
        return True
    except Exception as e:
        print(f"[DB] Error setting verification code: {e}")
        return False


async def verify_user_email(email: str, code: str) -> bool:
    """Verify OTP and mark user as verified. Returns True if successful."""
    if not db_pool:
        return False
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT verification_code, verification_expires FROM users WHERE email = $1",
                email,
            )
            if not row:
                return False
            if row["verification_code"] != code:
                return False
            from datetime import datetime
            if row["verification_expires"] and row["verification_expires"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
                return False
            await conn.execute(
                "UPDATE users SET is_verified = TRUE, verification_code = NULL, verification_expires = NULL WHERE email = $1",
                email,
            )
        return True
    except Exception as e:
        print(f"[DB] Error verifying user: {e}")
        return False


async def get_or_create_google_user(google_id: str, email: str, full_name: str, avatar_url: str = None) -> Optional[Dict]:
    """Find user by google_id, or create a new verified user. Returns user dict."""
    if not db_pool:
        return None
    try:
        async with db_pool.acquire() as conn:
            # Check if user exists by google_id
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE google_id = $1", google_id
            )
            if row:
                return dict(row)
            # Check if email exists (user registered with email, now linking Google)
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE email = $1", email
            )
            if row:
                # Link Google ID to existing account and verify
                await conn.execute(
                    "UPDATE users SET google_id = $1, is_verified = TRUE, provider = 'google', avatar_url = COALESCE($2, avatar_url) WHERE email = $3",
                    google_id, avatar_url, email,
                )
                updated = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
                return dict(updated) if updated else None
            # Create new Google user (auto-verified, no password)
            row = await conn.fetchrow(
                """
                INSERT INTO users (email, full_name, hashed_pw, provider, google_id, is_verified, avatar_url)
                VALUES ($1, $2, '', 'google', $3, TRUE, $4)
                RETURNING id, email, full_name, provider, avatar_url, is_active, is_verified, created_at
                """,
                email, full_name, google_id, avatar_url,
            )
            return dict(row) if row else None
    except Exception as e:
        print(f"[DB] Error with Google user: {e}")
        return None


# ─── Chat Session Operations ──────────────────────────────────────────────────

async def create_chat_session(user_id: int, title: str = "New Chat") -> Optional[Dict]:
    """Create a new chat session for a user."""
    if not db_pool:
        return None
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO chat_sessions (user_id, title)
                VALUES ($1, $2)
                RETURNING id, user_id, title, created_at, updated_at
                """,
                user_id, title,
            )
            return dict(row) if row else None
    except Exception as e:
        print(f"[DB] Error creating chat session: {e}")
        return None


async def get_user_sessions(user_id: int, limit: int = 50) -> List[Dict]:
    """Get all chat sessions for a user, most recent first."""
    if not db_pool:
        return []
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT s.id, s.title, s.created_at, s.updated_at,
                       (SELECT COUNT(*) FROM chat_messages WHERE session_id = s.id) as message_count
                FROM chat_sessions s
                WHERE s.user_id = $1
                ORDER BY s.updated_at DESC
                LIMIT $2
                """,
                user_id, limit,
            )
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"[DB] Error getting user sessions: {e}")
        return []


async def get_session_messages(session_id: int, user_id: int) -> List[Dict]:
    """Get all messages for a session (verifies ownership via user_id)."""
    if not db_pool:
        return []
    try:
        async with db_pool.acquire() as conn:
            # Verify session belongs to user
            owner = await conn.fetchval(
                "SELECT user_id FROM chat_sessions WHERE id = $1", session_id
            )
            if owner != user_id:
                return []

            rows = await conn.fetch(
                """
                SELECT id, role, content, mode, confidence, citations, created_at
                FROM chat_messages
                WHERE session_id = $1
                ORDER BY created_at ASC
                """,
                session_id,
            )
            result = []
            for row in rows:
                d = dict(row)
                # Parse citations JSONB
                if isinstance(d.get("citations"), str):
                    d["citations"] = json.loads(d["citations"])
                result.append(d)
            return result
    except Exception as e:
        print(f"[DB] Error getting session messages: {e}")
        return []


async def save_chat_message(
    session_id: int,
    role: str,
    content: str,
    mode: Optional[str] = None,
    confidence: Optional[float] = None,
    citations: Optional[List[Dict]] = None,
) -> Optional[Dict]:
    """Save a chat message and update session's updated_at."""
    if not db_pool:
        return None
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO chat_messages (session_id, role, content, mode, confidence, citations)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, session_id, role, content, mode, confidence, citations, created_at
                """,
                session_id, role, content, mode, confidence,
                json.dumps(citations) if citations else "[]",
            )
            # Update session timestamp
            await conn.execute(
                "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = $1",
                session_id,
            )
            return dict(row) if row else None
    except Exception as e:
        print(f"[DB] Error saving chat message: {e}")
        return None


async def delete_chat_session(session_id: int, user_id: int) -> bool:
    """Delete a chat session (verifies ownership)."""
    if not db_pool:
        return False
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM chat_sessions WHERE id = $1 AND user_id = $2",
                session_id, user_id,
            )
            return "DELETE 1" in result
    except Exception as e:
        print(f"[DB] Error deleting chat session: {e}")
        return False


async def update_session_title(session_id: int, user_id: int, title: str) -> bool:
    """Update session title (verifies ownership)."""
    if not db_pool:
        return False
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE chat_sessions SET title = $1 WHERE id = $2 AND user_id = $3",
                title, session_id, user_id,
            )
            return "UPDATE 1" in result
    except Exception as e:
        print(f"[DB] Error updating session title: {e}")
        return False


# ─── Session-Document Linking ─────────────────────────────────────────────────

async def link_doc_to_session(session_id: int, doc_id: str) -> bool:
    """Link a document to a chat session."""
    if not db_pool:
        return False
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO session_documents (session_id, doc_id)
                VALUES ($1, $2)
                ON CONFLICT (session_id, doc_id) DO NOTHING
                """,
                session_id, doc_id,
            )
        return True
    except Exception as e:
        print(f"[DB] Error linking doc to session: {e}")
        return False


async def get_session_doc_ids(session_id: int) -> List[str]:
    """Get all doc_ids linked to a chat session."""
    if not db_pool:
        return []
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT doc_id FROM session_documents WHERE session_id = $1",
                session_id,
            )
            return [row["doc_id"] for row in rows]
    except Exception as e:
        print(f"[DB] Error getting session docs: {e}")
        return []


# ─── Per-User Progress ─────────────────────────────────────────────────────────

async def get_user_progress(user_id: int) -> Dict[str, Any]:
    """Compute per-user learning progress from queries + chat activity."""
    if not db_pool:
        return {}

    try:
        async with db_pool.acquire() as conn:
            progress: Dict[str, Any] = {}

            # ── Total questions asked by this user
            progress["total_questions"] = await conn.fetchval(
                "SELECT COUNT(*) FROM queries WHERE user_id = $1", user_id
            ) or 0

            # ── Average confidence
            progress["avg_confidence"] = float(
                await conn.fetchval(
                    "SELECT COALESCE(AVG(confidence), 0) FROM queries WHERE user_id = $1 AND confidence > 0",
                    user_id,
                ) or 0
            )

            # ── Documents uploaded (via sessions owned by user)
            progress["documents_uploaded"] = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT sd.doc_id)
                FROM session_documents sd
                JOIN chat_sessions cs ON cs.id = sd.session_id
                WHERE cs.user_id = $1
                """,
                user_id,
            ) or 0

            # ── Study streak (consecutive days with activity)
            streak_rows = await conn.fetch(
                """
                SELECT DISTINCT DATE(cm.created_at) as day
                FROM chat_messages cm
                JOIN chat_sessions cs ON cs.id = cm.session_id
                WHERE cs.user_id = $1 AND cm.role = 'user'
                ORDER BY DATE(cm.created_at) DESC
                """,
                user_id,
            )
            streak = 0
            if streak_rows:
                from datetime import date, timedelta
                today = date.today()
                expected = today
                for row in streak_rows:
                    d = row["day"]
                    if isinstance(d, datetime):
                        d = d.date()
                    if d == expected:
                        streak += 1
                        expected -= timedelta(days=1)
                    elif d == expected - timedelta(days=1):
                        # Allow gap of 1 day (user might check at different times)
                        expected = d
                        streak += 1
                        expected -= timedelta(days=1)
                    else:
                        break
            progress["study_streak"] = streak

            # ── Study time estimation (sum of per-session time, capped at 30min each)
            session_times = await conn.fetch(
                """
                SELECT cm.session_id,
                       EXTRACT(EPOCH FROM (MAX(cm.created_at) - MIN(cm.created_at))) / 60.0 as dur_min
                FROM chat_messages cm
                JOIN chat_sessions cs ON cs.id = cm.session_id
                WHERE cs.user_id = $1
                GROUP BY cm.session_id
                HAVING COUNT(*) > 1
                """,
                user_id,
            )
            total_min = sum(min(float(r["dur_min"] or 0), 30.0) for r in session_times)
            progress["total_study_time_min"] = round(total_min)

            # ── Topics mastery (from query_type + query_text keywords)
            topic_rows = await conn.fetch(
                """
                SELECT query_type,
                       COUNT(*) as question_count,
                       COALESCE(AVG(confidence), 0) as avg_conf
                FROM queries
                WHERE user_id = $1 AND query_type IS NOT NULL
                GROUP BY query_type
                ORDER BY question_count DESC
                LIMIT 8
                """,
                user_id,
            )
            topics = []
            for r in topic_rows:
                avg_c = float(r["avg_conf"] or 0)
                topics.append({
                    "name": _format_topic_name(r["query_type"]),
                    "question_count": r["question_count"],
                    "avg_confidence": round(avg_c, 4),
                    "progress": round(min(avg_c * 100, 100)),
                    "color": "green" if avg_c >= 0.75 else ("yellow" if avg_c >= 0.5 else "red"),
                })
            progress["topics"] = topics

            # ── Weekly activity (last 7 days of questions)
            weekly = await conn.fetch(
                """
                SELECT DATE(created_at) as day, COUNT(*) as questions
                FROM queries
                WHERE user_id = $1
                  AND created_at >= CURRENT_DATE - INTERVAL '6 days'
                GROUP BY DATE(created_at)
                ORDER BY day
                """,
                user_id,
            )
            from datetime import date, timedelta
            weekly_map = {}
            for r in weekly:
                d = r["day"]
                if isinstance(d, datetime):
                    d = d.date()
                weekly_map[d] = r["questions"]

            today = date.today()
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            weekly_activity = []
            for i in range(6, -1, -1):
                d = today - timedelta(days=i)
                weekly_activity.append({
                    "day": day_names[d.weekday()],
                    "date": d.isoformat(),
                    "questions": weekly_map.get(d, 0),
                })
            progress["weekly_activity"] = weekly_activity

            # ── Recommendations (AI-like suggestions based on data)
            recs = []
            # Low-confidence topics
            for t in topics:
                if t["avg_confidence"] < 0.5:
                    recs.append({
                        "type": "review",
                        "message": f"Review {t['name']} — confidence is low ({t['progress']}%)",
                        "priority": "high",
                    })
            # Streak encouragement
            if streak > 0:
                recs.append({
                    "type": "streak",
                    "message": f"Study today to maintain your {streak}-day streak 🔥",
                    "priority": "medium",
                })
            elif progress["total_questions"] > 0:
                recs.append({
                    "type": "streak",
                    "message": "Start a new study streak today! Consistency is key 📚",
                    "priority": "medium",
                })
            # High-confidence celebration
            for t in topics:
                if t["avg_confidence"] >= 0.85:
                    recs.append({
                        "type": "continue",
                        "message": f"Great progress on {t['name']}! 🎉",
                        "priority": "low",
                    })
            if not recs:
                recs.append({
                    "type": "continue",
                    "message": "Upload a PDF and start asking questions to track your progress!",
                    "priority": "low",
                })
            progress["recommendations"] = recs[:5]  # cap at 5

            # ── Reflection rate
            progress["reflection_rate"] = float(
                await conn.fetchval(
                    "SELECT COALESCE(AVG(CASE WHEN reflection_validated THEN 1.0 ELSE 0.0 END), 0) FROM queries WHERE user_id = $1",
                    user_id,
                ) or 0
            )

            return progress

    except Exception as e:
        print(f"[DB] Error getting user progress: {e}")
        import traceback; traceback.print_exc()
        return {}


def _format_topic_name(query_type: str) -> str:
    """Format query_type enum into a readable topic name."""
    name_map = {
        "factual": "Factual Recall",
        "conceptual": "Conceptual Understanding",
        "comparison": "Comparative Analysis",
        "summarization": "Summarization",
        "listing": "List & Enumeration",
        "general": "General Questions",
        "document_study": "Document Study",
        "chat": "Conversational",
        "fast": "Quick Answers",
    }
    return name_map.get(query_type, query_type.replace("_", " ").title())


# ─── Study Materials ──────────────────────────────────────────────────────────

async def get_user_study_materials(user_id: int) -> Dict[str, Any]:
    """Build study materials (flashcards, documents, notes) from user's Q&A history."""
    if not db_pool:
        return {"flashcards": [], "documents": [], "notes": [], "stats": {}}

    try:
        async with db_pool.acquire() as conn:
            # ── Flashcards: auto-generate from high-quality Q&A pairs
            qa_rows = await conn.fetch(
                """
                SELECT query_text, answer, confidence, query_type, created_at
                FROM queries
                WHERE user_id = $1
                  AND confidence > 0.3
                  AND query_type NOT IN ('chat')
                  AND LENGTH(answer) > 20
                ORDER BY confidence DESC, created_at DESC
                LIMIT 50
                """,
                user_id,
            )
            flashcards = []
            for r in qa_rows:
                # Truncate answer for flashcard format (first 300 chars)
                answer_text = r["answer"]
                if len(answer_text) > 300:
                    # Find a sentence boundary near 300 chars
                    cut = answer_text[:300].rfind(".")
                    if cut > 100:
                        answer_text = answer_text[:cut + 1]
                    else:
                        answer_text = answer_text[:300] + "…"

                flashcards.append({
                    "question": r["query_text"],
                    "answer": answer_text,
                    "source": r["query_type"] or "general",
                    "confidence": round(float(r["confidence"] or 0), 4),
                    "topic": _format_topic_name(r["query_type"] or "general"),
                })

            # ── Documents: from user's sessions
            doc_rows = await conn.fetch(
                """
                SELECT DISTINCT d.doc_id, d.filename, d.page_count,
                       json_array_length(d.chunks::json) as chunk_count,
                       d.uploaded_at,
                       cs.title as session_title
                FROM documents d
                JOIN session_documents sd ON sd.doc_id = d.doc_id
                JOIN chat_sessions cs ON cs.id = sd.session_id
                WHERE cs.user_id = $1
                ORDER BY d.uploaded_at DESC
                """,
                user_id,
            )
            documents = []
            for r in doc_rows:
                documents.append({
                    "doc_id": r["doc_id"],
                    "filename": r["filename"],
                    "page_count": r["page_count"],
                    "chunk_count": r["chunk_count"] or 0,
                    "uploaded_at": str(r["uploaded_at"]),
                    "session_title": r["session_title"],
                })

            # ── Study Notes: recent Q&A with good answers
            note_rows = await conn.fetch(
                """
                SELECT id, query_text, answer, confidence, query_type, created_at
                FROM queries
                WHERE user_id = $1
                  AND query_type NOT IN ('chat')
                  AND LENGTH(answer) > 50
                ORDER BY created_at DESC
                LIMIT 20
                """,
                user_id,
            )
            notes = []
            for r in note_rows:
                notes.append({
                    "query": r["query_text"],
                    "answer": r["answer"],
                    "confidence": round(float(r["confidence"] or 0), 4),
                    "query_type": _format_topic_name(r["query_type"] or "general"),
                    "created_at": str(r["created_at"]),
                })

            # ── Stats
            total_flashcards = len(flashcards)
            total_docs = len(documents)
            total_notes = len(notes)
            avg_conf = (
                sum(f["confidence"] for f in flashcards) / total_flashcards
                if total_flashcards > 0 else 0.0
            )

            stats = {
                "total_flashcards": total_flashcards,
                "total_documents": total_docs,
                "total_notes": total_notes,
                "avg_confidence": round(avg_conf, 4),
            }

            return {
                "flashcards": flashcards,
                "documents": documents,
                "notes": notes,
                "stats": stats,
            }

    except Exception as e:
        print(f"[DB] Error getting study materials: {e}")
        import traceback; traceback.print_exc()
        return {"flashcards": [], "documents": [], "notes": [], "stats": {}}


# ─── Dynamic Topic Suggestions ────────────────────────────────────────────────

async def get_user_topics(user_id: int) -> List[Dict[str, Any]]:
    """Extract topic suggestions from user's activity: query keywords, document names, chat titles."""
    if not db_pool:
        return []

    try:
        async with db_pool.acquire() as conn:
            topics: List[Dict[str, Any]] = []
            seen = set()

            # 1. Topics from queries (most asked query types)
            type_rows = await conn.fetch(
                """
                SELECT query_type, COUNT(*) as cnt
                FROM queries
                WHERE user_id = $1 AND query_type IS NOT NULL AND query_type NOT IN ('chat', 'greeting')
                GROUP BY query_type
                ORDER BY cnt DESC
                LIMIT 5
                """,
                user_id,
            )
            for r in type_rows:
                name = _format_topic_name(r["query_type"])
                if name.lower() not in seen:
                    seen.add(name.lower())
                    topics.append({"name": name, "source": "your_queries", "count": r["cnt"]})

            # 2. Topics from uploaded document filenames
            doc_rows = await conn.fetch(
                """
                SELECT DISTINCT d.filename
                FROM documents d
                JOIN session_documents sd ON sd.doc_id = d.doc_id
                JOIN chat_sessions cs ON cs.id = sd.session_id
                WHERE cs.user_id = $1
                ORDER BY d.uploaded_at DESC
                LIMIT 5
                """,
                user_id,
            )
            for r in doc_rows:
                # Extract topic from filename (remove extension, underscores, etc.)
                raw = r["filename"]
                name = raw.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
                if len(name) > 3 and name.lower() not in seen:
                    seen.add(name.lower())
                    topics.append({"name": name.title(), "source": "your_documents", "count": 0})

            # 3. Topics from chat session titles
            session_rows = await conn.fetch(
                """
                SELECT DISTINCT title
                FROM chat_sessions
                WHERE user_id = $1 AND title IS NOT NULL AND title != 'New Chat'
                ORDER BY updated_at DESC
                LIMIT 5
                """,
                user_id,
            )
            for r in session_rows:
                name = r["title"].strip()
                if len(name) > 3 and name.lower() not in seen:
                    seen.add(name.lower())
                    topics.append({"name": name, "source": "your_chats", "count": 0})

            # 4. Extract keywords from recent queries (most frequent meaningful words)
            keyword_rows = await conn.fetch(
                """
                SELECT query_text FROM queries
                WHERE user_id = $1 AND LENGTH(query_text) > 10
                ORDER BY created_at DESC LIMIT 30
                """,
                user_id,
            )
            stop_words = {
                "what", "how", "why", "when", "where", "which", "who", "does", "the",
                "is", "are", "was", "were", "can", "could", "would", "should", "will",
                "this", "that", "these", "those", "from", "with", "about", "into",
                "for", "and", "but", "not", "have", "has", "had", "been", "being",
                "its", "it", "they", "their", "them", "you", "your", "our", "more",
                "some", "any", "all", "each", "every", "most", "other", "own", "same",
                "than", "too", "very", "just", "also", "between", "after", "before",
                "during", "explain", "tell", "give", "make", "know", "help", "please",
                "pdf", "document", "page", "file", "study", "exam",
            }
            word_freq: Dict[str, int] = {}
            for r in keyword_rows:
                words = r["query_text"].lower().split()
                for w in words:
                    w = w.strip("?.,!\"'()[]{}:;")
                    if len(w) > 3 and w not in stop_words and not w.isdigit():
                        word_freq[w] = word_freq.get(w, 0) + 1

            # Take most frequent keywords as topic suggestions
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            for word, count in sorted_words[:6]:
                if word.lower() not in seen and count >= 2:
                    seen.add(word.lower())
                    topics.append({"name": word.title(), "source": "frequent_keywords", "count": count})

            return topics[:12]  # cap at 12 suggestions

    except Exception as e:
        print(f"[DB] Error getting user topics: {e}")
        return []
