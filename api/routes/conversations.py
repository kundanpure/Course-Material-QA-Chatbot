"""
Conversation API Routes - Manage contextual chat sessions
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from db.session import get_db
from services.conversation_service import ConversationService
from api.deps import get_current_user
from core.logging import logger

router = APIRouter()


# Request/Response Models
class CreateSessionRequest(BaseModel):
    document_id: Optional[str] = None
    title: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    title: str
    document_id: Optional[str]
    message_count: int
    last_message_at: str
    created_at: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    tokens_used: Optional[int]
    confidence: Optional[float]
    citations: List[dict] = []


@router.post("/sessions", response_model=SessionResponse)
async def create_conversation_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new conversation session
    """
    service = ConversationService(db)
    
    session = await service.create_session(
        user_id=current_user["user_id"],
        tenant_id=current_user["tenant_id"],
        document_id=request.document_id,
        title=request.title
    )
    
    return {
        "id": session.id,
        "title": session.title,
        "document_id": session.document_id,
        "message_count": 0,
        "last_message_at": session.last_message_at.isoformat(),
        "created_at": session.created_at.isoformat()
    }


@router.get("/sessions", response_model=List[SessionResponse])
async def get_user_sessions(
    active_only: bool = True,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all conversation sessions for current user
    """
    service = ConversationService(db)
    
    sessions = await service.get_user_sessions(
        user_id=current_user["user_id"],
        active_only=active_only,
        limit=limit
    )
    
    return [
        {
            "id": s.id,
            "title": s.title,
            "document_id": s.document_id,
            "message_count": len(s.messages) if hasattr(s, 'messages') else 0,
            "last_message_at": s.last_message_at.isoformat(),
            "created_at": s.created_at.isoformat()
        }
        for s in sessions
    ]


@router.get("/sessions/{session_id}/history", response_model=List[MessageResponse])
async def get_conversation_history(
    session_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get conversation history for a session
    """
    service = ConversationService(db)
    
    # TODO: Add ownership check
    messages = await service.get_conversation_history(session_id, limit)
    
    return messages


@router.delete("/sessions/{session_id}")
async def delete_conversation(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Delete (soft delete) a conversation session
    """
    service = ConversationService(db)
    
    # TODO: Add ownership check
    await service.delete_session(session_id)
    
    return {"message": "Session deleted successfully"}


@router.get("/sessions/{session_id}/stats")
async def get_session_stats(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get statistics for a conversation session
    """
    service = ConversationService(db)
    
    # TODO: Add ownership check
    stats = await service.get_session_stats(session_id)
    
    return stats
