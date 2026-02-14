"""
Repository Layer - Data access patterns
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    User, Tenant, APIKey, Document, DocumentChunk,
    QueryLog, Feedback, CircuitBreakerState
)
from core.security import SecurityService
from core.logging import logger


class UserRepository:
    """User-related database operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def create(
        self,
        email: str,
        password: str,
        tenant_id: str,
        full_name: Optional[str] = None,
        is_superuser: bool = False
    ) -> User:
        """Create new user"""
        user = User(
            email=email,
            hashed_password=SecurityService.hash_password(password),
            tenant_id=tenant_id,
            full_name=full_name,
            is_superuser=is_superuser
        )
        
        self.session.add(user)
        await self.session.flush()
        
        logger.info(f"User created: {email}")
        return user
    
    async def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate API key and return user/tenant info"""
        key_hash = SecurityService.hash_password(api_key)
        
        result = await self.session.execute(
            select(APIKey, User, Tenant)
            .join(User, APIKey.user_id == User.id)
            .join(Tenant, User.tenant_id == Tenant.id)
            .where(
                and_(
                    APIKey.key_hash == key_hash,
                    APIKey.is_active == True,
                    User.is_active == True,
                    Tenant.is_active == True
                )
            )
        )
        
        row = result.first()
        if not row:
            return None
        
        api_key_obj, user, tenant = row
        
        # Update last used
        api_key_obj.last_used = datetime.utcnow()
        await self.session.flush()
        
        return {
            "user_id": user.id,
            "tenant_id": tenant.id,
            "permissions": user.permissions or []
        }


class DocumentRepository:
    """Document-related database operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        tenant_id: str,
        filename: str,
        file_type: str,
        file_size: int,
        s3_key: str,
        metadata: Optional[Dict] = None
    ) -> Document:
        """Create document record"""
        document = Document(
            tenant_id=tenant_id,
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            s3_key=s3_key,
            metadata=metadata or {},
            status="pending"
        )
        
        self.session.add(document)
        await self.session.flush()
        
        logger.info(f"Document created: {filename}")
        return document
    
    async def update_status(
        self,
        document_id: str,
        status: str,
        error_message: Optional[str] = None,
        chunk_count: Optional[int] = None
    ):
        """Update document processing status"""
        result = await self.session.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        
        if document:
            document.status = status
            document.error_message = error_message
            if chunk_count is not None:
                document.chunk_count = chunk_count
            if status == "completed":
                document.processed_at = datetime.utcnow()
            
            await self.session.flush()
    
    async def list_by_tenant(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Document]:
        """List documents for tenant"""
        result = await self.session.execute(
            select(Document)
            .where(Document.tenant_id == tenant_id)
            .order_by(desc(Document.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def add_chunks(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]]
    ):
        """Add chunks for a document"""
        chunk_objects = []
        for i, chunk_data in enumerate(chunks):
            chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=i,
                text=chunk_data["text"],
                vector_id=chunk_data.get("vector_id"),
                page_number=chunk_data.get("page"),
                metadata=chunk_data.get("metadata", {})
            )
            chunk_objects.append(chunk)
        
        self.session.add_all(chunk_objects)
        await self.session.flush()
        
        logger.info(f"Added {len(chunks)} chunks for document {document_id}")


