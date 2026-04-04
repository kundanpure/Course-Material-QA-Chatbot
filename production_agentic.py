"""
Production Agentic RAG Server — v4.0.0
Hybrid Semantic Agentic RAG: FAISS + BM25 + MMR + Query Rewriting +
Structured Context + Reflection Validation + Advanced Confidence Scoring +
Multilingual Support
"""

# ─── Standard Library ──────────────────────────────────────────────────────────
import os
import re
import time
import math
import hashlib
import tempfile
import asyncio
import pickle
from collections import defaultdict
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

# ─── Third-party ───────────────────────────────────────────────────────────────
import numpy as np
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
from pypdf import PdfReader

# Embeddings
from fastembed import TextEmbedding

# FAISS Vector Index
import faiss

# BM25 Lexical Index
from rank_bm25 import BM25Okapi

# Language detection + translation
from langdetect import detect as lang_detect, LangDetectException
from deep_translator import GoogleTranslator

# NeonDB persistence layer
import db_postgres as db

# Auth + Chat History + Progress + Study Materials routes
from routes_auth import router as auth_router
from routes_chat_history import router as chat_history_router
from routes_evaluation import router as evaluation_router
from routes_progress import router as progress_router
from routes_study_materials import router as study_materials_router
from auth import get_optional_user
from llm_provider import llm_generate, get_provider_info

# ─── Environment ───────────────────────────────────────────────────────────────
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ─── Embedding Service (singleton) ────────────────────────────────────────────

class EmbeddingService:
    """Loads fastembed model once; thread-safe embedding generation."""

    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    _instance: Optional["EmbeddingService"] = None

    def __init__(self):
        print(f"[EMBED] Loading model '{self.MODEL_NAME}' in fastembed (no PyTorch)…")
        # fastembed uses ONNX runtime, greatly saving memory
        self._model = TextEmbedding(model_name=self.MODEL_NAME)
        self._dim   = 384  # fixed dimension for all-MiniLM-L6-v2
        print(f"[EMBED] [OK] Model ready — dim={self._dim}")

    @classmethod
    def get(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def dim(self) -> int:
        return self._dim

    def encode(self, texts: List[str]) -> np.ndarray:
        """Return float32 L2-normalised embedding matrix."""
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)
        # fastembed returns a generator of numpy arrays
        vecs_list = list(self._model.embed(texts))
        if not vecs_list:
            return np.empty((0, self._dim), dtype=np.float32)
        vecs = np.vstack(vecs_list)
        faiss.normalize_L2(vecs.astype(np.float32))
        return vecs.astype(np.float32)

    def encode_one(self, text: str) -> np.ndarray:
        return self.encode([text])[0]

# ─── Pydantic Models ──────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str

class QueryRequest(BaseModel):
    query: str
    conversation_history: Optional[List[Message]] = []
    options: Optional[dict] = {}
    mode: str = "auto"  # "auto" | "fast" | "study" | "research" | "chat"
    session_id: Optional[int] = None  # chat session for history persistence
    doc_ids: Optional[List[str]] = None  # restrict retrieval to these docs only

class Citation(BaseModel):
    text: str
    source: str
    page: Optional[int] = None
    section: Optional[str] = None
    confidence: float

class QueryMetadata(BaseModel):
    query_type:           Optional[str] = "rag"
    retrieval_strategy:   str           = "hybrid_semantic"
    pipeline_mode:        str           = "auto"
    chunks_retrieved:     int           = 0
    chunks_used:          int           = 0
    attempts:             int           = 1
    tokens_used:          int           = 0
    retrieval_time_ms:    float         = 0
    generation_time_ms:   float         = 0
    total_time_ms:        float         = 0
    avg_retrieval_score:  float         = 0.0
    mmr_diversity_score:  float         = 0.0
    reflection_validated: bool          = False
    language_detected:    str           = "en"
    original_query:       str           = ""
    rewritten_query:      str           = ""

class QueryResponse(BaseModel):
    answer:    str
    citations: List[Citation]
    confidence: float
    metadata:  QueryMetadata
    cached:    bool = False


# ─── Global State ─────────────────────────────────────────────────────────────

documents_store: Dict[str, Dict] = {}   # doc_id → {filename, text, chunks, embeddings, page_count}
faiss_indexes:   Dict[str, faiss.IndexFlatIP] = {}  # doc_id → FAISS index
bm25_indexes:    Dict[str, BM25Okapi]          = {}  # doc_id → BM25 index
chunk_lookup:    Dict[str, List[Dict]]         = {}  # doc_id → ordered chunk list (mirrors FAISS order)
session_doc_map: Dict[int, set]               = {}  # session_id → set of doc_ids (in-memory)

# ─── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Production Agentic RAG Backend",
    description=(
        "v4.0.0 — Hybrid Semantic Agentic RAG: "
        "FAISS + BM25 + MMR + Query Rewriting + Reflection Validation"
    ),
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Register Auth + Chat History + Progress Routers ──────────────────────────

app.include_router(auth_router)
app.include_router(chat_history_router)
app.include_router(evaluation_router)
app.include_router(progress_router)
app.include_router(study_materials_router)

# ─── Startup / Shutdown ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Boot: warm embedding model, connect NeonDB, rebuild indexes from stored data."""
    global documents_store

    # 1. Warm up embedding model
    embed = EmbeddingService.get()
    print(f"[STARTUP] [OK] Embedding service ready (dim={embed.dim})")

    # 2. Connect NeonDB
    db_available = await db.init_db()

    if db_available:
        documents_store = await db.get_all_documents()
        print(f"[STARTUP] [OK] Loaded {len(documents_store)} documents from NeonDB")
        # 3. Rebuild in-memory indexes
        for doc_id, doc_data in documents_store.items():
            _build_indexes(doc_id, doc_data)
        print(f"[STARTUP] [OK] Rebuilt FAISS + BM25 indexes for {len(documents_store)} documents")
    else:
        print("[STARTUP] [WARN] NeonDB not available — using in-memory storage only")


@app.on_event("shutdown")
async def shutdown_event():
    await db.close_db()

# ─── Layer 1: Hierarchical + Metadata-Aware Chunking ─────────────────────────

def extract_text_from_pdf(pdf_path: str) -> Tuple[str, int, List[Dict]]:
    """
    Extract text page-by-page and return:
    - full concatenated text
    - page count
    - list of page-level dicts {page_num, text}
    """
    reader = PdfReader(pdf_path)
    pages = []
    full_text = ""
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        pages.append({"page_num": i + 1, "text": page_text})
        full_text += f"\n\n--- Page {i + 1} ---\n\n{page_text}"
    return full_text, len(reader.pages), pages


def _detect_section(text: str) -> str:
    """Heuristic: first line that looks like a heading."""
    lines = text.strip().split("\n")
    for line in lines[:5]:
        stripped = line.strip()
        if stripped and len(stripped) < 100 and not stripped.endswith("."):
            return stripped
    return "Content"


