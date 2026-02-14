"""
Database Models - SQLAlchemy ORM models
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, 
    Boolean, ForeignKey, JSON, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()


def generate_uuid():
    """Generate UUID string"""
    return str(uuid.uuid4())


class Tenant(Base):
    """Tenant/Organization"""
    __tablename__ = "tenants"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    
    # Settings
    settings = Column(JSON, default={})
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = relationship("User", back_populates="tenant")
    documents = relationship("Document", back_populates="tenant")
    query_logs = relationship("QueryLog", back_populates="tenant")


class User(Base):
    """User accounts"""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    
    # Auth
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    permissions = Column(JSON, default=[])
    
    # API Keys
    api_keys = relationship("APIKey", back_populates="user")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    query_logs = relationship("QueryLog", back_populates="user")
    feedback = relationship("Feedback", back_populates="user")
    
    __table_args__ = (
        Index('ix_users_tenant_email', 'tenant_id', 'email'),
    )


class APIKey(Base):
    """API Keys for authentication"""
    __tablename__ = "api_keys"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")


class Document(Base):
    """Uploaded documents"""
    __tablename__ = "documents"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer)
    
    # Storage
    s3_key = Column(String(500))
    s3_bucket = Column(String(255))
    
    # Processing status
    status = Column(String(50), default="pending", index=True)  # pending, processing, completed, failed
    error_message = Column(Text)
    
    # Metadata
    metadata = Column(JSON, default={})
    
    # Statistics
    chunk_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = Column(DateTime)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_documents_tenant_status', 'tenant_id', 'status'),
    )


class DocumentChunk(Base):
    """Document chunks stored in vector DB"""
    __tablename__ = "document_chunks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    
    # Chunk data
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    
    # Vector DB reference
    vector_id = Column(String(255), index=True)  # ID in Qdrant
    
    # Metadata
    page_number = Column(Integer)
    metadata = Column(JSON, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
    
    __table_args__ = (
        Index('ix_chunks_document_index', 'document_id', 'chunk_index'),
    )


class QueryLog(Base):
    """Query logs for analytics and active learning"""
    __tablename__ = "query_logs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    
    # Query data
    query = Column(Text, nullable=False)
    answer = Column(Text)
    
    # Classification
    query_type = Column(String(50), index=True)
    retrieval_strategy = Column(String(50))
    
    # Metrics
    confidence = Column(Float)
    chunks_retrieved = Column(Integer)
    chunks_used = Column(Integer)
    tokens_used = Column(Integer)
    
    retrieval_time_ms = Column(Float)
    generation_time_ms = Column(Float)
    total_time_ms = Column(Float)
    
    # Caching
    was_cached = Column(Boolean, default=False)
    cache_hit_similarity = Column(Float)
    
    # Status
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    
    # Metadata
    metadata = Column(JSON, default={})
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="query_logs")
    user = relationship("User", back_populates="query_logs")
    feedback = relationship("Feedback", back_populates="query_log", uselist=False)
    
    __table_args__ = (
        Index('ix_query_logs_tenant_created', 'tenant_id', 'created_at'),
    )


class Feedback(Base):
    """User feedback for active learning"""
    __tablename__ = "feedback"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    query_log_id = Column(String(36), ForeignKey("query_logs.id"), nullable=False, unique=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    
    # Feedback data
    rating = Column(String(20), nullable=False)  # positive, negative, neutral
    comment = Column(Text)
    
    # Issues (multi-select)
    issues = Column(JSON, default=[])  # ["inaccurate", "incomplete", "irrelevant", "other"]
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    query_log = relationship("QueryLog", back_populates="feedback")
    user = relationship("User", back_populates="feedback")
    
    __table_args__ = (
        Index('ix_feedback_rating_created', 'rating', 'created_at'),
    )


class CircuitBreakerState(Base):
    """Circuit breaker state persistence"""
    __tablename__ = "circuit_breaker_states"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    service_name = Column(String(100), unique=True, nullable=False, index=True)
    
    state = Column(String(20), default="closed")  # closed, open, half_open
    failure_count = Column(Integer, default=0)
    last_failure_time = Column(DateTime)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)