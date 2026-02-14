"""
Conversation Session Management - Contextual Chat with Memory
Tracks conversation history per user/session for contextual responses
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
import uuid

from db.models import Base, generate_uuid


class ConversationSession(Base):
    """Conversation sessions for contextual chat"""
    __tablename__ = "conversation_sessions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    
    # Session info
    title = Column(String(255))  # Auto-generated from first query
    document_id = Column(String(36), ForeignKey("documents.id"), index=True)  # Context document
    
    # Session settings
    is_active = Column(Boolean, default=True)
    metadata = Column(JSON, default={})  # Store custom settings like temperature, model, etc.
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    messages = relationship("ConversationMessage", back_populates="session", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_sessions_user_active', 'user_id', 'is_active', 'updated_at'),
        Index('ix_sessions_document', 'document_id', 'is_active'),
    )


class ConversationMessage(Base):
    """Individual messages in a conversation"""
    __tablename__ = "conversation_messages"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("conversation_sessions.id"), nullable=False, index=True)
    
    # Message data
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    
    # Metadata
    tokens_used = Column(Integer)
    model_used = Column(String(100))
    confidence = Column(Float)
    
    # Citations (if assistant message)
    citations = Column(JSON, default=[])
    
    # Query metadata (if user message)
    query_type = Column(String(50))
    retrieval_strategy = Column(String(50))
    
    # Performance metrics
    generation_time_ms = Column(Float)
    was_cached = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    session = relationship("ConversationSession", back_populates="messages")
    
    __table_args__ = (
        Index('ix_messages_session_created', 'session_id', 'created_at'),
    )