def chunk_text_hierarchical(pages: List[Dict], doc_id: str,
                             chunk_size: int = 800, overlap: int = 150) -> List[Dict]:
    """
    Splits text page-by-page first, then into word-windowed chunks.
    Preserves: doc_id, page_num, section, start_pos, end_pos.
    """
    chunks: List[Dict] = []
    chunk_idx = 0

    for page_data in pages:
        page_num  = page_data["page_num"]
        page_text = page_data["text"].strip()
        if not page_text:
            continue

        words = page_text.split()
        step  = max(1, chunk_size - overlap)

        for i in range(0, len(words), step):
            chunk_words = words[i : i + chunk_size]
            if not chunk_words:
                continue
            chunk_text_str = " ".join(chunk_words)
            section = _detect_section(chunk_text_str)
            chunks.append({
                "id":        f"{doc_id}_chunk_{chunk_idx}",
                "text":      chunk_text_str,
                "page_num":  page_num,
                "section":   section,
                "doc_id":    doc_id,
                "start_pos": i,
                "end_pos":   i + len(chunk_words),
            })
            chunk_idx += 1

    return chunks

# ─── Layer 2 + 3: FAISS + Embedding Indexing ──────────────────────────────────

def _backfill_chunk_fields(chunks: List[Dict], doc_id: str) -> List[Dict]:
    """
    Backfill v4 fields ('id', 'page_num', 'section', 'doc_id') onto old-format
    chunks that were stored before the v4 upgrade. Safe to call on already-
    upgraded chunks — existing values are preserved.
    """
    for i, chunk in enumerate(chunks):
        if "id" not in chunk:
            chunk["id"] = f"{doc_id}_chunk_{i}"
        if "page_num" not in chunk:
            chunk["page_num"] = None
        if "section" not in chunk:
            chunk["section"] = _detect_section(chunk.get("text", ""))
        if "doc_id" not in chunk:
            chunk["doc_id"] = doc_id
    return chunks


def _build_indexes(doc_id: str, doc_data: Dict):
    """
    (Re)build FAISS + BM25 for a single document.
    Called on startup (from DB data) and after new upload.
    Handles both v3 (legacy) and v4 chunk formats.
    """
    chunks = doc_data.get("chunks", [])
    if not chunks:
        return

    # Backfill any missing v4 fields on old-format chunks
    chunks = _backfill_chunk_fields(chunks, doc_id)
    doc_data["chunks"] = chunks  # update in-place so documents_store reflects this

    embed = EmbeddingService.get()
    texts = [c["text"] for c in chunks]

    # --- FAISS ---
    existing_embeddings = doc_data.get("embeddings")
    if isinstance(existing_embeddings, np.ndarray) and len(existing_embeddings) == len(texts):
        vecs = existing_embeddings.astype(np.float32)
        faiss.normalize_L2(vecs)
    else:
        vecs = embed.encode(texts)

    index = faiss.IndexFlatIP(embed.dim)  # inner-product on L2-normalized = cosine
    index.add(vecs)
    faiss_indexes[doc_id] = index
    chunk_lookup[doc_id]  = chunks

    # --- BM25 ---
    tokenized = [t.lower().split() for t in texts]
    bm25_indexes[doc_id] = BM25Okapi(tokenized)

    print(f"[INDEX] [OK] {doc_id}: FAISS {len(texts)} vecs, BM25 ready")

# ─── Layer 4: Hybrid Retrieval (Semantic + Lexical) ───────────────────────────

def _semantic_scores(query_vec: np.ndarray, doc_id: str, k: int) -> Dict[int, float]:
    """Return {chunk_idx → cosine_score} for top-k from FAISS."""
    index = faiss_indexes.get(doc_id)
    if index is None or index.ntotal == 0:
        return {}
    k = min(k, index.ntotal)
    scores, indices = index.search(query_vec.reshape(1, -1), k)
    return {int(idx): float(score) for idx, score in zip(indices[0], scores[0]) if idx >= 0}


def _bm25_scores(query_tokens: List[str], doc_id: str) -> Dict[int, float]:
    """Return {chunk_idx → BM25_score} for all chunks."""
    bm25 = bm25_indexes.get(doc_id)
    if bm25 is None:
        return {}
    raw = bm25.get_scores(query_tokens)
    max_score = float(max(raw)) if max(raw) > 0 else 1.0
    return {i: float(s) / max_score for i, s in enumerate(raw)}


def hybrid_retrieve(query: str, top_k: int = 10, doc_ids: Optional[List[str]] = None) -> List[Dict]:
    """
    Dual retrieval:
      final_score = 0.6 * semantic + 0.4 * bm25 (normalised)
    Returns merged chunk list sorted by final_score, with source info attached.
    If doc_ids is given, only those documents are searched.
    """
    embed        = EmbeddingService.get()
    query_vec    = embed.encode_one(query)
    query_tokens = query.lower().split()

    fused: Dict[str, Dict] = {}  # key = chunk["id"]

    docs_to_search = {did: documents_store[did] for did in (doc_ids or documents_store.keys()) if did in documents_store}

    for doc_id, doc_data in docs_to_search.items():
        sem_scores = _semantic_scores(query_vec, doc_id, k=top_k * 2)
        lex_scores = _bm25_scores(query_tokens, doc_id)
        chunks     = chunk_lookup.get(doc_id, doc_data.get("chunks", []))

        for idx, chunk in enumerate(chunks):
            sem = sem_scores.get(idx, 0.0)
            lex = lex_scores.get(idx, 0.0)
            final = 0.6 * sem + 0.4 * lex
            if final <= 0:
                continue
            # Use 'id' if present (v4 chunks); fall back to positional key (v3 legacy)
            key = chunk.get("id") or f"{doc_id}_chunk_{idx}"
            fused[key] = {
                **chunk,
                "id":          key,
                "source":      doc_data["filename"],
                "doc_id":      doc_id,
                "score":       final,
                "sem_score":   sem,
                "lex_score":   lex,
            }

    ranked = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]

# ─── Layer 5: MMR Diversification ─────────────────────────────────────────────

def mmr_select(
    candidates: List[Dict],
    query_vec: np.ndarray,
    top_k: int = 5,
    lambda_val: float = 0.7,
) -> Tuple[List[Dict], float]:
    """
    Maximum Marginal Relevance:
        score = λ * relevance − (1−λ) * max_similarity_to_selected
    Returns (selected_chunks, diversity_score).
    """
    if not candidates:
        return [], 0.0

    embed = EmbeddingService.get()
    texts = [c["text"] for c in candidates]
    vecs  = embed.encode(texts)          # already L2-normalised

    # Cosine with query
    rel_scores = np.dot(vecs, query_vec).tolist()

    selected_indices: List[int] = []
    remaining        = list(range(len(candidates)))

    while len(selected_indices) < top_k and remaining:
        if not selected_indices:
            # First pick: highest relevance
            best_idx = max(remaining, key=lambda i: rel_scores[i])
        else:
            selected_vecs = vecs[selected_indices]  # (k, dim)
            best_idx = None
            best_mmr = -1e9
            for i in remaining:
                rel   = rel_scores[i]
                sim   = float(np.max(np.dot(selected_vecs, vecs[i])))
                mmr   = lambda_val * rel - (1 - lambda_val) * sim
                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = i
        selected_indices.append(best_idx)
        remaining.remove(best_idx)

    selected = [candidates[i] for i in selected_indices]

    # Diversity score: 1 - avg pairwise similarity among selected
    if len(selected_indices) > 1:
        sel_vecs = vecs[selected_indices]
        sim_matrix = np.dot(sel_vecs, sel_vecs.T)
        n = len(selected_indices)
        off_diag_mask = ~np.eye(n, dtype=bool)
        avg_sim = float(np.mean(sim_matrix[off_diag_mask]))
        diversity = max(0.0, 1.0 - avg_sim)
    else:
        diversity = 1.0

    return selected, diversity

# ─── Layer 6: Query Rewriting Agent ───────────────────────────────────────────

