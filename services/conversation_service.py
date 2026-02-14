"""
Conversation Service - Manages chat sessions with contextual memory
Innovation: Persistent conversation history per document/topic
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.conversation_models import ConversationSession, ConversationMessage
from core.logging import logger


class ConversationService:
    """
    Manages conversation sessions and message history
    
    Features:
    - Persistent conversation history
    - Auto-session creation per document
    - Context window management
    - Conversation title auto-generation
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_session(
        self,
        user_id: str,
        tenant_id: str,
        document_id: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> ConversationSession:
        """Create a new conversation session"""
        
        session_obj = ConversationSession(
            user_id=user_id,
            tenant_id=tenant_id,
            document_id=document_id,
            title=title or "New Conversation",
            metadata=metadata or {}
        )
        
        self.session.add(session_obj)
        await self.session.commit()
        await self.session.refresh(session_obj)
        
        logger.info(f"Created conversation session {session_obj.id} for user {user_id}")
        return session_obj
    
    async def get_or_create_session(
        self,
        user_id: str,
        tenant_id: str,
        document_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> ConversationSession:
        """Get existing session or create new one"""
        
        # If session_id provided, get that session
        if session_id:
            result = await self.session.execute(
                select(ConversationSession).where(
                    and_(
                        ConversationSession.id == session_id,
                        ConversationSession.user_id == user_id,
                        ConversationSession.is_active == True
                    )
                )
            )
            session_obj = result.scalar_one_or_none()
            if session_obj:
                return session_obj
        
        # If document_id provided, get active session for that document
        if document_id:
            result = await self.session.execute(
                select(ConversationSession).where(
                    and_(
                        ConversationSession.user_id == user_id,
                        ConversationSession.document_id == document_id,
                        ConversationSession.is_active == True
                    )
                ).order_by(desc(ConversationSession.last_message_at)).limit(1)
            )
            session_obj = result.scalar_one_or_none()
            if session_obj:
                return session_obj
        
        # Create new session
        return await self.create_session(
            user_id=user_id,
            tenant_id=tenant_id,
            document_id=document_id
        )
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        **metadata
    ) -> ConversationMessage:
        """Add a message to conversation"""
        
        message = ConversationMessage(
            session_id=session_id,
            role=role,
            content=content,
            **metadata
        )
        
        self.session.add(message)
        
        # Update session last_message_at
        await self.session.execute(
            ConversationSession.__table__.update().where(
                ConversationSession.id == session_id
            ).values(last_message_at=datetime.utcnow())
        )
        
        await self.session.commit()
        await self.session.refresh(message)
        
        return message
    
    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """
        Get conversation history formatted for LLM
        Returns list of {role, content} dicts
        """
        
        result = await self.session.execute(
            select(ConversationMessage).where(
                ConversationMessage.session_id == session_id
            ).order_by(ConversationMessage.created_at).limit(limit)
        )
        
        messages = result.scalars().all()
        
        return [
            {
                "role": msg.role,
                "content": msg.content
            }
            for msg in messages
        ]
    
    async def get_user_sessions(
        self,
        user_id: str,
        active_only: bool = True,
        limit: int = 20
    ) -> List[ConversationSession]:
        """Get all sessions for a user"""
        
        query = select(ConversationSession).where(
            ConversationSession.user_id == user_id
        )
        
        if active_only:
            query = query.where(ConversationSession.is_active == True)
        
        query = query.order_by(desc(ConversationSession.last_message_at)).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def update_session_title(
        self,
        session_id: str,
        title: str
    ):
        """Update session title"""
        
        await self.session.execute(
            ConversationSession.__table__.update().where(
                ConversationSession.id == session_id
            ).values(title=title)
        )
        
        await self.session.commit()
    
    async def auto_generate_title(
        self,
        session_id: str,
        first_query: str
    ) -> str:
        """Auto-generate conversation title from first query"""
        
        # Simple title generation - first 60 chars of query
        title = first_query[:60] + ("..." if len(first_query) > 60 else "")
        
        await self.update_session_title(session_id, title)
        return title
    
    async def delete_session(self, session_id: str):
        """Soft delete a session"""
        
        await self.session.execute(
            ConversationSession.__table__.update().where(
                ConversationSession.id == session_id
            ).values(is_active=False)
        )
        
        await self.session.commit()
    
    async def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for a session"""
        
        result = await self.session.execute(
            select(ConversationMessage).where(
                ConversationMessage.session_id == session_id
            )
        )
        
        messages = result.scalars().all()
        
        total_tokens = sum(msg.tokens_used or 0 for msg in messages)
        avg_confidence = sum(msg.confidence or 0 for msg in messages if msg.role == "assistant") / max(1, sum(1 for msg in messages if msg.role == "assistant"))
        
        return {
            "message_count": len(messages),
            "total_tokens": total_tokens,
            "average_confidence": avg_confidence,
            "cache_hit_rate": sum(1 for msg in messages if msg.was_cached) / max(1, len(messages))
        }


# Dependency injection helper
async def get_conversation_service(session: AsyncSession) -> ConversationService:
    """Get conversation service instance"""
    return ConversationService(session)
