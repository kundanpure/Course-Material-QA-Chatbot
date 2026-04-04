# StudyAI — Intelligent Study Companion 🎓

> **AI-powered study platform** with a 10-layer Agentic RAG pipeline, 5 query modes, AI exam evaluation, study material generation, email verification, Google OAuth, and real-time learning analytics — **deployed live on Render + Netlify**.

<p align="center">
  <img src="screenshots/chat_dashboard.png" width="800" alt="StudyAI Chat Dashboard" />
</p>

---

## 🌐 Live Deployment

| Service | Platform | URL |
|---------|----------|-----|
| **Backend API** | Render (Free Tier) | `https://studyai-backend.onrender.com` |
| **Frontend App** | Netlify | `https://studyai-app.netlify.app` |
| **API Docs** | Swagger UI | `https://studyai-backend.onrender.com/docs` |
| **Database** | NeonDB (PostgreSQL) | Serverless PostgreSQL |

### Deployment Architecture

```mermaid
graph LR
    User[👨‍🎓 Student] -->|HTTPS| Netlify[Netlify CDN<br/>React Frontend]
    Netlify -->|API Calls| Render[Render<br/>FastAPI Backend]
    Render -->|SQL| Neon[(NeonDB<br/>PostgreSQL)]
    Render -->|Embeddings| ONNX[ONNX Runtime<br/>fastembed]
    Render -->|LLM Calls| Gemini[Google Gemini API]
    Render -->|LLM Fallback| Groq[Groq Cloud API]
    Render -->|Email| Gmail[Gmail SMTP]

    style Netlify fill:#00c7b7,color:#fff
    style Render fill:#46e3b7,color:#000
    style Neon fill:#3ecf8e,color:#fff
    style Gemini fill:#4285f4,color:#fff
    style Groq fill:#f55036,color:#fff
```

### Deployment Stack Decisions

| Concern | Decision | Rationale |
|---------|----------|-----------|
| **Embeddings** | `fastembed` (ONNX) instead of PyTorch | Render free tier has 512 MB RAM; PyTorch alone uses ~400 MB |
| **Embedding Model** | `all-MiniLM-L6-v2` | 384-dim, fast, accurate — same model via ONNX |
| **Workers** | 1 Uvicorn worker | RAM constraint; single-worker is sufficient |
| **Frontend Host** | Netlify (separate) | Free, global CDN, auto-deploys from Git |
| **Database** | NeonDB serverless | Free tier, auto-scaling, no cold-start penalty |

---

## 🌟 What Makes StudyAI Different?

### ChatGPT / Normal LLM vs StudyAI

| Feature | ChatGPT / Normal LLMs | **StudyAI (Agentic RAG)** |
|---------|----------------------|---------------------------|
| **Knowledge** | Trained on general internet data up to cutoff | **Grounded in YOUR uploaded documents** — zero hallucination by design |
| **Citations** | No source tracking | **Page-level citations** with exact source, page number, and section |
| **Retrieval** | None — relies purely on memorized training data | **Hybrid FAISS + BM25** dual retrieval with score fusion |
| **Verification** | No — can confidently hallucinate | **Reflection Agent** validates every answer against context |
| **Diversity** | May repeat same information | **MMR diversification** ensures varied, comprehensive results |
| **Query Understanding** | One-size-fits-all | **5 specialized pipelines** auto-selected based on query type |
| **Exam Prep** | Generic study advice | **Full-document study guides** with page recommendations |
| **Exam Evaluation** | No grading capability | **AI exam grading** with 3 strictness modes + model answers |
| **Study Materials** | Generic content | **5 AI tools**: guides, flashcards, quizzes, concept maps, resources |
| **Multilingual** | Good but no explicit routing | **Auto-detects language**, retrieves in English, responds in user's language |
| **Confidence** | No transparency | **6-factor confidence scoring** — you know exactly how reliable each answer is |
| **Speed** | ~2-5s per response | **Fast Mode**: sub-second with FAISS-only retrieval |
| **Privacy** | Data sent to third-party servers | **Your PDFs stay on your server** — self-hosted |

### Why Better Than Other RAG Systems?

Most RAG systems use a single retrieval method (usually just vector search). StudyAI uses a **10-layer agentic pipeline** that acts like a team of specialist agents:

1. 🔍 **Dual Retrieval** — Not just FAISS vectors; BM25 catches exact keyword matches that embeddings miss
2. 🧠 **Query Rewriting** — An LLM rewrites your question to maximize retrieval quality
3. 🎯 **MMR Diversity** — Ensures you get information from different parts of the document, not just the most similar chunk repeated
4. ✅ **Self-Healing** — Reflection Agent checks if the answer is actually supported by retrieved context
5. 🎓 **Study Mode** — Full-document synthesis for exam prep (most RAG systems only do Q&A)
6. 🌐 **Multilingual** — Ask in Hindi, get answers grounded in English documents
7. 📊 **Transparent Scoring** — 6-factor confidence tells you HOW MUCH to trust each answer

---

## 🏗️ System Architecture

### Overall Architecture — How Everything Connects