async def query_rewrite_agent(query: str, query_type: str) -> str:
    """Use LLM to expand / clarify the user's query before retrieval."""
    prompt = f"""You are a search query optimizer for an academic AI tutor.
Rewrite the following student question into a more detailed, retrieval-friendly query.
- Expand abbreviations
- Add relevant synonyms and related concepts
- Keep it under 60 words
- Output ONLY the rewritten query — no explanation

Query type: {query_type}
Original: {query}

Rewritten query:"""

    try:
        rewritten, _ = await llm_generate(prompt)
        rewritten = rewritten.strip()
        # Safety: if LLM returns nothing useful, fall back
        if len(rewritten) < 5 or len(rewritten) > 500:
            return query
        return rewritten
    except Exception as e:
        print(f"[REWRITE] LLM error: {e} — using original query")
        return query

# ─── Layer 7: Structured Context Assembly ─────────────────────────────────────

def build_structured_context(chunks: List[Dict]) -> str:
    """
    Format retrieved chunks into a structured block that helps the LLM
    understand provenance clearly.

    Format:
    [Source 1]
    Source: <filename>
    Page: <page_num>
    Section: <section>
    Content:
    <text>
    """
    blocks = []
    for i, chunk in enumerate(chunks, 1):
        block = (
            f"[Source {i}]\n"
            f"Source: {chunk.get('source', 'Unknown')}\n"
            f"Page: {chunk.get('page_num', 'N/A')}\n"
            f"Section: {chunk.get('section', 'Content')}\n"
            f"Content:\n{chunk['text']}"
        )
        blocks.append(block)
    return "\n\n" + ("─" * 60 + "\n\n").join(blocks)

# ─── Layer 8: Reflection / Verification Agent ─────────────────────────────────

async def reflection_agent(
    query: str, answer: str, context: str
) -> Tuple[str, bool]:
    """
    Ask Gemini to verify whether the answer is fully grounded in context.
    If not, regenerate a corrected answer.

    Returns (final_answer, is_validated).
    """
    reflection_prompt = f"""You are a strict academic fact-checker.

Context provided to the AI tutor:
{context}

Student question:
{query}

AI-generated answer:
{answer}

Task:
1. Determine if EVERY claim in the answer is supported by the context above.
2. If YES — respond with exactly: VALIDATED
3. If NO — respond with: CORRECTED\n<corrected answer here>

Only use information from the provided context. Do not add outside knowledge."""

    try:
        reflection_text, _ = await llm_generate(reflection_prompt)
        reflection_text = reflection_text.strip()

        if reflection_text.upper().startswith("VALIDATED"):
            return answer, True
        elif reflection_text.upper().startswith("CORRECTED"):
            corrected = reflection_text[len("CORRECTED"):].strip().lstrip("\n").strip()
            if corrected:
                return corrected, True  # corrected = now validated
            return answer, False
        else:
            # Ambiguous — keep original but mark not validated
            return answer, False

    except Exception as e:
        print(f"[REFLECT] LLM error: {e} — skipping reflection")
        return answer, False

# ─── Layer 6: Query Classification (Enhanced) ─────────────────────────────────

# Study-mode trigger phrases — these indicate the user wants full-document synthesis
_STUDY_TRIGGERS = [
    "whole pdf", "entire pdf", "full pdf", "entire document", "whole document",
    "help me study", "help me read", "prepare for exam", "exam preparation",
    "table of content", "content of the pdf", "content of pdf",
    "give me pages", "pages to read", "study guide", "study plan",
    "important topics", "key topics", "what topics", "what chapters",
    "cover the pdf", "reading plan", "deep research", "comprehensive summary",
    "complete overview", "everything in", "all topics",
]

def classify_query(query: str) -> Dict[str, str]:
    """Classify query type and recommended retrieval strategy."""
    q = query.lower()

    # Document-study mode: user wants full-doc synthesis / exam prep
    if any(trigger in q for trigger in _STUDY_TRIGGERS):
        return {"type": "document_study", "strategy": "full_document", "intent": "study"}

    if any(w in q for w in ["what is", "define", "meaning of", "definition"]):
        return {"type": "factual",        "strategy": "hybrid", "intent": "definition"}
    elif any(w in q for w in ["how", "why", "explain", "describe", "elaborate"]):
        return {"type": "conceptual",     "strategy": "hybrid", "intent": "understanding"}
    elif any(w in q for w in ["compare", "difference", "vs", "versus", "contrast"]):
        return {"type": "comparison",     "strategy": "hybrid", "intent": "comparison"}
    elif any(w in q for w in ["summarize", "summary", "overview", "brief"]):
        return {"type": "summarization",  "strategy": "hybrid", "intent": "summarization"}
    elif any(w in q for w in ["list", "enumerate", "what are", "name the"]):
        return {"type": "listing",        "strategy": "hybrid", "intent": "enumeration"}
    else:
        return {"type": "general",        "strategy": "hybrid", "intent": "question"}

# ─── Layer 10: Multilingual Support ───────────────────────────────────────────

def detect_language(text: str) -> str:
    """Detect query language; returns ISO 639-1 code or 'en'.
    Short text defaults to English — langdetect is unreliable on < ~20 chars.
    """
    # Short text → assume English (langdetect is very unreliable on short input)
    if len(text.strip()) < 20 or len(text.split()) < 4:
        return "en"

    # Common English phrases that langdetect misclassifies
    _EN_MARKERS = ["my name", "i am", "what is", "how to", "tell me", "help me",
                   "explain", "please", "thank", "hello", "hi ", "hey "]
    lower = text.lower()
    if any(m in lower for m in _EN_MARKERS):
        return "en"

    try:
        lang = lang_detect(text)
        return lang if lang else "en"
    except LangDetectException:
        return "en"


def translate_to_english(text: str, source_lang: str) -> str:
    """Translate text to English if source_lang != 'en'."""
    if source_lang == "en":
        return text
    try:
        translator = GoogleTranslator(source=source_lang, target="en")
        return translator.translate(text) or text
    except Exception as e:
        print(f"[TRANSLATE] Failed ({source_lang}→en): {e} — using original")
        return text


def translate_from_english(text: str, target_lang: str) -> str:
    """Translate answer back to original language if needed."""
    if target_lang == "en":
        return text
    try:
        translator = GoogleTranslator(source="en", target=target_lang)
        return translator.translate(text) or text
    except Exception as e:
        print(f"[TRANSLATE] Failed (en→{target_lang}): {e} — original kept")
        return text

# ─── Layer 9: Advanced Confidence Scoring ─────────────────────────────────────

def calculate_confidence_v4(
    answer: str,
    citations: List[Citation],
    avg_retrieval_score: float,
    mmr_diversity: float,
    reflection_validated: bool,
    tokens_used: int,
) -> float:
    """
    Multi-factor v4 confidence:
    - Base citations / chunks
    - Answer quality (length + structure)
    - Average retrieval score
    - MMR diversity
    - Reflection validation bonus
    - Token usage ratio
    """
    score = 0.0

    # 1. Citations (up to 0.20)
    score += min(len(citations) * 0.07, 0.20)

    # 2. Answer length quality (0.10)
    wc = len(answer.split())
    if 40 < wc < 600:
        score += 0.10
    elif wc >= 600:
        score += 0.06  # penalise overly verbose

    # 3. Average retrieval score (0.20)
    score += min(avg_retrieval_score * 0.20, 0.20)

    # 4. MMR diversity (0.15)
    score += mmr_diversity * 0.15

    # 5. Reflection validation (0.25)
    if reflection_validated:
        score += 0.25

    # 6. Structured citations present (0.10)
    if citations and any(c.page is not None for c in citations):
        score += 0.10

    return round(min(score, 1.0), 4)

