"""
Minimal FastAPI server for frontend testing
This is a simplified version that doesn't require all dependencies
"""
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import time

# Create FastAPI app
app = FastAPI(
    title="AI Tutor API",
    description="Backend API for AI Tutor Application",
    version="1.0.0"
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

# CORS Configuration - Allow frontend access (Development mode - permissive)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=False,  # Don't require credentials for simplicity
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    query_type: Optional[str] = "simple"
    retrieval_strategy: str = "semantic"
    chunks_retrieved: int = 5
    chunks_used: int = 3
    attempts: int = 1
    tokens_used: int = 150
    retrieval_time_ms: float = 45.5
    generation_time_ms: float = 234.2
    total_time_ms: float = 279.7

class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation]
    confidence: float
    metadata: QueryMetadata
    cached: bool = False
    cache_hit_similarity: Optional[float] = None

# Routes
@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "service": "AI Tutor Backend",
        "version": "1.0.0",
        "status": "operational",
        "message": "Backend is running! Frontend can now connect.",
        "docs": "/docs"
    }

@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "Backend is up and running"
    }

@app.post("/api/v1/query/ask", response_model=QueryResponse)
async def ask_question(request: QueryRequest):
    """
    Main endpoint: Ask a question to the AI assistant
    This is a MOCK version for frontend testing
    """
    # Mock response
    answer = f"""Great question! You asked: "{request.query}"

This is a mock response from the backend. In production, this would:
1. Process your PDF documents
2. Search through relevant course materials
3. Generate an AI-powered answer with citations
4. Return confidence scores and metadata

The full RAG pipeline is ready to be integrated once you upload documents!"""

    citations = [
        Citation(
            text="This is a sample citation from your course materials",
            source="sample_document.pdf",
            page=42,
            confidence=0.92
        ),
        Citation(
            text="Another relevant excerpt from your materials",
            source="lecture_notes.pdf", 
            page=15,
            confidence=0.87
        )
    ]

    metadata = QueryMetadata()

    return QueryResponse(
        answer=answer,
        citations=citations,
        confidence=0.89,
        metadata=metadata,
        cached=False
    )

@app.get("/api/v1/progress")
async def get_progress():
    """Get learning progress - Mock data"""
    return {
        "total_questions": 47,
        "study_streak": 7,
        "total_time": 124,
        "avg_confidence": 0.85,
        "topics_discussed": 12
    }

@app.post("/api/v1/feedback")
async def submit_feedback(query_id: str, helpful: bool, comment: Optional[str] = None):
    """Submit feedback on an answer"""
    return {
        "status": "success",
        "message": "Feedback received. Thank you!"
    }

@app.post("/api/v1/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a PDF document - Mock version"""
    print(f"[UPLOAD] Received file: {file.filename}")
    
    # In production, this would:
    # 1. Save file to storage (S3/local)
    # 2. Extract text from PDF
    # 3. Chunk the content
    # 4. Generate embeddings
    # 5. Store in vector database
    # 6. Create knowledge graph
    
    return {
        "status": "success",
        "message": f"Document '{file.filename}' uploaded successfully! (Mock)",
        "document_id": "doc_12345",
        "pages": 42,
        "chunks_created": 85,
        "processing_time_ms": 1234.5
    }

if __name__ == "__main__":
    print("=" * 60)
    print("Starting AI Tutor Backend Server...")
    print("=" * 60)
    print("Server will run on: http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("Frontend connection: ENABLED")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