```mermaid
graph TB
    subgraph Frontend["🖥️ Frontend (React + Vite + TailwindCSS)"]
        UI[Chat Interface] --> AuthCtx[Auth Context]
        UI --> APILayer[API Service Layer]
        Login[Login Page] --> AuthCtx
        Signup[Signup Page] --> AuthCtx
        ForgotPw[Forgot Password] --> APILayer
        Dashboard[Dashboard] --> APILayer
        StudyMat[Study Materials] --> APILayer
        Evaluate[Exam Evaluator] --> APILayer
    end

    subgraph Backend["⚙️ Backend (FastAPI + Uvicorn)"]
        Router[API Router] --> AuthRoutes[Auth Routes]
        Router --> QueryRoute[Query Pipeline]
        Router --> DocRoute[Document Upload]
        Router --> ChatHist[Chat History]
        Router --> EvalRoute[Evaluation Routes]
        Router --> StudyMatRoute[Study Materials Routes]
        Router --> ProgressRoute[Progress Routes]
        
        AuthRoutes --> JWT[JWT Auth]
        AuthRoutes --> SMTP[Email OTP Service]
        AuthRoutes --> GoogleAPI[Google OAuth]
        
        QueryRoute --> Pipeline[Agentic RAG Pipeline]
        DocRoute --> Chunker[PDF Chunker]
        Chunker --> Indexer[Index Builder]
        EvalRoute --> EvalLLM[Eval LLM Provider]
    end

    subgraph Pipeline["🧠 10-Layer Agentic Pipeline"]
        L1[Language Detection] --> L2[Query Classification]
        L2 --> L3[Mode Router]
        L3 -->|Chat| ChatPipe[Chat Pipeline]
        L3 -->|Fast| FastPipe[Fast Pipeline]
        L3 -->|Study| StudyPipe[Study Pipeline]
        L3 -->|Research| ResearchPipe[Research Pipeline]
    end

    subgraph Storage["💾 Storage Layer"]
        PG[(PostgreSQL / NeonDB)]
        FAISS_IDX[FAISS Vector Index]
        BM25_IDX[BM25 Lexical Index]
    end

    subgraph External["🌐 External Services"]
        Gemini[Google Gemini LLM]
        Groq[Groq LLM]
        Gmail[Gmail SMTP]
        GoogleAuth[Google OAuth API]
    end

    APILayer <-->|HTTP/JSON| Router
    Pipeline --> FAISS_IDX
    Pipeline --> BM25_IDX
    Pipeline --> Gemini
    Pipeline --> Groq
    Indexer --> FAISS_IDX
    Indexer --> BM25_IDX
    AuthRoutes --> PG
    ChatHist --> PG
    DocRoute --> PG
    EvalRoute --> PG
    SMTP --> Gmail
    GoogleAPI --> GoogleAuth
```

---

## 🔬 The 10-Layer Agentic Pipeline (Deep Dive)

This is the heart of StudyAI. Each "layer" is a specialized agent that transforms the query progressively.

### Layer-by-Layer Flow

```mermaid
graph LR
    Q[User Query] --> L0[Layer 0<br/>Language Detection]
    L0 --> L1[Layer 1<br/>Query Classification]
    L1 --> L2[Layer 2<br/>Query Rewriting]
    L2 --> L3[Layer 3<br/>Semantic Retrieval<br/>FAISS]
    L2 --> L4[Layer 4<br/>Lexical Retrieval<br/>BM25]
    L3 --> L5[Layer 5<br/>Hybrid Score Fusion]
    L4 --> L5
    L5 --> L6[Layer 6<br/>MMR Diversification]
    L6 --> L7[Layer 7<br/>Structured Context<br/>Assembly]
    L7 --> L8[Layer 8<br/>LLM Answer<br/>Generation]
    L8 --> L9[Layer 9<br/>Reflection Agent]
    L9 --> L10[Layer 10<br/>Confidence Scoring]
    L10 --> R[Final Response]

    style L0 fill:#e0e7ff
    style L1 fill:#e0e7ff
    style L2 fill:#c7d2fe
    style L3 fill:#a5b4fc
    style L4 fill:#a5b4fc
    style L5 fill:#818cf8
    style L6 fill:#6366f1
    style L7 fill:#4f46e5
    style L8 fill:#4338ca
    style L9 fill:#3730a3
    style L10 fill:#312e81
```

---

### Layer 0 — 🌐 Language Detection & Translation

```
Module: detect_language(), translate_to_english(), translate_from_english()
```

**What it does:** Automatically detects the language of the incoming query. If it's not English, it translates the query to English for retrieval (since documents are typically in English), then translates the final answer *back* to the user's language.

**How it works:**
- Uses `langdetect` library for ISO 639-1 language code detection
- Short queries (<20 chars) default to English (langdetect is unreliable on very short text)
- Translation powered by `deep-translator` (Google Translate API)

**Example:**
```
Input:  "इस PDF में मशीन लर्निंग क्या है?"  (Hindi)
→ Detected: "hi"
→ Translated: "What is machine learning in this PDF?"
→ [Pipeline runs in English]
→ Answer translated back to Hindi
```

---

### Layer 1 — 🏷️ Query Classification