# ─── Full-Document study retrieval ────────────────────────────────────────────

def get_all_chunks_for_study(doc_ids: Optional[List[str]] = None) -> Tuple[List[Dict], str]:
    """
    For document_study queries: gather ALL chunks from requested documents,
    sorted by page number so Gemini sees them in reading order.
    If doc_ids is given, only those documents are included.
    Returns (chunks_list, filenames_str).
    """
    all_chunks: List[Dict] = []
    filenames = set()

    docs_to_search = {did: documents_store[did] for did in (doc_ids or documents_store.keys()) if did in documents_store}

    for doc_id, doc_data in docs_to_search.items():
        filenames.add(doc_data["filename"])
        chunks = chunk_lookup.get(doc_id, doc_data.get("chunks", []))
        for c in chunks:
            all_chunks.append({
                **c,
                "source":  doc_data["filename"],
                "doc_id":  doc_id,
                "score":   1.0,
            })

    # Sort by page so Gemini reads in document order
    all_chunks.sort(key=lambda x: (x.get("source", ""), x.get("page_num") or 0))
    return all_chunks, ", ".join(filenames)


async def generate_study_guide_with_gemini(
    query: str,
    all_chunks: List[Dict],
    filenames: str,
) -> Dict:
    """
    Study/exam-prep synthesis: send ALL document content to Gemini and ask it
    to produce a structured study guide with table of contents, topic summaries,
    and specific page recommendations.
    """
    # Build a compact page-ordered context (truncate very long chunks to save tokens)
    page_blocks = []
    seen_pages: set = set()
    for c in all_chunks:
        page_key = (c.get("source", ""), c.get("page_num"))
        if page_key in seen_pages:
            continue
        seen_pages.add(page_key)
        # Cap each page to ~800 chars to fit within context window
        text_snippet = c["text"][:800]
        page_blocks.append(
            f"[Page {c.get('page_num', '?')}]\n{text_snippet}"
        )

    full_context = "\n\n".join(page_blocks)
    total_pages  = max((c.get("page_num") or 0) for c in all_chunks)

    study_prompt = f"""You are an expert academic tutor helping a student deeply understand their course material, prepare for exams, and solve practice problems.

Document(s): {filenames}
Total pages: {total_pages}

Here is the complete page-by-page content of the document:
{full_context}

Student request: "{query}"

=== INSTRUCTIONS ===
1. If the Student request contains EXPLICIT formatting instructions (e.g., "Give answers in THIS STRICT FORMAT") or explicitly asks you to SOLVE, EVALUATE, or act as a specific persona (e.g., "university topper", "paper evaluator"):
-> IGNORE the default study guide format below. Follow the Student's instructions PERFECTLY.
-> You MUST use your own internal knowledge (parametric memory) to solve problems, evaluate answers, and provide detailed explanations that might not be explicitly written in the Document context. Use the Document primarily as the source of the questions/topics.

2. OTHERWISE, if the Student request is a general study request (e.g., "help me study", "what are the important topics"):
-> Provide a COMPREHENSIVE STUDY GUIDE with the following sections based ONLY on the document content:

## 📋 Table of Contents
List ALL major topics / chapters found in this document with their page numbers.

## 📚 Topic Summaries
For each major topic, write a 3-5 line summary covering what the document teaches about it.

## 🎯 5 Most Important Pages to Study
Identify exactly 5 page numbers that contain the most exam-critical content. For each:
- Page number
- Topic covered
- Why it's important for the exam (1-2 sentences)

## ⚡ Key Concepts to Remember
List 8-10 bullet points of the most important definitions, formulas, or facts from the entire document.

## 📝 Suggested Reading Order
Recommend the best order to read the document pages for exam preparation."""

    start  = time.time()
    answer_text, tokens = await llm_generate(study_prompt)
    gen_time = (time.time() - start) * 1000

    return {
        "answer":             answer_text,
        "generation_time_ms": gen_time,
        "tokens_used":        tokens,
    }


# ─── Gemini Answer Generation ──────────────────────────────────────────────────

async def generate_answer_with_gemini(
    query: str,
    context: str,
    conversation_history: List[Message],
    query_type: str,
) -> Dict:
    """Generate a grounded answer using Gemini with structured context."""

    system_prompt = f"""You are an expert AI tutor helping students understand academic material.
Query intent: {query_type.upper()}

RETRIEVED CONTEXT (use the information below to answer the student):
{context}

INSTRUCTIONS:
- Answer based on the context above. You may use your knowledge to clarify concepts.
- For FACTUAL queries: give precise definitions citing the source.
- For CONCEPTUAL queries: explain clearly with examples from the context.
- For COMPARISON queries: create a clear comparison using context data.
- For SUMMARIZATION: synthesise key points from all sources.
- For LISTING: enumerate items found in the context.
- Always mention which source/page your answer draws from.
- If the topic is not in the context, say so generically — do not hallucinate specific details not in the text."""

    # Flatten conversation + context into a single prompt for the LLM
    conv_text = ""
    for msg in conversation_history[-6:]:
        role_label = "Student" if msg.role == "user" else "Tutor"
        conv_text += f"{role_label}: {msg.content}\n"

    full_prompt = f"{system_prompt}\n\n{conv_text}\nStudent question: {query}"

    start  = time.time()
    answer_text, tokens = await llm_generate(full_prompt)
    gen_time = (time.time() - start) * 1000

    return {
        "answer":             answer_text,
        "generation_time_ms": gen_time,
        "tokens_used":        tokens,
    }


# --- Chat Pipeline (No RAG) ---------------------------------------------------

_CASUAL_PATTERNS = [
    "hi", "hey", "hello", "sup", "yo", "hiya", "howdy",
    "how are you", "how r u", "whats up", "what's up",
    "good morning", "good evening", "good night", "good afternoon",
    "thanks", "thank you", "ty", "thx", "cool", "okay", "ok", "bye",
    "who are you", "what can you do", "help me",
]

def _is_casual_chat(query: str) -> bool:
    q = query.lower().strip().rstrip("!?.,")
    return q in _CASUAL_PATTERNS or (
        any(q.startswith(p) for p in _CASUAL_PATTERNS) and len(q.split()) <= 6
    )


async def run_chat_pipeline(
    query: str,
    conversation_history: List[Message],
) -> Dict:
    """CHAT MODE: Pure conversational AI. No document retrieval."""
    prompt = (
        f"You are StudyAI, a friendly AI study companion.\n"
        f"Have a warm, natural conversation. If asked what you can do, explain the 5 modes:\n"
        f"- Fast: Quick PDF Q&A / Research: Deep analysis / Study: Exam prep / "
        f"Auto: Smart routing / Chat: Casual talk.\n"
        f"Keep replies concise and encouraging.\n\nStudent: {query}"
    )
    try:
        # Flatten conversation context into the prompt
        conv_text = ""
        for m in conversation_history[-4:]:
            label = "Student" if m.role == "user" else "Tutor"
            conv_text += f"{label}: {m.content}\n"

        full_prompt = f"{prompt}\n{conv_text}"
        t0 = time.time()
        answer_text, tokens = await llm_generate(full_prompt)
        gen_ms = (time.time() - t0) * 1000
        return {"answer": answer_text, "generation_time_ms": gen_ms, "tokens_used": tokens}
    except Exception:
        return {"answer": "Hey! I am StudyAI. Upload a PDF and ask me anything!", "generation_time_ms": 0, "tokens_used": 0}


