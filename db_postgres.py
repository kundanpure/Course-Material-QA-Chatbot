"""
PostgreSQL Database Integration for Production Agentic Backend
Adds persistent storage for documents, queries, and feedback
"""
import asyncpg
import json
from typing import List, Dict, Optional, Any
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Database connection pool
db_pool: Optional[asyncpg.Pool] = None

# PostgreSQL Schema
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(50) UNIQUE NOT NULL,
    filename VARCHAR(255) NOT NULL,
    text_content TEXT NOT NULL,
    chunks JSONB NOT NULL,
    page_count INTEGER NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS queries (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_type VARCHAR(50),
    retrieval_strategy VARCHAR(50),
    answer TEXT,
    citations JSONB,
    confidence FLOAT,
    chunks_retrieved INTEGER,
    chunks_used INTEGER,
    tokens_used INTEGER,
    retrieval_time_ms FLOAT,
    generation_time_ms FLOAT,
    total_time_ms FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    query_id INTEGER REFERENCES queries(id),
    helpful BOOLEAN NOT NULL,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_doc_id ON documents(doc_id);
CREATE INDEX IF NOT EXISTS idx_queries_created_at ON queries(created_at DESC);
"""

async def init_db():
    """Initialize database connection pool and create tables"""
    global db_pool
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("[DB] Warning: DATABASE_URL not found, skipping database init")
        return False
    
    try:
        # Create connection pool
        db_pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        
        # Create tables
        async with db_pool.acquire() as conn:
            await conn.execute(CREATE_TABLES_SQL)
        
        print("[DB] ✅ PostgreSQL connected and tables initialized")
        return True
        
    except Exception as e:
        print(f"[DB] ❌ Failed to initialize database: {e}")
        db_pool = None
        return False

async def close_db():
    """Close database connection pool"""
    global db_pool
    if db_pool:
        await db_pool.close()
        print("[DB] Connection closed")

# Document Operations
async def save_document(doc_id: str, filename: str, text: str, chunks: List[Dict], page_count: int) -> bool:
    """Save document to database"""
    if not db_pool:
        return False
    
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO documents (doc_id, filename, text_content, chunks, page_count)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (doc_id) DO UPDATE 
                SET filename = $2, text_content = $3, chunks = $4, page_count = $5
                """,
                doc_id, filename, text, json.dumps(chunks), page_count
            )
        return True
    except Exception as e:
        print(f"[DB] Error saving document: {e}")
        return False

async def get_all_documents() -> Dict[str, Dict]:
    """Load all documents from database"""
    if not db_pool:
        return {}
    
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM documents ORDER BY uploaded_at DESC")
            
            documents = {}
            for row in rows:
                documents[row['doc_id']] = {
                    "filename": row['filename'],
                    "text": row['text_content'],
                    "chunks": json.loads(row['chunks']),
                    "page_count": row['page_count'],
                    "uploaded_at": row['uploaded_at'].timestamp()
                }
            
            return documents
            
    except Exception as e:
        print(f"[DB] Error loading documents: {e}")
        return {}

async def delete_document(doc_id: str) -> bool:
    """Delete document from database"""
    if not db_pool:
        return False
    
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM documents WHERE doc_id = $1", doc_id)
        return True
    except Exception as e:
        print(f"[DB] Error deleting document: {e}")
        return False

# Query Operations
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
    total_time_ms: float
) -> Optional[int]:
    """Save query to database and return query ID"""
    if not db_pool:
        return None
    
    try:
        async with db_pool.acquire() as conn:
            query_id = await conn.fetchval(
                """
                INSERT INTO queries (
                    query_text, query_type, retrieval_strategy, answer, citations,
                    confidence, chunks_retrieved, chunks_used, tokens_used,
                    retrieval_time_ms, generation_time_ms, total_time_ms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id
                """,
                query_text, query_type, strategy, answer, json.dumps(citations),
                confidence, chunks_retrieved, chunks_used, tokens_used,
                retrieval_time_ms, generation_time_ms, total_time_ms
            )
        return query_id
    except Exception as e:
        print(f"[DB] Error saving query: {e}")
        return None

async def get_query_history(limit: int = 50) -> List[Dict]:
    """Get recent query history"""
    if not db_pool:
        return []
    
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, query_text, query_type, answer, confidence, created_at
                FROM queries
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit
            )
            
            return [dict(row) for row in rows]
            
    except Exception as e:
        print(f"[DB] Error loading query history: {e}")
        return []

# Feedback Operations
async def save_feedback(query_id: int, helpful: bool, comment: Optional[str] = None) -> bool:
    """Save user feedback"""
    if not db_pool:
        return False
    
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO feedback (query_id, helpful, comment) VALUES ($1, $2, $3)",
                query_id, helpful, comment
            )
        return True
    except Exception as e:
        print(f"[DB] Error saving feedback: {e}")
        return False

# Analytics
async def get_analytics() -> Dict[str, Any]:
    """Get usage analytics"""
    if not db_pool:
        return {}
    
    try:
        async with db_pool.acquire() as conn:
            stats = {}
            
            # Total queries
            stats['total_queries'] = await conn.fetchval("SELECT COUNT(*) FROM queries")
            
            # Average confidence
            stats['avg_confidence'] = await conn.fetchval(
                "SELECT AVG(confidence) FROM queries WHERE confidence > 0"
            ) or 0.0
            
            # Total documents
            stats['total_documents'] = await conn.fetchval("SELECT COUNT(*) FROM documents")
            
            # Query types distribution
            type_dist = await conn.fetch(
                "SELECT query_type, COUNT(*) as count FROM queries GROUP BY query_type"
            )
            stats['query_types'] = {row['query_type']: row['count'] for row in type_dist}
            
            return stats
            
    except Exception as e:
        print(f"[DB] Error getting analytics: {e}")
        return {}