```
Module: classify_query()
```

**What it does:** Analyzes the user's query to determine its *type* and the best *retrieval strategy*. This decides how aggressively we need to search.

**Classification Types:**

| Query Type | Trigger | Strategy |
|-----------|---------|----------|
| `greeting` | "hi", "hello", "how are you" | No retrieval needed |
| `document_study` | "study guide", "key topics", "summarize" | Full-document synthesis |
| `factual` | Direct questions ("what is X?") | Hybrid retrieval |
| `conceptual` | "explain", "how does", "difference between" | Hybrid + query rewriting |
| `application` | "calculate", "solve", "apply" | Hybrid + deep context |

**Rules-based + heuristic approach:**
```python
if is_casual_chat(query)  → "greeting"
if study_trigger in query → "document_study"
if "?" in query           → "factual" / "conceptual"
else                      → "factual" (default)
```

---

### Layer 2 — ✏️ Query Rewriting Agent

```
Module: query_rewrite_agent()
```

**What it does:** Uses the LLM itself to *rewrite* the user's query into a more retrieval-friendly form. This dramatically improves retrieval recall.

**Why it matters:** Users often write vague or conversational queries. The rewriting agent expands them into specific, searchable terms.

**Example:**
```
Original:  "Tell me about the second chapter"
Rewritten: "Chapter 2 content topics concepts key points summary"

Original:  "What did the author say about neural nets?"
Rewritten: "author neural networks deep learning architecture layers training"
```

**Prompt template:**
```
Rewrite this student question to maximise retrieval from a textbook.
Add synonyms and related terms. Keep under 40 words.
Return only the rewritten query.
```

---

### Layer 3 — 🔎 Semantic Retrieval (FAISS)

```
Module: _semantic_scores()
```

**What it does:** Converts the query into a 384-dimensional vector using `all-MiniLM-L6-v2` (via ONNX/fastembed), then finds the most semantically similar document chunks using Facebook's FAISS index.

**Technical details:**
- **Embedding model:** `all-MiniLM-L6-v2` (384 dimensions, L2-normalized)
- **Runtime:** ONNX (fastembed) — no PyTorch required, ~80 MB RAM
- **Index type:** `IndexFlatIP` (inner product on L2-normalized vectors = cosine similarity)
- **Returns:** `{chunk_index → cosine_score}` for top-K results

**Why FAISS?** It finds chunks that are *conceptually* similar, even if they use different words. "Machine learning" matches "ML algorithms" and "artificial intelligence training."

---

### Layer 4 — 📝 Lexical Retrieval (BM25)

```
Module: _bm25_scores()
```

**What it does:** Token-level keyword matching using the BM25 (Okapi) algorithm. This catches *exact terms* that semantic search might miss.

**Why BM25 alongside FAISS?** Semantic search is great for meaning, but it can miss:
- Specific names, dates, numbers, acronyms
- Exact technical terms ("TCP/IP", "RSA-2048")
- Rare words not well-represented in the embedding model

**BM25 fills this gap** by scoring based on term frequency, inverse document frequency, and document length normalization.

---

### Layer 5 — ⚡ Hybrid Score Fusion

```
Module: hybrid_retrieve()
```

**What it does:** Merges results from FAISS and BM25 into a single ranked list using weighted score fusion.

**Formula:**
```
final_score = 0.6 × semantic_score + 0.4 × bm25_score (normalized)
```

**Why 60/40?** Semantic understanding is more important for most academic queries, but lexical matching provides crucial precision for specific terms. This ratio was empirically tuned.

**Process:**
1. Get top-K from FAISS (semantic scores)
2. Get all BM25 scores (lexical scores)
3. Normalize BM25 scores to 0-1 range
4. Fuse scores with 60/40 weighting
5. Sort by final fused score
6. Return top results with source metadata attached

---

### Layer 6 — 🎯 MMR Diversification

```
Module: mmr_select()
```

**What it does:** Applies **Maximum Marginal Relevance** to ensure the selected chunks are both *relevant* and *diverse*. Without this, you might get 5 chunks that all say the same thing.

**Formula:**
```
MMR_score = λ × relevance(chunk, query) − (1−λ) × max_similarity(chunk, selected)
```
- **λ = 0.7** — Favors relevance while still enforcing diversity
- Iteratively selects the chunk that maximizes this score
- Returns a **diversity score** (0-1) measuring how diverse the final selection is

**Example:**
```
Without MMR: 5 chunks all about "neural network layers" (page 12, 13, 14)
With MMR:    Chunks about "layers" + "training" + "backprop" + "activation" + "loss"
```

---

### Layer 7 — 📦 Structured Context Assembly

```
Module: build_structured_context()
```

**What it does:** Formats the selected chunks into a structured context block that helps the LLM understand where each piece of information comes from.

**Output format:**
```
[Source 1]
Source: machine_learning.pdf
Page: 42
Section: Neural Network Architecture
Content:
A neural network consists of layers of interconnected nodes...

[Source 2]
Source: machine_learning.pdf
Page: 67
Section: Backpropagation
Content:
The backpropagation algorithm computes gradients...
```

