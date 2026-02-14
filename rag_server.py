"""
REAL RAG Backend with Gemini API and PDF Processing
This version actually processes PDFs and generates real AI responses
"""
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import uvicorn
import time
import os
from dotenv import load_dotenv
import google.generativeai as genai
from pypdf import PdfReader
import tempfile

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file!")

genai.configure(api_key=GEMINI_API_KEY)

# Create FastAPI app
app = FastAPI(
    title="AI Tutor RAG Backend",
    description="Production RAG Backend with Gemini API",
    version="2.0.0"
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    print(f"\n[REQUEST] {request.method} {request.url.path}")
    response = await call_next(request)
    duration = time.time() - start_time
    print(f"[RESPONSE] {request.method} {request.url.path} - {response.status_code} ({duration:.2f}s)\n")
    return response

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory document storage (simple version)
# In production, this would be a vector database
documents_store: Dict[str, Dict] = {}

# Models
class Message(BaseModel):
    role: str
    content: str

class QueryRequest(BaseModel):
    query: str
    conversation_history: Optional[List[Message]] = []
    options: Optional[dict] = {}

class Citation(BaseModel):
    text: str
    source: str
    page: Optional[int] = None
    confidence: float

class QueryMetadata(BaseModel):
    query_type: Optional[str] = "rag"
    retrieval_strategy: str = "semantic"
    chunks_retrieved: int = 0
    chunks_used: int = 0
    attempts: int = 1
    tokens_used: int = 0
    retrieval_time_ms: float = 0
    generation_time_ms: float = 0
    total_time_ms: float = 0

class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation]
    confidence: float
    metadata: QueryMetadata
    cached: bool = False
    cache_hit_similarity: Optional[float] = None

# Helper Functions
def extract_text_from_pdf(pdf_file) -> tuple[str, int]:
    """Extract all text from a PDF file"""
    reader = PdfReader(pdf_file)
    text = ""
    page_count = len(reader.pages)
    
    for page_num, page in enumerate(reader.pages):
        page_text = page.extract_text()
        text += f"\n\n--- Page {page_num + 1} ---\n\n{page_text}"
    
    return text, page_count

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[Dict]:
    """Simple text chunking"""
    chunks = []
    words = text.split()
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append({
                "text": chunk,
                "start_pos": i,
                "end_pos": i + len(chunk.split())
            })
    
    return chunks

def find_relevant_chunks(query: str, chunks: List[Dict], top_k: int = 3) -> List[Dict]:
    """Simple keyword-based retrieval (in production, use embeddings)"""
    # Simple scoring based on keyword overlap
    query_words = set(query.lower().split())
    
    scored_chunks = []
    for chunk in chunks:
        chunk_words = set(chunk["text"].lower().split())
        overlap = len(query_words & chunk_words)
        if overlap > 0:
            scored_chunks.append({
                **chunk,
                "score": overlap / len(query_words)
            })
    
    # Sort by score and return top_k
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    return scored_chunks[:top_k]

async def generate_answer_with_gemini(query: str, context: str, conversation_history: List[Message]) -> Dict:
    """Generate answer using Gemini API"""
    
    # Build prompt with context (embedded in first message for older API)
    system_prompt = f"""You are an AI tutor helping students understand their course materials. 
You have access to the following context from uploaded documents:

{context}

Based on this context, answer the student's question accurately and helpfully. 
Always cite the specific parts of the context you use to answer.
If the answer is not in the context, say so clearly."""

    # Build conversation for Gemini
    messages = []
    
    # Add conversation history
    for msg in conversation_history[-5:]:  # Last 5 messages for context
        messages.append({
            "role": "user" if msg.role == "user" else "model",
            "parts": [msg.content]
        })
    
    # Add current query with system prompt embedded
    if not messages:
        # First message - include system prompt
        messages.append({
            "role": "user",
            "parts": [f"{system_prompt}\n\nStudent Question: {query}"]
        })
    else:
        # Has history - just add query
        messages.append({
            "role": "user",
            "parts": [query]
        })
    
    # Create model (without system_instruction for older API)
    model = genai.GenerativeModel(model_name=GEMINI_MODEL)
    
    # Generate response
    start_time = time.time()
    response = await model.generate_content_async(messages)
    generation_time = (time.time() - start_time) * 1000
    
    # Extract usage info
    try:
        tokens_used = response.usage_metadata.total_token_count
    except:
        tokens_used = 0
    
    return {
        "answer": response.text,
        "generation_time_ms": generation_time,
        "tokens_used": tokens_used
    }

# Routes
@app.get("/")
async def root():
    return {
        "service": "AI Tutor RAG Backend",
        "version": "2.0.0",
        "status": "operational",
        "message": "Real RAG pipeline with Gemini API",
        "features": [
            "PDF Upload & Processing",
            "Real AI Responses (Gemini)",
            "Document-based Q&A",
            "Citation Support"
        ],
        "docs": "/docs"
    }