class QueryLogRepository:
    """Query log operations for analytics"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def log_query(
        self,
        query: str,
        answer: str,
        confidence: float,
        metadata: Dict[str, Any],
        tenant_id: str,
        user_id: str,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> QueryLog:
        """Log a query for analytics and active learning"""
        query_log = QueryLog(
            tenant_id=tenant_id,
            user_id=user_id,
            query=query,
            answer=answer,
            confidence=confidence,
            query_type=metadata.get("query_type"),
            retrieval_strategy=metadata.get("retrieval_strategy"),
            chunks_retrieved=metadata.get("chunks_retrieved"),
            chunks_used=metadata.get("chunks_used"),
            tokens_used=metadata.get("tokens_used"),
            retrieval_time_ms=metadata.get("retrieval_time_ms"),
            generation_time_ms=metadata.get("generation_time_ms"),
            total_time_ms=metadata.get("total_time_ms"),
            was_cached=metadata.get("cached", False),
            success=success,
            error_message=error_message,
            metadata=metadata
        )
        
        self.session.add(query_log)
        await self.session.flush()
        
        return query_log
    
    async def get_by_id(self, query_log_id: str) -> Optional[QueryLog]:
        """Get query log by ID"""
        result = await self.session.execute(
            select(QueryLog).where(QueryLog.id == query_log_id)
        )
        return result.scalar_one_or_none()
    
    async def get_analytics(
        self,
        tenant_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get query analytics for tenant"""
        since = datetime.utcnow() - timedelta(days=days)
        
        # Total queries
        total_result = await self.session.execute(
            select(func.count(QueryLog.id))
            .where(
                and_(
                    QueryLog.tenant_id == tenant_id,
                    QueryLog.created_at >= since
                )
            )
        )
        total_queries = total_result.scalar()
        
        # Average confidence
        avg_confidence_result = await self.session.execute(
            select(func.avg(QueryLog.confidence))
            .where(
                and_(
                    QueryLog.tenant_id == tenant_id,
                    QueryLog.created_at >= since
                )
            )
        )
        avg_confidence = avg_confidence_result.scalar() or 0.0
        
        # Cache hit rate
        cache_hits_result = await self.session.execute(
            select(func.count(QueryLog.id))
            .where(
                and_(
                    QueryLog.tenant_id == tenant_id,
                    QueryLog.created_at >= since,
                    QueryLog.was_cached == True
                )
            )
        )
        cache_hits = cache_hits_result.scalar()
        cache_hit_rate = (cache_hits / total_queries * 100) if total_queries > 0 else 0.0
        
        # Query types distribution
        query_types_result = await self.session.execute(
            select(QueryLog.query_type, func.count(QueryLog.id))
            .where(
                and_(
                    QueryLog.tenant_id == tenant_id,
                    QueryLog.created_at >= since
                )
            )
            .group_by(QueryLog.query_type)
        )
        query_types = {row[0]: row[1] for row in query_types_result.all()}
        
        return {
            "total_queries": total_queries,
            "avg_confidence": float(avg_confidence),
            "cache_hit_rate": cache_hit_rate,
            "query_types": query_types,
            "period_days": days
        }


class FeedbackRepository:
    """Feedback operations for active learning"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def add_feedback(
        self,
        query_log_id: str,
        user_id: str,
        rating: str,
        comment: Optional[str] = None,
        issues: Optional[List[str]] = None
    ) -> Feedback:
        """Add user feedback"""
        feedback = Feedback(
            query_log_id=query_log_id,
            user_id=user_id,
            rating=rating,
            comment=comment,
            issues=issues or []
        )
        
        self.session.add(feedback)
        await self.session.flush()
        
        logger.info(f"Feedback added for query {query_log_id}: {rating}")
        return feedback
    
    async def get_negative_feedback(
        self,
        tenant_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get negative feedback for active learning
        Returns queries that need improvement
        """
        result = await self.session.execute(
            select(QueryLog, Feedback)
            .join(Feedback, QueryLog.id == Feedback.query_log_id)
            .where(
                and_(
                    QueryLog.tenant_id == tenant_id,
                    Feedback.rating == "negative"
                )
            )
            .order_by(desc(Feedback.created_at))
            .limit(limit)
        )
        
        items = []
        for query_log, feedback in result.all():
            items.append({
                "query": query_log.query,
                "answer": query_log.answer,
                "confidence": query_log.confidence,
                "feedback_comment": feedback.comment,
                "issues": feedback.issues,
                "created_at": feedback.created_at
            })
        
        return items


class CircuitBreakerRepository:
    """Circuit breaker state persistence"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_state(self, service_name: str) -> Optional[CircuitBreakerState]:
        """Get circuit breaker state"""
        result = await self.session.execute(
            select(CircuitBreakerState)
            .where(CircuitBreakerState.service_name == service_name)
        )
        return result.scalar_one_or_none()
    
    async def update_state(
        self,
        service_name: str,
        state: str,
        failure_count: int = 0,
        last_failure_time: Optional[datetime] = None
    ):
        """Update circuit breaker state"""
        cb_state = await self.get_state(service_name)
        
        if cb_state:
            cb_state.state = state
            cb_state.failure_count = failure_count
            cb_state.last_failure_time = last_failure_time
        else:
            cb_state = CircuitBreakerState(
                service_name=service_name,
                state=state,
                failure_count=failure_count,
                last_failure_time=last_failure_time
            )
            self.session.add(cb_state)
        
        await self.session.flush()