**Why structure it?** Raw concatenated text confuses LLMs. Structured context with source labels enables:
- Accurate citation generation
- Better answer grounding
- Page-level reference tracking

---

### Layer 8 — 🤖 LLM Answer Generation

```
Module: generate_answer_with_gemini()
```

**What it does:** Sends the structured context + user query to the LLM (Gemini or Groq) with a carefully tuned system prompt.

**System prompt enforces:**
- Answer ONLY using the provided context
- Cite sources with `[Source N]` notation
- If information isn't in context, say "not found in the document"
- Use clear, educational language

**Dual LLM support:**
- **Google Gemini** (`gemini-2.0-flash`) — default, high quality
- **Groq** (`llama-3.3-70b-versatile`) — fallback, faster inference

---

### Layer 9 — ✅ Reflection Agent (Self-Verification)

```
Module: reflection_agent()
```

**What it does:** A second LLM call that acts as a **fact-checker**. It reviews the generated answer against the original context to verify that every claim is actually supported.

**Verification prompt:**
```
Review this answer against the context. For each claim:
1. Is it directly supported by the context? 
2. Is anything fabricated or assumed?

If the answer is fully grounded → respond "VALIDATED"
If not → regenerate a corrected answer using ONLY the context
```

**Outcomes:**
- `VALIDATED` → Answer passes, +0.25 confidence bonus
- `Corrected` → New answer replaces the original, no bonus

**This is the key anti-hallucination layer.** Even if the LLM invents something plausible, the reflection agent catches it.

---

### Layer 10 — 📊 Advanced Confidence Scoring

```
Module: calculate_confidence_v4()
```

**What it does:** Produces a final 0.0-1.0 confidence score based on 6 weighted factors.

| Factor | Weight | What It Measures |
|--------|--------|------------------|
| **Citation count** | 0.20 | More citations = more grounded |
| **Answer quality** | 0.10 | Word count 40-600 = ideal length |
| **Retrieval score** | 0.20 | Average score from hybrid retrieval |
| **MMR diversity** | 0.15 | How diverse the source chunks are |
| **Reflection validated** | 0.25 | Did the reflection agent approve? |
| **Structured citations** | 0.10 | Page numbers present in citations |
| **Total** | **1.00** | |

**Interpretation:**
- **0.85+** → High confidence, well-grounded answer
- **0.60-0.85** → Moderate confidence, answer likely correct
- **Below 0.60** → Low confidence, might need better documents

---

## 🚀 The 5 Pipeline Modes

Each mode activates different layers of the pipeline depending on the use case.

### Mode Activation Matrix

```mermaid
graph TD
    subgraph Auto["🤖 AUTO MODE"]
        A1[Classify Query] --> A2{Query Type?}
        A2 -->|Greeting| ChatM[Chat Pipeline]
        A2 -->|Simple Q| FastM[Fast Pipeline]
        A2 -->|Complex| ResM[Research Pipeline]
        A2 -->|Study/Exam| StudyM[Study Pipeline]
    end

    style Auto fill:#f0f9ff,stroke:#3b82f6,stroke-width:2px
```

### Layers Used Per Mode

| Layer | 💬 Chat | ⚡ Fast | 🔬 Research | 📚 Study | 🤖 Auto |
|-------|---------|--------|-------------|----------|---------|
| Language Detection | ✅ | ✅ | ✅ | ✅ | ✅ |
| Query Classification | ❌ | ❌ | ✅ | ❌ | ✅ |
| Query Rewriting | ❌ | ❌ | ✅ | ❌ | Depends |
| FAISS Retrieval | ❌ | ✅ | ✅ | ❌ | Depends |
| BM25 Retrieval | ❌ | ❌ | ✅ | ❌ | Depends |
| Hybrid Fusion | ❌ | ❌ | ✅ | ❌ | Depends |
| MMR Diversification | ❌ | ❌ | ✅ | ❌ | Depends |
| Structured Context | ❌ | Basic | ✅ | Full Doc | Depends |
| Reflection Agent | ❌ | ❌ | ✅ | ❌ | Depends |
| Confidence Scoring | Static | Basic | ✅ Full | ✅ Full | Depends |

---

### 💬 Chat Mode — Pure Conversational AI

```mermaid
graph LR
    Q[Student Query] --> D[Language Detect]
    D --> LLM[LLM with<br/>Conversation History]
    LLM --> A[Friendly Response]

    style Q fill:#10b981,color:#fff
    style A fill:#10b981,color:#fff
```

**Use case:** Greetings, small talk, asking what StudyAI can do.  
**Layers active:** 2 of 10 (Language Detection → Direct LLM)  
**Speed:** ~500ms  
**Special behavior:** If documents ARE uploaded, auto-upgrades to Research mode so the chatbot can discuss PDF content.

---

### ⚡ Fast Mode — Speed-Optimized RAG

```mermaid
graph LR
    Q[Student Query] --> D[Language Detect]
    D --> F[FAISS Only<br/>Top 3 Chunks]
    F --> CTX[Simple Context<br/>Assembly]
    CTX --> LLM[LLM<br/>Concise Answer]
    LLM --> A[Quick Answer<br/>+ Citations]

    style Q fill:#f59e0b,color:#fff
    style A fill:#f59e0b,color:#fff
```