# --- Fast Pipeline (Speed-optimised RAG) ---------------------------------------

async def run_fast_pipeline(
    query: str,
    conversation_history: List[Message],
    doc_ids: Optional[List[str]] = None,
) -> Tuple[str, List[Citation], float, Dict]:
    """FAST MODE: FAISS-only top-3 -> direct Gemini. No BM25/rewrite/reflection."""
    embed     = EmbeddingService.get()
    query_vec = embed.encode_one(query)

    docs_to_search = {did: documents_store[did] for did in (doc_ids or documents_store.keys()) if did in documents_store}

    fused: Dict[str, Dict] = {}
    for doc_id, doc_data in docs_to_search.items():
        sem    = _semantic_scores(query_vec, doc_id, k=6)
        chunks = chunk_lookup.get(doc_id, doc_data.get("chunks", []))
        for idx, chunk in enumerate(chunks):
            s = sem.get(idx, 0.0)
            if s <= 0:
                continue
            key = chunk.get("id") or f"{doc_id}_chunk_{idx}"
            fused[key] = {**chunk, "source": doc_data["filename"], "doc_id": doc_id, "score": s}

    top3 = sorted(fused.values(), key=lambda x: x["score"], reverse=True)[:3]
    if not top3:
        return "No relevant content found. Upload a PDF first!", [], 0.0, {}

    context = "\n\n---\n\n".join(
        f"[Page {c.get('page_num','?')} | {c.get('source','')}]\n{c['text']}" for c in top3
    )
    prompt = (
        f"You are a fast AI tutor. Answer concisely (under 120 words) using only this context:\n"
        f"{context}\n\nQuestion: {query}"
    )
    t0     = time.time()
    answer_text, tokens = await llm_generate(prompt)
    gen_ms = (time.time() - t0) * 1000

    citations = [
        Citation(
            text=c["text"][:150] + "..." if len(c["text"]) > 150 else c["text"],
            source=c.get("source", ""),
            page=c.get("page_num"),
            section=c.get("section"),
            confidence=round(c.get("score", 0.5), 4),
        ) for c in top3
    ]
    avg_score  = sum(c.get("score", 0) for c in top3) / max(len(top3), 1)
    confidence = round(min(0.50 + avg_score * 0.40, 0.88), 4)
    return answer_text, citations, confidence, {"generation_time_ms": gen_ms, "tokens_used": tokens}


# --- Auto-detect mode ---------------------------------------------------------

async def auto_detect_mode(query: str) -> str:
    """Detect best pipeline for query. Returns: chat | fast | research | study."""
    if _is_casual_chat(query):
        return "chat"
    if any(t in query.lower() for t in _STUDY_TRIGGERS):
        return "study"

    prompt = (
        f"Classify this student message and reply with ONLY one word.\n"
        f"Options: chat (small talk), fast (simple PDF question), "
        f"research (complex analysis), study (exam prep / overview)\n"
        f"Message: \"{query}\"\nReply with ONLY the one word:"
    )
    try:
        detected, _ = await llm_generate(prompt)
        detected = detected.strip().lower().split()[0]
        return detected if detected in ("chat", "fast", "research", "study") else "fast"
    except Exception:
        return "fast"



# ─── API Routes ────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "Production Agentic RAG Backend",
        "version": "4.0.0",
        "architecture": "Hybrid Semantic Agentic RAG",
        "pipeline": {
            "1_query_classification":    "[OK] Active",
            "2_multilingual_detection":  "[OK] langdetect",
            "3_query_rewriting":         "[OK] Gemini",
            "4_hybrid_retrieval":        "[OK] FAISS + BM25",
            "5_mmr_diversification":     "[OK] λ=0.70",
            "6_structured_context":      "[OK] Page/Section aware",
            "7_answer_generation":       "[OK] Gemini",
            "8_reflection_validation":   "[OK] Gemini post-gen",
            "9_advanced_confidence":     "[OK] 6-factor scoring",
            "10_neondb_persistence":     "[OK] asyncpg",
        },
        "features": [
            "Semantic + Lexical Hybrid Retrieval",
            "FAISS Vector Index",
            "BM25 Keyword Index",
            "Maximum Marginal Relevance (MMR)",
            "Query Rewriting Agent",
            "Hierarchical Metadata-Aware Chunking",
            "Structured Context Assembly",
            "Reflection / Hallucination Validation",
            "6-Factor Confidence Scoring",
            "Multilingual Support (langdetect + deep-translator)",
            "NeonDB Persistent Storage",
        ],
    }


@app.get("/api/v1/health")
async def health():
    return await health_check()




async def health_check():
    embed = EmbeddingService.get()
    return {
        "status":            "healthy",
        "version":           "4.0.0",
        "gemini_configured": bool(GEMINI_API_KEY),
        "documents_loaded":  len(documents_store),
        "faiss_indexes":     len(faiss_indexes),
        "bm25_indexes":      len(bm25_indexes),
        "embedding_model":   EmbeddingService.MODEL_NAME,
        "embedding_dim":     embed.dim,
        "pipeline_active":   True,
    }


@app.get("/api/v1/documents")
async def list_documents():
    docs = []
    for doc_id, data in documents_store.items():
        docs.append({
            "doc_id":      doc_id,
            "filename":    data["filename"],
            "page_count":  data["page_count"],
            "chunk_count": len(data.get("chunks", [])),
            "indexed":     doc_id in faiss_indexes,
            "uploaded_at": datetime.fromtimestamp(data["uploaded_at"]).isoformat(),
        })
    return {"documents": docs, "total": len(docs)}


@app.post("/api/v1/documents/upload")
async def upload_document(file: UploadFile = File(...), session_id: Optional[int] = Query(None)):
    print(f"\n[UPLOAD] Processing: {file.filename}  (session_id={session_id})")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files supported")

    start = time.time()

    try:
        # Write to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Layer 1: Hierarchical chunking
        print(f"[UPLOAD] [1/4] Extracting text + hierarchical chunking…")
        full_text, page_count, pages = extract_text_from_pdf(tmp_path)
        os.unlink(tmp_path)

        # Generate doc_id (content hash = deterministic)
        doc_id = "doc_" + hashlib.sha256(content).hexdigest()[:12]
        chunks = chunk_text_hierarchical(pages, doc_id)
        print(f"[UPLOAD]       → {page_count} pages, {len(chunks)} chunks")
        
        if not chunks:
            raise HTTPException(status_code=400, detail="Could not extract any text from the PDF. It might be a scanned image or completely empty.")

        # Layer 2: Generate embeddings
        print(f"[UPLOAD] [2/4] Generating embeddings…")
        embed = EmbeddingService.get()
        texts = [c["text"] for c in chunks]
        embeddings = embed.encode(texts)
        print(f"[UPLOAD]       → Embeddings shape: {embeddings.shape}")

        # Layer 3: Build in-memory FAISS + BM25 indexes
        print(f"[UPLOAD] [3/4] Indexing (FAISS + BM25)…")
        doc_data = {
            "filename":    file.filename,
            "text":        full_text,
            "chunks":      chunks,
            "embeddings":  embeddings,
            "page_count":  page_count,
            "uploaded_at": time.time(),
        }
        documents_store[doc_id] = doc_data
        _build_indexes(doc_id, doc_data)

        # Layer 3 cont.: Persist to NeonDB
        print(f"[UPLOAD] [4/4] Persisting to NeonDB…")
        await db.save_document(doc_id, file.filename, full_text, chunks, page_count, embeddings)

        elapsed = (time.time() - start) * 1000
        print(f"[UPLOAD] [OK] {file.filename} — {page_count}p / {len(chunks)}c / {elapsed:.0f}ms")

        return {
            "status":           "success",
            "document_id":      doc_id,
            "filename":         file.filename,
            "pages":            page_count,
            "chunks_created":   len(chunks),
            "embedding_dim":    int(embeddings.shape[1]),
            "processing_time_ms": elapsed,
        }

        # Link document to session if provided
        if session_id:
            # In-memory mapping (immediate; always works)
            if session_id not in session_doc_map:
                session_doc_map[session_id] = set()
            session_doc_map[session_id].add(doc_id)
            print(f"[UPLOAD]       → Linked to session {session_id} (in-memory: {session_doc_map[session_id]})")
            # Also persist to DB (best-effort)
            await db.link_doc_to_session(session_id, doc_id)

        return result

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"[UPLOAD ERROR] {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(e))


