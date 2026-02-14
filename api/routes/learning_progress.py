"""
Learning Progress API Routes
"""
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.learning_progress_service import LearningProgressService
from api.deps import get_current_user

router = APIRouter()


# Request Models
class KnowledgeGapRequest(BaseModel):
    curriculum: List[str]  # List of topics that should be covered


@router.get("/dashboard")
async def get_learning_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get comprehensive learning progress dashboard
    """
    service = LearningProgressService(db)
    
    dashboard = await service.get_learning_dashboard(
        user_id=current_user["user_id"],
        tenant_id=current_user["tenant_id"]
    )
    
    return dashboard


@router.post("/knowledge-gaps")
async def identify_knowledge_gaps(
    request: KnowledgeGapRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Identify knowledge gaps based on curriculum
    """
    service = LearningProgressService(db)
    
    gaps = await service.identify_knowledge_gaps(
        user_id=current_user["user_id"],
        tenant_id=current_user["tenant_id"],
        curriculum=request.curriculum
    )
    
    return gaps


@router.get("/recommendations")
async def get_study_recommendations(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get personalized study recommendations
    """
    service = LearningProgressService(db)
    
    recommendations = await service.get_study_recommendations(
        user_id=current_user["user_id"],
        tenant_id=current_user["tenant_id"]
    )
    
    return {"recommendations": recommendations}


@router.get("/analytics")
async def get_performance_analytics(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get performance analytics over time
    """
    service = LearningProgressService(db)
    
    analytics = await service.get_performance_analytics(
        user_id=current_user["user_id"],
        tenant_id=current_user["tenant_id"],
        days=days
    )
    
    return analytics