@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "gemini_configured": bool(GEMINI_API_KEY),
        "documents_loaded": len(documents_store)
    }

@app.post("/api/v1/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and process a PDF document"""
    print(f"[UPLOAD] Processing file: {file.filename}")
    
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    start_time = time.time()
    
    try:
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Extract text from PDF
        text, page_count = extract_text_from_pdf(temp_path)
        
        # Clean up temp file
        os.unlink(temp_path)
        
        # Chunk the text
        chunks = chunk_text(text)
        
        # Store in memory (with simple ID)
        doc_id = f"doc_{len(documents_store) + 1}"
        documents_store[doc_id] = {
            "filename": file.filename,
            "text": text,
            "chunks": chunks,
            "page_count": page_count,
            "uploaded_at": time.time()
        }
        
        processing_time = (time.time() - start_time) * 1000
        
        print(f"[UPLOAD] Success: {file.filename} - {page_count} pages, {len(chunks)} chunks")
        
        return {
            "status": "success",
            "message": f"Document '{file.filename}' uploaded and processed successfully!",
            "document_id": doc_id,
            "pages": page_count,
            "chunks_created": len(chunks),
            "processing_time_ms": processing_time
        }
        
    except Exception as e:
        print(f"[UPLOAD ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

@app.post("/api/v1/query/ask", response_model=QueryResponse)
async def ask_question(request: QueryRequest):
    """Ask a question using RAG pipeline"""
    print(f"[QUERY] {request.query}")
    
    total_start = time.time()
    
    try:
        # Check if we have any documents
        if not documents_store:
            return QueryResponse(
                answer="Please upload a PDF document first! I need course materials to answer your questions.",
                citations=[],
                confidence=0.0,
                metadata=QueryMetadata(
                    chunks_retrieved=0,
                    chunks_used=0,
                    total_time_ms=0
                )
            )
        
        # Retrieve relevant chunks from all documents
        retrieval_start = time.time()
        all_relevant_chunks = []
        
        for doc_id, doc_data in documents_store.items():
            relevant = find_relevant_chunks(request.query, doc_data["chunks"], top_k=2)
            for chunk in relevant:
                all_relevant_chunks.append({
                    **chunk,
                    "source": doc_data["filename"],
                    "doc_id": doc_id
                })
        
        # Sort all chunks by score and take top 3
        all_relevant_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_chunks = all_relevant_chunks[:3]
        
        retrieval_time = (time.time() - retrieval_start) * 1000
        
        # Build context from retrieved chunks
        context = "\n\n---\n\n".join([
            f"From {chunk['source']}:\n{chunk['text']}"
            for chunk in top_chunks
        ])
        
        # Generate answer using Gemini
        result = await generate_answer_with_gemini(
            request.query,
            context,
            request.conversation_history
        )
        
        # Create citations
        citations = [
            Citation(
                text=chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"],
                source=chunk["source"],
                page=None,  # Simple version doesn't track page numbers
                confidence=chunk.get("score", 0.5)
            )
            for chunk in top_chunks
        ]
        
        total_time = (time.time() - total_start) * 1000
        
        print(f"[QUERY] Success - {len(citations)} citations, {result['tokens_used']} tokens")
        
        return QueryResponse(
            answer=result["answer"],
            citations=citations,
            confidence=0.85 if citations else 0.5,
            metadata=QueryMetadata(
                query_type="rag",
                retrieval_strategy="keyword",
                chunks_retrieved=len(all_relevant_chunks),
                chunks_used=len(top_chunks),
                tokens_used=result["tokens_used"],
                retrieval_time_ms=retrieval_time,
                generation_time_ms=result["generation_time_ms"],
                total_time_ms=total_time
            ),
            cached=False
        )
        
    except Exception as e:
        print(f"[QUERY ERROR] {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process query: {str(e)}")

@app.get("/api/v1/progress")
async def get_progress():
    """Get learning progress"""
    return {
        "total_questions": 0,  # Would track in production
        "study_streak": 0,
        "total_time": 0,
        "avg_confidence": 0.85,
        "topics_discussed": len(documents_store),
        "documents_uploaded": len(documents_store)
    }

@app.post("/api/v1/feedback")
async def submit_feedback(query_id: str, helpful: bool, comment: Optional[str] = None):
    """Submit feedback"""
    print(f"[FEEDBACK] Helpful: {helpful}, Comment: {comment}")
    return {
        "status": "success",
        "message": "Thank you for your feedback!"
    }

if __name__ == "__main__":
    print("=" * 60)
    print("Starting REAL RAG Backend with Gemini API...")
    print("=" * 60)
    print(f"Gemini Model: {GEMINI_MODEL}")
    print(f"API Key configured: {'Yes' if GEMINI_API_KEY else 'No'}")
    print("Server will run on: http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