@app.delete("/api/v1/documents/{doc_id}")
async def delete_document(doc_id: str):
    if doc_id not in documents_store:
        raise HTTPException(404, f"Document '{doc_id}' not found")

    documents_store.pop(doc_id, None)
    faiss_indexes.pop(doc_id, None)
    bm25_indexes.pop(doc_id, None)
    chunk_lookup.pop(doc_id, None)
    await db.delete_document(doc_id)

    return {"status": "deleted", "doc_id": doc_id}


async def _save_assistant_response(user_id, session_id, response: QueryResponse):
    """Save assistant response to chat history if user is authenticated."""
    if user_id and session_id:
        try:
            await db.save_chat_message(
                session_id=session_id, role="assistant", content=response.answer,
                mode=response.metadata.pipeline_mode if response.metadata else None,
                confidence=response.confidence,
                citations=[c.dict() for c in response.citations] if response.citations else [],
            )
        except Exception as e:
            print(f"[CHAT HISTORY] Error saving assistant message: {e}")


@app.post("/api/v1/query/ask", response_model=QueryResponse)
async def ask_question(request: QueryRequest, raw_request: Request):
    total_start = time.time()
    print(f"\n{'═'*60}")
    print(f"[AGENTIC PIPELINE v4.0] START")
    print(f"Query: {request.query}")
    print(f"{'═'*60}")

    # Optional auth — save chat history if user is logged in
    current_user = await get_optional_user(raw_request)
    session_id = request.session_id
    user_id = current_user["user_id"] if current_user else None

    # Save user message to chat history
    if user_id and session_id:
        await db.save_chat_message(
            session_id=session_id, role="user", content=request.query,
            mode=request.mode,
        )

    # Determine which documents to search
    # Priority: 1) explicit doc_ids from frontend, 2) session-linked docs, 3) all docs
    session_doc_ids: Optional[List[str]] = None
    if request.doc_ids:
        # Frontend explicitly specified which docs to search
        session_doc_ids = request.doc_ids
        print(f"[DOCS] Using {len(session_doc_ids)} doc_ids from request: {session_doc_ids}")
    elif session_id:
        # Try in-memory map, then DB
        if session_id in session_doc_map and session_doc_map[session_id]:
            session_doc_ids = list(session_doc_map[session_id])
            print(f"[DOCS] Scoping to {len(session_doc_ids)} docs (in-memory): {session_doc_ids}")
        else:
            session_doc_ids = await db.get_session_doc_ids(session_id)
            if session_doc_ids:
                session_doc_map[session_id] = set(session_doc_ids)
                print(f"[DOCS] Scoping to {len(session_doc_ids)} docs (DB): {session_doc_ids}")
            else:
                session_doc_ids = []
                print(f"[DOCS] Session {session_id} has no linked docs")

    # Determine if we have docs available for this request
    has_docs = bool(session_doc_ids) if session_doc_ids is not None else bool(documents_store)

    try:
        # Language detection used by all modes
        original_query = request.query
        lang_detected  = detect_language(original_query)
        english_query  = translate_to_english(original_query, lang_detected)

        # Resolve pipeline mode
        req_mode = (request.mode or "auto").lower().strip()
        if req_mode == "auto":
            resolved_mode = await auto_detect_mode(english_query)
            # When auto-detected, upgrade "fast" to "research" for full context
            if resolved_mode == "fast" and has_docs:
                print("[AUTO] Upgrading fast → research for full context")
                resolved_mode = "research"
        elif req_mode in ("chat", "fast", "study", "research"):
            resolved_mode = req_mode
        else:
            resolved_mode = await auto_detect_mode(english_query)

        print(f"[MODE] requested={req_mode}  resolved={resolved_mode}  lang={lang_detected}")

        # CHAT MODE ---------------------------------------------------
        if resolved_mode == "chat":
            # If user has uploaded docs, upgrade to Research pipeline
            # so the chatbot can actually talk about the PDF content
            if has_docs:
                print("[CHAT+DOCS] Documents available — upgrading to research pipeline for full context")
                resolved_mode = "research"
                # Fall through to Research pipeline below
            else:
                # Pure chat — no documents uploaded
                gen = await run_chat_pipeline(english_query, request.conversation_history)
                answer = gen["answer"]
                if lang_detected != "en":
                    answer = translate_from_english(answer, lang_detected)
                total_time = (time.time() - total_start) * 1000
                resp = QueryResponse(
                    answer=answer, citations=[], confidence=0.95,
                    metadata=QueryMetadata(
                        query_type="chat", retrieval_strategy="none", pipeline_mode="chat",
                        generation_time_ms=gen["generation_time_ms"],
                        tokens_used=gen["tokens_used"], total_time_ms=total_time,
                        language_detected=lang_detected, original_query=original_query,
                        rewritten_query=english_query,
                    ),
                )
                await _save_assistant_response(user_id, session_id, resp)
                return resp

        # FAST MODE ---------------------------------------------------
        if resolved_mode == "fast":
            if not has_docs:
                return QueryResponse(
                    answer="Upload a PDF first to use Fast mode!",
                    citations=[], confidence=0.0,
                    metadata=QueryMetadata(pipeline_mode="fast", total_time_ms=0),
                )
            answer_text, citations, confidence, timing = await run_fast_pipeline(
                english_query, request.conversation_history, doc_ids=session_doc_ids
            )
            if lang_detected != "en":
                answer_text = translate_from_english(answer_text, lang_detected)
            total_time = (time.time() - total_start) * 1000
            await db.save_query(
                query_text=original_query, query_type="fast", strategy="semantic_only",
                answer=answer_text, citations=[c.dict() for c in citations],
                confidence=confidence, chunks_retrieved=len(citations), chunks_used=len(citations),
                tokens_used=timing.get("tokens_used", 0), retrieval_time_ms=0,
                generation_time_ms=timing.get("generation_time_ms", 0), total_time_ms=total_time,
                mmr_diversity_score=0.0, avg_retrieval_score=confidence, reflection_validated=False,
                language_detected=lang_detected, original_query=original_query, rewritten_query=english_query,
                user_id=user_id,
            )
            resp = QueryResponse(
                answer=answer_text, citations=citations, confidence=confidence,
                metadata=QueryMetadata(
                    query_type="fast", retrieval_strategy="semantic_only", pipeline_mode="fast",
                    chunks_retrieved=len(citations), chunks_used=len(citations),
                    tokens_used=timing.get("tokens_used", 0),
                    generation_time_ms=timing.get("generation_time_ms", 0),
                    total_time_ms=total_time, language_detected=lang_detected,
                    original_query=original_query, rewritten_query=english_query,
                ),
            )
            await _save_assistant_response(user_id, session_id, resp)
            return resp

        # STUDY MODE --------------------------------------------------
        if resolved_mode == "study":
            if not has_docs:
                return QueryResponse(
                    answer="Upload a PDF first to use Study mode!",
                    citations=[], confidence=0.0,
                    metadata=QueryMetadata(pipeline_mode="study", total_time_ms=0),
                )
            ret_start = time.time()
            all_chunks, filenames = get_all_chunks_for_study(doc_ids=session_doc_ids)
            ret_ms    = (time.time() - ret_start) * 1000
            gen       = await generate_study_guide_with_gemini(english_query, all_chunks, filenames)
            answer    = gen["answer"]
            if lang_detected != "en":
                answer = translate_from_english(answer, lang_detected)
            seen_pgs: set = set()
            cit_list: List[Citation] = []
            for c in all_chunks:
                pk = (c.get("source", ""), c.get("page_num"))
                if pk not in seen_pgs:
                    seen_pgs.add(pk)
                    cit_list.append(Citation(
                        text=c["text"][:150] + "..." if len(c["text"]) > 150 else c["text"],
                        source=c.get("source", "Unknown"), page=c.get("page_num"),
                        section=c.get("section"), confidence=1.0,
                    ))
            total_time = (time.time() - total_start) * 1000
            await db.save_query(
                query_text=original_query, query_type="document_study", strategy="full_document",
                answer=answer, citations=[c.dict() for c in cit_list[:20]], confidence=0.92,
                chunks_retrieved=len(all_chunks), chunks_used=len(all_chunks),
                tokens_used=gen["tokens_used"], retrieval_time_ms=ret_ms,
                generation_time_ms=gen["generation_time_ms"], total_time_ms=total_time,
                mmr_diversity_score=1.0, avg_retrieval_score=1.0, reflection_validated=True,
                language_detected=lang_detected, original_query=original_query, rewritten_query=english_query,
                user_id=user_id,
            )
            resp = QueryResponse(
                answer=answer, citations=cit_list[:20], confidence=0.92,
                metadata=QueryMetadata(
                    query_type="document_study", retrieval_strategy="full_document_synthesis",
                    pipeline_mode="study", chunks_retrieved=len(all_chunks), chunks_used=len(all_chunks),
                    tokens_used=gen["tokens_used"], retrieval_time_ms=ret_ms,
                    generation_time_ms=gen["generation_time_ms"], total_time_ms=total_time,
                    avg_retrieval_score=1.0, mmr_diversity_score=1.0, reflection_validated=True,
                    language_detected=lang_detected, original_query=original_query, rewritten_query=english_query,
                ),
            )
            await _save_assistant_response(user_id, session_id, resp)
            return resp

        # RESEARCH MODE (v4 full pipeline) -- default fallback ---------
        if not has_docs:
            return QueryResponse(
                answer="Please upload a PDF first to enable the research pipeline.",
                citations=[], confidence=0.0,
                metadata=QueryMetadata(pipeline_mode="research", total_time_ms=0),
            )

        print("[1/8] CLASSIFICATION...")
        classification = classify_query(english_query)
        query_type  = classification["type"]
        strategy    = classification["strategy"]
        print(f"       -> Type: {query_type.upper()}, Strategy: {strategy}")

        if query_type == "document_study":
            rewritten_query = english_query
        else:
            print("[2/8] QUERY REWRITING (Gemini)…")
            rewritten_query = await query_rewrite_agent(english_query, query_type)
            print(f"       → Original:  {english_query[:60]}…")
            print(f"       → Rewritten: {rewritten_query[:80]}…")

        # ══════════════════════════════════════════════════════════
        # ── STUDY MODE: full-document synthesis pipeline ──────────
        # ══════════════════════════════════════════════════════════
        if query_type == "document_study":
            print("[STUDY MODE] Full-document synthesis activated…")
            retrieval_start = time.time()
            all_study_chunks, filenames = get_all_chunks_for_study(doc_ids=session_doc_ids)
            retrieval_time = (time.time() - retrieval_start) * 1000
            print(f"[STUDY MODE] {len(all_study_chunks)} chunks from: {filenames}")

            print("[STUDY MODE] Generating study guide (Gemini)…")
            gen_result = await generate_study_guide_with_gemini(
                english_query, all_study_chunks, filenames
            )

            final_answer = gen_result["answer"]
            if lang_detected != "en":
                final_answer = translate_from_english(final_answer, lang_detected)

            # Build page citations from all unique pages
            seen_pages_cit: set = set()
            citations: List[Citation] = []
            for c in all_study_chunks:
                pk = (c.get("source", ""), c.get("page_num"))
                if pk not in seen_pages_cit:
                    seen_pages_cit.add(pk)
                    citations.append(Citation(
                        text=c["text"][:150] + "…" if len(c["text"]) > 150 else c["text"],
                        source=c.get("source", "Unknown"),
                        page=c.get("page_num"),
                        section=c.get("section"),
                        confidence=1.0,
                    ))

            total_time = (time.time() - total_start) * 1000
            confidence  = 0.92  # high confidence: full doc was used
            mmr_diversity       = 1.0
            avg_retrieval_score = 1.0
            reflection_ok       = True

            print(f"[STUDY MODE COMPLETE] {total_time:.0f}ms | {len(citations)} page sources")

            await db.save_query(
                query_text=original_query,
                query_type=query_type,
                strategy="full_document",
                answer=final_answer,
                citations=[c.dict() for c in citations[:20]],
                confidence=confidence,
                chunks_retrieved=len(all_study_chunks),
                chunks_used=len(all_study_chunks),
                tokens_used=gen_result["tokens_used"],
                retrieval_time_ms=retrieval_time,
                generation_time_ms=gen_result["generation_time_ms"],
                total_time_ms=total_time,
                mmr_diversity_score=mmr_diversity,
                avg_retrieval_score=avg_retrieval_score,
                reflection_validated=reflection_ok,
                language_detected=lang_detected,
                original_query=original_query,
                rewritten_query=rewritten_query,
                user_id=user_id,
            )

            return QueryResponse(
                answer=final_answer,
                citations=citations[:20],
                confidence=confidence,
                metadata=QueryMetadata(
                    pipeline_mode=resolved_mode,
                    query_type="document_study",
                    retrieval_strategy="full_document_synthesis",
                    chunks_retrieved=len(all_study_chunks),
                    chunks_used=len(all_study_chunks),
                    tokens_used=gen_result["tokens_used"],
                    retrieval_time_ms=retrieval_time,
                    generation_time_ms=gen_result["generation_time_ms"],
                    total_time_ms=total_time,
                    avg_retrieval_score=1.0,
                    mmr_diversity_score=1.0,
                    reflection_validated=True,
                    language_detected=lang_detected,
                    original_query=original_query,
                    rewritten_query=rewritten_query,
                ),
            )

        # ══════════════════════════════════════════════════════════
        # ── NORMAL RAG PIPELINE ───────────────────────────────────
        # ══════════════════════════════════════════════════════════

        # ── STEP 3: Hybrid Retrieval
        print("[3/8] HYBRID RETRIEVAL (FAISS + BM25)…")
        retrieval_start = time.time()
        candidates = hybrid_retrieve(rewritten_query, top_k=12, doc_ids=session_doc_ids)
        retrieval_time = (time.time() - retrieval_start) * 1000
        print(f"       → Candidates: {len(candidates)}, Time: {retrieval_time:.0f}ms")

        if not candidates:
            return QueryResponse(
                answer="I couldn't find relevant content in the uploaded documents for your question.",
                citations=[],
                confidence=0.05,
                metadata=QueryMetadata(
                    query_type=query_type,
                    language_detected=lang_detected,
                    original_query=original_query,
                    rewritten_query=rewritten_query,
                    total_time_ms=(time.time() - total_start) * 1000,
                ),
            )

        # ── STEP 4: MMR Diversification
        print("[4/8] MMR DIVERSIFICATION…")
        embed = EmbeddingService.get()
        query_vec = embed.encode_one(rewritten_query)
        top_chunks, mmr_diversity = mmr_select(candidates, query_vec, top_k=5, lambda_val=0.7)
        print(f"       → Selected: {len(top_chunks)}, Diversity score: {mmr_diversity:.3f}")

        avg_retrieval_score = (
            sum(c.get("score", 0) for c in top_chunks) / len(top_chunks)
            if top_chunks else 0.0
        )

        # ── STEP 5: Structured Context
        print("[5/8] STRUCTURED CONTEXT ASSEMBLY…")
        context = build_structured_context(top_chunks)

        # ── STEP 6: Answer Generation
        print("[6/8] ANSWER GENERATION (Gemini)…")
        gen_result = await generate_answer_with_gemini(
            english_query, context, request.conversation_history, query_type
        )
        raw_answer = gen_result["answer"]

        # ── STEP 7: Reflection Validation
        print("[7/8] REFLECTION VALIDATION (Gemini)…")
        final_answer, reflection_ok = await reflection_agent(english_query, raw_answer, context)
        print(f"       → Validated: {reflection_ok}")

        # ── STEP 8: Advanced Confidence + Citations
        print("[8/8] ADVANCED CONFIDENCE SCORING…")
        citations = [
            Citation(
                text=c["text"][:220] + "…" if len(c["text"]) > 220 else c["text"],
                source=c.get("source", "Unknown"),
                page=c.get("page_num"),
                section=c.get("section"),
                confidence=round(c.get("score", 0.5), 4),
            )
            for c in top_chunks
        ]

        confidence = calculate_confidence_v4(
            answer=final_answer,
            citations=citations,
            avg_retrieval_score=avg_retrieval_score,
            mmr_diversity=mmr_diversity,
            reflection_validated=reflection_ok,
            tokens_used=gen_result["tokens_used"],
        )
        print(f"       → Confidence: {confidence:.4f}")

        # ── Translate answer back if needed
        if lang_detected != "en":
            print(f"[POST] Translating answer back to '{lang_detected}'…")
            final_answer = translate_from_english(final_answer, lang_detected)

        total_time = (time.time() - total_start) * 1000
        print(f"\n{'─'*60}")
        print(f"[PIPELINE COMPLETE] {total_time:.0f}ms")
        print(f"  Query type:    {query_type}")
        print(f"  Language:      {lang_detected}")
        print(f"  Candidates:    {len(candidates)}, Used: {len(top_chunks)}")
        print(f"  Avg score:     {avg_retrieval_score:.4f}")
        print(f"  MMR diversity: {mmr_diversity:.4f}")
        print(f"  Reflected:     {reflection_ok}")
        print(f"  Confidence:    {confidence:.4f}")
        print(f"{'─'*60}\n")

        # ── Persist to NeonDB
        await db.save_query(
            query_text=original_query,
            query_type=query_type,
            strategy=strategy,
            answer=final_answer,
            citations=[c.dict() for c in citations],
            confidence=confidence,
            chunks_retrieved=len(candidates),
            chunks_used=len(top_chunks),
            tokens_used=gen_result["tokens_used"],
            retrieval_time_ms=retrieval_time,
            generation_time_ms=gen_result["generation_time_ms"],
            total_time_ms=total_time,
            mmr_diversity_score=mmr_diversity,
            avg_retrieval_score=avg_retrieval_score,
            reflection_validated=reflection_ok,
            language_detected=lang_detected,
            original_query=original_query,
            rewritten_query=rewritten_query,
            user_id=user_id,
        )

        resp = QueryResponse(
            answer=final_answer,
            citations=citations,
            confidence=confidence,
            metadata=QueryMetadata(
                pipeline_mode=resolved_mode,
                query_type=query_type,
                retrieval_strategy="hybrid_semantic_mmr",
                chunks_retrieved=len(candidates),
                chunks_used=len(top_chunks),
                tokens_used=gen_result["tokens_used"],
                retrieval_time_ms=retrieval_time,
                generation_time_ms=gen_result["generation_time_ms"],
                total_time_ms=total_time,
                avg_retrieval_score=round(avg_retrieval_score, 4),
                mmr_diversity_score=round(mmr_diversity, 4),
                reflection_validated=reflection_ok,
                language_detected=lang_detected,
                original_query=original_query,
                rewritten_query=rewritten_query,
            ),
        )
        await _save_assistant_response(user_id, session_id, resp)
        return resp

    except Exception as e:
        print(f"[PIPELINE ERROR] {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(e))


# NOTE: /api/v1/progress is now handled by routes_progress.py (per-user, authenticated)


@app.get("/api/v1/query/history")
async def query_history(limit: int = 20):
    """Return recent query history from NeonDB."""
    history = await db.get_query_history(limit=limit)
    return {"history": history, "total": len(history)}


@app.post("/api/v1/feedback")
async def submit_feedback(query_id: int, helpful: bool, comment: Optional[str] = None):
    """Record user feedback for a query."""
    print(f"[FEEDBACK] query_id={query_id}, helpful={helpful}")
    saved = await db.save_feedback(query_id, helpful, comment)
    return {"status": "success" if saved else "saved_locally", "message": "Thank you!"}


@app.get("/api/v1/analytics")
async def get_analytics():
    """Full analytics from NeonDB."""
    return await db.get_analytics()

# ─── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("PRODUCTION AGENTIC RAG BACKEND — v4.0.0")
    print("Hybrid Semantic Agentic RAG")
    print("=" * 70)
    print("Pipeline:")
    print("  0. Language Detection + Translation  (langdetect + deep-translator)")
    print("  1. Query Classification              (rule-based + heuristic)")
    print("  2. Query Rewriting Agent             (Gemini)")
    print("  3. Hybrid Retrieval                  (FAISS cosine + BM25 Okapi)")
    print("  4. MMR Diversification               (lambda=0.70)")
    print("  5. Structured Context Assembly       (Page + Section aware)")
    print("  6. Answer Generation                 (LLM)")
    print("  7. Reflection / Validation Agent     (LLM)")
    print("  8. Advanced Confidence Scoring       (6-factor)")
    print("=" * 70)
    llm_info = get_provider_info()
    print(f"LLM Provider : {llm_info['provider'].upper()} ({llm_info['model']})")
    print(f"Embed Model  : {EmbeddingService.MODEL_NAME}")
    print(f"Server       : http://localhost:8000")
    print(f"API Docs     : http://localhost:8000/docs")
    print("=" * 70)

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
