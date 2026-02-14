"""
Feedback API Routes - Active Learning
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import get_current_user, TenantContext
from core.logging import logger
from db.session import get_db
from db.repository import FeedbackRepository, QueryLogRepository
from observability.metrics import answer_confidence

router = APIRouter()


class FeedbackRequest(BaseModel):
    """Feedback submission"""
    query_id: str = Field(..., description="Query log ID")
    rating: str = Field(..., description="positive, negative, or neutral")
    comment: Optional[str] = Field(None, description="Optional feedback comment")
    issues: Optional[List[str]] = Field(
        default=[],
        description="Issues: inaccurate, incomplete, irrelevant, slow, other"
    )


class FeedbackResponse(BaseModel):
    """Feedback response"""
    success: bool
    message: str


@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    context: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit feedback for a query
    
    This data is used for:
    - Active learning (improving the model)
    - Analytics (understanding user satisfaction)
    - Identifying problematic queries
    """
    
    try:
        # Validate rating
        if request.rating not in ["positive", "negative", "neutral"]:
            raise HTTPException(
                status_code=400,
                detail="Rating must be 'positive', 'negative', or 'neutral'"
            )
        
        # Verify query belongs to tenant
        query_repo = QueryLogRepository(db)
        query_log = await query_repo.get_by_id(request.query_id)
        
        if not query_log:
            raise HTTPException(
                status_code=404,
                detail="Query not found"
            )
        
        if query_log.tenant_id != context.tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )
        
        # Add feedback
        feedback_repo = FeedbackRepository(db)
        await feedback_repo.add_feedback(
            query_log_id=request.query_id,
            user_id=context.user_id,
            rating=request.rating,
            comment=request.comment,
            issues=request.issues
        )
        
        # Record metric
        answer_confidence.labels(
            tenant_id=context.tenant_id
        ).observe(query_log.confidence or 0.0)
        
        logger.info(
            f"Feedback submitted",
            extra={
                "query_id": request.query_id,
                "rating": request.rating,
                "tenant_id": context.tenant_id
            }
        )
        
        return FeedbackResponse(
            success=True,
            message="Thank you for your feedback!"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to submit feedback"
        )


@router.get("/analytics")
async def get_feedback_analytics(
    context: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get feedback analytics for active learning
    Requires admin permission
    """
    
    if not context.has_permission("admin"):
        raise HTTPException(
            status_code=403,
            detail="Admin permission required"
        )
    
    try:
        feedback_repo = FeedbackRepository(db)
        
        # Get queries with negative feedback for improvement
        negative_feedback = await feedback_repo.get_negative_feedback(
            tenant_id=context.tenant_id,
            limit=50
        )
        
        # Get query analytics
        query_repo = QueryLogRepository(db)
        analytics = await query_repo.get_analytics(
            tenant_id=context.tenant_id,
            days=30
        )
        
        return {
            "negative_feedback_count": len(negative_feedback),
            "negative_feedback_samples": negative_feedback[:10],
            "query_analytics": analytics
        }
        
    except Exception as e:
        logger.error(f"Failed to get analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve analytics"
        )