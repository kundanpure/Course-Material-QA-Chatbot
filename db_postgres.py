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
from datetime import datetime
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

CREATE INDEX IF NOT EXISTS idx_documents_doc_id   ON documents(doc_id);
CREATE INDEX IF NOT EXISTS idx_queries_created_at ON queries(created_at DESC);
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
                    language_detected, original_query, rewritten_query
                ) VALUES (
                    $1,  $2,  $3,  $4,  $5,
                    $6,  $7,  $8,  $9,
                    $10, $11, $12,
                    $13, $14, $15,
                    $16, $17, $18
                )
                RETURNING id
                """,
                query_text, query_type, strategy, answer, json.dumps(citations),
                confidence, chunks_retrieved, chunks_used, tokens_used,
                retrieval_time_ms, generation_time_ms, total_time_ms,
                mmr_diversity_score, avg_retrieval_score, reflection_validated,
                language_detected, original_query, rewritten_query,
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