**Use case:** Quick factual lookups ("What is on page 5?", "Define X").  
**Layers active:** 4 of 10 (Language → FAISS → Context → LLM)  
**Speed:** ~1-2s  
**Key details:**
- **No BM25** — saves ~200ms
- **No query rewriting** — saves LLM call
- **No reflection** — saves second LLM call
- Top 3 chunks only, answer capped at 120 words
- Confidence: `0.50 + avg_score × 0.40` (max 0.88)

---

### 🔬 Research Mode — Full Agentic Pipeline

```mermaid
graph LR
    Q[Student Query] --> D[Language Detect]
    D --> CL[Classification]
    CL --> RW[Query Rewriting<br/>Agent]
    RW --> F[FAISS<br/>Semantic]
    RW --> B[BM25<br/>Lexical]
    F --> HY[Hybrid Fusion<br/>0.6 Sem + 0.4 Lex]
    B --> HY
    HY --> MMR[MMR<br/>Diversification]
    MMR --> CTX[Structured<br/>Context]
    CTX --> LLM[LLM Answer<br/>Generation]
    LLM --> REF[Reflection<br/>Agent]
    REF --> CONF[6-Factor<br/>Confidence]
    CONF --> A[Research Answer<br/>+ Citations<br/>+ Confidence]

    style Q fill:#6366f1,color:#fff
    style A fill:#6366f1,color:#fff
```

**Use case:** Complex analytical questions, multi-concept queries, deep research.  
**Layers active:** ALL 10 layers  
**Speed:** ~3-5s  
**Key details:**
- Full hybrid retrieval with query rewriting
- MMR ensures diverse source coverage
- Reflection agent validates factual grounding
- 6-factor confidence scoring
- Detailed page-level citations

---

### 📚 Study Mode — Full-Document Synthesis

```mermaid
graph LR
    Q[Student Query] --> D[Language Detect]
    D --> ALL[Gather ALL<br/>Document Chunks]
    ALL --> SORT[Sort by<br/>Page Order]
    SORT --> DEDUP[Deduplicate<br/>Pages]
    DEDUP --> LLM[LLM Study Guide<br/>Generation]
    LLM --> A["📋 Table of Contents<br/>📚 Topic Summaries<br/>⭐ Key Concepts<br/>📖 Reading Plan<br/>❓ Practice Questions"]

    style Q fill:#8b5cf6,color:#fff
    style A fill:#8b5cf6,color:#fff
```

**Use case:** Exam preparation, document overview, topic mastery.  
**Layers active:** Specialized (bypasses normal retrieval)  
**Speed:** ~5-8s (processes entire document)  
**Key details:**
- **Does NOT use FAISS/BM25** — reads the ENTIRE document
- Chunks sorted in reading order (by page number)
- Pages deduplicated and capped at ~800 chars each
- Special study prompt generates 5-section output:
  1. Table of Contents with page numbers
  2. Topic-by-topic summaries
  3. Key concepts, formulas, definitions
  4. Recommended reading plan with page ranges
  5. Potential exam questions
- **Dynamic persona mode**: If the student asks to "solve", "evaluate", or act as a specific persona (e.g., "university topper"), the study prompt adapts accordingly

---

### 🤖 Auto Mode — Intelligent Routing

```mermaid
graph TD
    Q[Student Query] --> IS_CASUAL{Casual<br/>Pattern?}
    IS_CASUAL -->|Yes| CHAT[💬 Chat]
    IS_CASUAL -->|No| STUDY_CHECK{Study<br/>Trigger?}
    STUDY_CHECK -->|Yes| STUDY[📚 Study]
    STUDY_CHECK -->|No| LLM_CLASSIFY[LLM Classifies<br/>Intent]
    LLM_CLASSIFY -->|chat| CHAT
    LLM_CLASSIFY -->|fast| UPGRADE{Has<br/>Docs?}
    LLM_CLASSIFY -->|research| RESEARCH[🔬 Research]
    LLM_CLASSIFY -->|study| STUDY
    UPGRADE -->|Yes| RESEARCH
    UPGRADE -->|No| FAST[⚡ Fast]

    style Q fill:#ec4899,color:#fff
    style CHAT fill:#10b981,color:#fff
    style FAST fill:#f59e0b,color:#fff
    style RESEARCH fill:#6366f1,color:#fff
    style STUDY fill:#8b5cf6,color:#fff
```

**How Auto-Detection works (3-stage):**

1. **Rule-based check:** Pattern matching against 30+ casual phrases
2. **Keyword triggers:** Checks for study-mode trigger phrases ("study guide", "key topics", "exam prep")
3. **LLM classification:** If rules don't match, asks the LLM: *"Classify: chat / fast / research / study?"*
4. **Smart upgrade:** If `fast` is detected but documents are uploaded, auto-upgrades to `research` for full context

---

## 📄 Document Processing Pipeline

When a PDF is uploaded, it goes through its own pipeline before any queries can use it:

