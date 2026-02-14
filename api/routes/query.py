"""
Query API Routes - Main endpoint for question answering
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from core.security import get_current_user, TenantContext, check_prompt_injection
from core.logging import logger
from agents.orchestrator import orchestrator
from observability.metrics import query_requests_total, query_duration_seconds
import time

router = APIRouter()


class ConversationMessage(BaseModel):
    """Single message in conversation history"""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class QueryRequest(BaseModel):
    """Request model for query endpoint"""
    query: str = Field(
        ...,
        description="User's question",
        min_length=1,
        max_length=2000,
        examples=["What is the difference between supervised and unsupervised learning?"]
    )
    conversation_history: Optional[List[ConversationMessage]] = Field(
        default=[],
        description="Previous conversation messages for context",
        max_length=20
    )
    options: Optional[dict] = Field(
        default={},
        description="Optional query parameters (temperature, max_tokens, etc.)"
    )


class Citation(BaseModel):
    """Citation/source reference"""
    text: str
    source: str
    page: Optional[int] = None
    confidence: float


class QueryMetadata(BaseModel):
    """Metadata about query processing"""
    query_type: Optional[str]
    retrieval_strategy: str
    chunks_retrieved: int
    chunks_used: int
    attempts: int
    tokens_used: int
    retrieval_time_ms: float
    generation_time_ms: float
    total_time_ms: float


class QueryResponse(BaseModel):
    """Response model for query endpoint"""
    answer: str
    citations: List[Citation]
    confidence: float
    metadata: QueryMetadata
    cached: bool = False
    cache_hit_similarity: Optional[float] = None


@router.post("/ask", response_model=QueryResponse)
async def ask_question(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    context: TenantContext = Depends(get_current_user)
):
    """
    Main endpoint: Ask a question about course materials
    
    Innovation features:
    - Semantic caching (instant response for similar queries)
    - Adaptive retrieval (chooses best strategy automatically)
    - Self-healing (retries with different approach if validation fails)
    - Circuit breaker protection
    
    Returns:
    - answer: Generated answer with citations
    - confidence: How confident the system is (0-1)
    - metadata: Processing details and performance metrics
    """
    
    start_time = time.time()
    
    try:
        # Security: Check for prompt injection
        sanitized_query = await check_prompt_injection(request.query)
        
        logger.info(
            f"Query received",
            extra={
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
                "query_length": len(sanitized_query)
            }
        )
        
        # Convert conversation history
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.conversation_history
        ]
        
        # Process query through orchestrator
        result = await orchestrator.process_query(
            query=sanitized_query,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            conversation_history=history
        )
        
        # Record metrics
        duration = time.time() - start_time
        
        query_requests_total.labels(
            tenant_id=context.tenant_id,
            cached=str(result.get("cached", False))
        ).inc()
        
        query_duration_seconds.labels(
            tenant_id=context.tenant_id
        ).observe(duration)
        
        # Log active learning event in background
        if not result.get("cached"):
            background_tasks.add_task(
                log_query_for_learning,
                query=sanitized_query,
                result=result,
                tenant_id=context.tenant_id,
                user_id=context.user_id
            )
        
        logger.info(
            f"Query completed",
            extra={
                "tenant_id": context.tenant_id,
                "cached": result.get("cached", False),
                "confidence": result.get("confidence"),
                "duration_ms": round(duration * 1000, 2)
            }
        )
        
        return QueryResponse(**result)
        
    except Exception as e:
        logger.error(
            f"Query processing failed",
            exc_info=True,
            extra={
                "tenant_id": context.tenant_id,
                "error": str(e)
            }
        )
        
        query_requests_total.labels(
            tenant_id=context.tenant_id,
            cached="error"
        ).inc()
        
        raise HTTPException(
            status_code=500,
            detail="Failed to process query. Please try again."
        )


@router.post("/ask/stream")
async def ask_question_stream(
    request: QueryRequest,
    context: TenantContext = Depends(get_current_user)
):
    """
    Streaming version of ask endpoint
    Returns answer in real-time as it's generated
    """
    from fastapi.responses import StreamingResponse
    
    # TODO: Implement streaming response
    # This would use SSE (Server-Sent Events) to stream the answer
    
    raise HTTPException(
        status_code=501,
        detail="Streaming not yet implemented"
    )


async def log_query_for_learning(
    query: str,
    result: dict,
    tenant_id: str,
    user_id: str
):
    """
    Background task: Log query for active learning
    Innovation: Build dataset from real user queries
    """
    try:
        from db.repository import QueryLogRepository
        
        repo = QueryLogRepository()
        await repo.log_query(
            query=query,
            answer=result["answer"],
            confidence=result["confidence"],
            metadata=result["metadata"],
            tenant_id=tenant_id,
            user_id=user_id
        )
        
    except Exception as e:
        logger.error(f"Failed to log query for learning: {e}")
        # Don't fail the request if logging fails