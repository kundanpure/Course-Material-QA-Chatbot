"""
Health Check API Routes
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict
from datetime import datetime

from core.logging import logger
from services.cache_service import cache_service
from services.retrieval_service import retrieval_service

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    version: str = "2.0.0"


class DetailedHealthResponse(BaseModel):
    """Detailed health check response"""
    status: str
    timestamp: str
    version: str
    services: Dict[str, str]


@router.get("/", response_model=HealthResponse)
async def health_check():
    """
    Basic health check
    Returns 200 if service is alive
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat()
    )


@router.get("/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check():
    """
    Detailed health check - checks all dependencies
    Returns status of each service
    """
    services = {}
    overall_status = "healthy"
    
    # Check Redis
    try:
        if cache_service.redis_client:
            await cache_service.redis_client.ping()
            services["redis"] = "healthy"
        else:
            services["redis"] = "not_initialized"
    except Exception as e:
        services["redis"] = "unhealthy"
        overall_status = "degraded"
        logger.error(f"Redis health check failed: {e}")
    
    # Check Qdrant
    try:
        if retrieval_service._initialized:
            collections = await retrieval_service.qdrant_client.get_collections()
            services["qdrant"] = "healthy"
        else:
            services["qdrant"] = "not_initialized"
    except Exception as e:
        services["qdrant"] = "unhealthy"
        overall_status = "degraded"
        logger.error(f"Qdrant health check failed: {e}")
    
    # Check Neo4j
    try:
        if retrieval_service.neo4j_driver:
            async with retrieval_service.neo4j_driver.session() as session:
                await session.run("RETURN 1")
            services["neo4j"] = "healthy"
        else:
            services["neo4j"] = "not_initialized"
    except Exception as e:
        services["neo4j"] = "unhealthy"
        overall_status = "degraded"
        logger.error(f"Neo4j health check failed: {e}")
    
    # Check LLM providers (just config check, not actual API call)
    from core.config import settings
    services["openai"] = "configured" if settings.OPENAI_API_KEY else "not_configured"
    services["groq"] = "configured" if settings.GROQ_API_KEY else "not_configured"
    
    return DetailedHealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        version="2.0.0",
        services=services
    )


@router.get("/ready")
async def readiness_check():
    """
    Kubernetes readiness probe
    Returns 200 only if all critical services are ready
    """
    try:
        # Check critical services
        if not retrieval_service._initialized:
            return {"status": "not_ready", "reason": "retrieval_service_not_initialized"}, 503
        
        if not cache_service.redis_client:
            return {"status": "not_ready", "reason": "redis_not_initialized"}, 503
        
        # Quick health check
        await cache_service.redis_client.ping()
        
        return {"status": "ready"}
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {"status": "not_ready", "reason": str(e)}, 503


@router.get("/live")
async def liveness_check():
    """
    Kubernetes liveness probe
    Returns 200 if service is alive (even if degraded)
    """
    return {"status": "alive"}