```mermaid
graph LR
    PDF[PDF Upload] --> EXT[Page-by-Page<br/>Text Extraction]
    EXT --> SEC[Section<br/>Detection]
    SEC --> CHUNK[Hierarchical<br/>Chunking]
    CHUNK --> EMB[fastembed<br/>ONNX Embedding]
    EMB --> FAISS[FAISS Index<br/>Build]
    CHUNK --> TOK[Tokenization]
    TOK --> BM25[BM25 Index<br/>Build]
    CHUNK --> DB[(PostgreSQL<br/>Storage)]

    style PDF fill:#ef4444,color:#fff
    style FAISS fill:#3b82f6,color:#fff
    style BM25 fill:#22c55e,color:#fff
    style DB fill:#a855f7,color:#fff
```

**Chunking strategy:**
- **Window size:** 800 words per chunk
- **Overlap:** 150 words between chunks (prevents information loss at boundaries)
- Each chunk preserves: `doc_id`, `page_num`, `section`, `start_pos`, `end_pos`
- Section headers detected heuristically from first line of each chunk
- **Content-hash doc IDs:** `doc_` + SHA-256 prefix → deterministic, deduplication-friendly

**Session-document linking:**
- Documents are linked to chat sessions (both in-memory and persisted to DB)
- Queries are scoped to session-specific documents for multi-session isolation

---

## 📝 AI Exam Evaluation System

StudyAI includes a dedicated **AI exam grading** feature with isolated LLM keys to prevent token budget conflicts with the RAG pipeline.

```mermaid
graph LR
    Q[Question +<br/>Student Answer] --> MODE{Grading<br/>Mode?}
    MODE -->|Lenient| L[Supportive<br/>Grading]
    MODE -->|Moderate| M[Fair University<br/>Professor]
    MODE -->|Strict| S[Strict<br/>Evaluator]
    L --> LLM[Evaluation LLM]
    M --> LLM
    S --> LLM
    LLM --> R["Score (0-10)<br/>Strengths<br/>Missing Concepts<br/>Improvements<br/>Model Answer"]

    style Q fill:#f43f5e,color:#fff
    style R fill:#f43f5e,color:#fff
```

### Features
- **3 grading modes:** Lenient (supportive), Moderate (fair), Strict (penalizes gaps)
- **Reference material support:** Upload PDF/DOCX as grading reference
- **Structured output:** Score, strengths, missing concepts, improvements, model answer
- **Separate LLM keys:** `EVAL_GEMINI_API_KEY` / `EVAL_GROQ_API_KEY` isolate evaluation budget
- **Text extraction:** Supports PDF (via pdfplumber) and DOCX input

---

## 📚 Study Materials Hub

A topic-based AI learning center with 5 specialized tools:

| Tool | Output | Format |
|------|--------|--------|
| 📖 **Study Guide** | Comprehensive overview, prerequisites, key concepts, formulas, learning path, revision points | Markdown |
| 🃏 **Flashcards** | 12 question-answer cards with difficulty levels | JSON array |
| 📋 **Quiz** | 10 questions (7 MCQ + 3 short answer) with explanations | JSON array |
| 🗺️ **Concept Map** | Hierarchical topic tree with descriptions | JSON tree |
| 📎 **Resources** | 10 curated resources (videos, courses, books, tools) | JSON array |

- All tools can be **enhanced with uploaded PDF content** for document-grounded material
- Requires authentication (user-scoped)
- Dynamic topic suggestions based on user's query history

---

## 🔐 Authentication System

### Three Authentication Flows

**1. Email + OTP Registration:**
```
Register → OTP Email → Verify Code → JWT Token → Dashboard
```

**2. Google OAuth (One-Click):**
```
Click "Sign in with Google" → Google Popup → ID Token → Backend Verifies → JWT → Dashboard
```

**3. Forgot Password:**
```
Enter Email → OTP Email → Enter Code → Set New Password → Login
```

### Security Features
- **bcrypt** password hashing (12 rounds)
- **JWT** tokens with 24h expiry
- **6-digit OTP** codes with 10-minute expiry
- Google ID token verification via `oauth2.googleapis.com/tokeninfo`
- CORS whitelisting for frontend origins
- Unverified accounts blocked from login

---

## 📊 Learning Progress Dashboard

Per-user analytics powered by query history:

| Metric | Description |
|--------|-------------|
| **Total Questions** | Number of queries asked |
| **Avg Confidence** | Mean confidence across all answers |
| **Study Streak** | Consecutive days of activity |
| **Study Time** | Estimated minutes spent studying |
| **Documents Uploaded** | Number of PDFs uploaded |
| **Topic Mastery** | Per-topic progress with question count and avg confidence |
| **Weekly Activity** | Last 7 days of query activity |
| **Recommendations** | AI-generated study suggestions |
| **Reflection Rate** | Percentage of answers that passed reflection validation |

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **PostgreSQL** (NeonDB or local)

### 1. Backend Setup

```bash
cd backend

# Install dependencies
pip install -r requirements-render.txt

# Create .env from template
cp .env.example .env
# Edit .env with your keys

# Run the server
python production_agentic.py
```

Server: `http://localhost:8000` | Docs: `http://localhost:8000/docs`

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

### 3. Deploy to Render (Backend)

1. Push code to GitHub
2. Create new **Web Service** on Render
3. Set **Build Command:** `pip install -r requirements-render.txt`
4. Set **Start Command:** `uvicorn production_agentic:app --host 0.0.0.0 --port $PORT --workers 1 --timeout-keep-alive 120`
5. Add all environment variables from `.env`
6. Deploy (free tier works — `fastembed` keeps RAM under 512 MB)

### 4. Deploy to Netlify (Frontend)

1. Connect repository to Netlify
2. Set **Base directory:** `frontend`
3. Set **Build command:** `npm install && npm run build`
4. Set **Publish directory:** `frontend/dist`
5. Set **Node version:** `20`
6. Add environment variable: `VITE_API_URL=https://your-render-url.onrender.com`

---

## 🔧 Environment Variables

```env
# ═══════════════ LLM (RAG Pipeline) ═══════════════
GEMINI_API_KEY=AIza...                    # Google Gemini API key
GEMINI_MODEL=gemini-2.0-flash-exp         # Model for RAG pipeline
LLM_PROVIDER=gemini                       # "gemini" or "groq"
GROQ_API_KEY=gsk_...                      # Groq API key (optional fallback)
GROQ_MODEL=llama-3.3-70b-versatile        # Groq model name

# ═══════════════ LLM (Evaluation — Isolated Keys) ═══════════════
EVAL_LLM_PROVIDER=gemini                  # Separate provider for exam grading
EVAL_GEMINI_API_KEY=AIza...               # Separate Gemini key for evaluation
EVAL_GROQ_API_KEY=gsk_...                 # Separate Groq key for evaluation

# ═══════════════ Database (NeonDB / PostgreSQL) ═══════════════
DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
POSTGRES_HOST=your-neon-hostname.neon.tech
POSTGRES_PORT=5432
POSTGRES_USER=your-username
POSTGRES_PASSWORD=your-password
POSTGRES_DB=course_qa

# ═══════════════ Auth ═══════════════
SECRET_KEY=your-random-secret-key         # JWT signing key
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-...

# ═══════════════ Email (OTP Verification) ═══════════════
SMTP_EMAIL=your-email@gmail.com
SMTP_PASSWORD=your-app-password           # Gmail App Password (not login password)

# ═══════════════ Server ═══════════════
HOST=0.0.0.0
PORT=8000
DEBUG=True
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

---

## 📡 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/register` | Register new account → sends OTP email |
| `POST` | `/api/v1/auth/verify-email` | Verify 6-digit OTP code |
| `POST` | `/api/v1/auth/login` | Login (verified accounts only) |
| `POST` | `/api/v1/auth/google` | Google OAuth one-click login |
| `POST` | `/api/v1/auth/forgot-password` | Send password reset OTP |
| `POST` | `/api/v1/auth/reset-password` | Reset password with OTP |
| `GET`  | `/api/v1/auth/me` | Get current user profile |

### RAG Pipeline
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/query/ask` | Ask a question (supports 5 modes: auto/fast/study/research/chat) |
| `POST` | `/api/v1/documents/upload` | Upload PDF document |
| `GET`  | `/api/v1/documents` | List all uploaded documents |
| `DELETE` | `/api/v1/documents/{doc_id}` | Delete a document |
| `GET`  | `/api/v1/query/history` | Recent query history |

### Chat History
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/chat/sessions` | Create new chat session |
| `GET`  | `/api/v1/chat/sessions` | List user's chat sessions |
| `GET`  | `/api/v1/chat/sessions/{id}/messages` | Get messages for a session |
| `DELETE` | `/api/v1/chat/sessions/{id}` | Delete a chat session |

### AI Evaluation
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/evaluate` | Grade an exam answer (JSON input) |
| `POST` | `/api/v1/evaluate/with-reference` | Grade with reference material file |
| `POST` | `/api/v1/extract-text` | Extract text from PDF/DOCX |

### Study Materials
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/study-materials/generate` | Generate study material (guide/flashcards/quiz/concepts/resources) |
| `GET`  | `/api/v1/study-materials/topics` | Get topic suggestions for user |

### Analytics & Progress
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/v1/progress` | Per-user learning progress dashboard |
| `GET`  | `/api/v1/analytics` | Global analytics |
| `POST` | `/api/v1/feedback` | Submit feedback on query quality |
| `GET`  | `/api/v1/health` | Health check + system status |

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **LLM** | Gemini 2.0 Flash / Groq Llama 3.3 70B | Answer generation, query rewriting, reflection |
| **Embeddings** | all-MiniLM-L6-v2 (via fastembed/ONNX) | 384-dim sentence vectors, ~80 MB RAM |
| **Vector Search** | FAISS (IndexFlatIP) | Cosine semantic similarity |
| **Keyword Search** | BM25 (Okapi) | Lexical retrieval |
| **Backend** | FastAPI + Uvicorn | ASGI web server |
| **Database** | PostgreSQL (NeonDB Serverless) | Persistent storage |
| **PDF Parsing** | pypdf + pdfplumber | Text extraction |
| **Auth** | JWT + bcrypt + Google OAuth 2.0 | Authentication |
| **Email** | aiosmtplib (Gmail SMTP) | OTP verification |
| **Translation** | langdetect + deep-translator | Multilingual support |
| **Frontend** | React 18 + TypeScript + Vite | User interface |
| **Styling** | TailwindCSS | Design system |
| **Frontend Hosting** | Netlify | CDN + auto-deploy |
| **Backend Hosting** | Render (Free Tier) | Container hosting |

---

## 📂 Project Structure

```
backend/
├── production_agentic.py       # 🧠 Main app: 10-layer RAG pipeline + all routes
├── auth.py                     # 🔑 JWT verification + Google OAuth helper
├── routes_auth.py              # 🔐 Auth endpoints (register, login, OTP, Google, reset)
├── routes_chat_history.py      # 💬 Chat session CRUD
├── routes_evaluation.py        # 📝 AI exam grading endpoints
├── routes_progress.py          # 📊 Per-user learning progress dashboard
├── routes_study_materials.py   # 📚 AI study material generation (5 tools)
├── db_postgres.py              # 💾 PostgreSQL/NeonDB persistence layer
├── llm_provider.py             # 🤖 LLM abstraction (Gemini / Groq) for RAG
├── llm_eval_provider.py        # 🤖 LLM abstraction for evaluation (separate keys)
├── email_service.py            # 📧 SMTP email service for OTP
├── requirements.txt            # 📦 Full local dependencies (incl. PyTorch)
├── requirements-render.txt     # 📦 Render deployment deps (fastembed, no PyTorch)
├── start.sh                    # 🚀 Render start script
├── netlify.toml                # 🌐 Netlify frontend build config
├── .env.example                # ⚙️ Environment variable template
├── .env                        # ⚙️ Active configuration (not committed)
├── .gitignore                  # 🙈 Git ignore rules
│
├── screenshots/                # 📸 UI screenshots for README
│   ├── chat_dashboard.png
│   ├── login.png
│   ├── signup.png
│   ├── otp_verify.png
│   ├── pdf_upload_autodetect.png
│   ├── research_mode_answer.png
│   ├── study_mode_guide.png
│   ├── multilingual_hindi.png
│   ├── progress_dashboard.png
│   └── study_materials.png
│
└── frontend/                   # 🖥️ React + TypeScript + Vite App
    ├── netlify.toml
    ├── package.json
    ├── tailwind.config.js
    ├── vite.config.ts
    └── src/
        ├── main.tsx                          # App entry point
        ├── App.tsx                           # Router + page layout
        ├── index.css                         # Global styles
        ├── contexts/
        │   └── AuthContext.tsx               # JWT auth state management
        ├── services/
        │   └── api.ts                        # Centralized API client
        ├── components/
        │   ├── MarkdownRenderer.tsx          # Rich markdown rendering
        │   └── ReplyPreview.tsx              # Chat reply preview
        └── pages/
            ├── ChatPage.tsx                  # Main chat + PDF upload interface
            ├── LoginPage.tsx                 # Email/password + Google login
            ├── SignupPage.tsx                # Registration with OTP verification
            ├── ForgotPasswordPage.tsx        # Password reset flow
            ├── DashboardPage.tsx             # Learning analytics dashboard
            ├── StudyMaterialsPage.tsx        # AI study material generation
            └── EvaluatePage.tsx              # AI exam answer evaluation
```

---

## 📸 Screenshots

### Authentication

<p align="center">
  <img src="screenshots/login.png" width="380" alt="Login Page" />
  <img src="screenshots/signup.png" width="380" alt="Signup Page" />
</p>
<p align="center">
  <img src="screenshots/otp_verify.png" width="380" alt="OTP Verification" />
</p>

### Chat Interface — PDF Upload & Auto-Detect Pipeline

<p align="center">
  <img src="screenshots/pdf_upload_autodetect.png" width="800" alt="PDF Upload with Auto Pipeline Detection" />
</p>

### Research Mode — Grounded Answers with Page Citations

<p align="center">
  <img src="screenshots/research_mode_answer.png" width="800" alt="Research Mode Answer with Citations" />
</p>

### Study Mode — Full Exam Preparation Guide

<p align="center">
  <img src="screenshots/study_mode_guide.png" width="800" alt="Study Mode - Table of Contents and Topic Summaries" />
</p>

### Multilingual Support — Hindi Query on English PDF

<p align="center">
  <img src="screenshots/multilingual_hindi.png" width="800" alt="Multilingual Response in Hindi" />
</p>

### Learning Progress Dashboard

<p align="center">
  <img src="screenshots/progress_dashboard.png" width="800" alt="Progress Dashboard with Topic Mastery" />
</p>

### Study Materials — Flashcards, Practice Tests & More

<p align="center">
  <img src="screenshots/study_materials.png" width="800" alt="Study Materials Page" />
</p>

---

## 👥 Team

Built at **KIIT University** as a Major Project (8th Semester).

---

## 📄 License

This project is developed for academic purposes at KIIT University.

---

<p align="center">
  Built with ❤️ at KIIT University · StudyAI © 2026
</p>