"""
Production-grade Course Material QA Chatbot - Main Application
Features: Semantic Caching, Circuit Breaker, GraphRAG, Multi-tenancy
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from core.config import settings
from core.middleware import (
    RequestLoggingMiddleware,
    PrometheusMiddleware,
    CircuitBreakerMiddleware
)
from core.exceptions import AppException
from core.logging import setup_logging, logger
from api.routes import query, health, feedback, admin
from observability.metrics import metrics_registry
from services.cache_service import cache_service
from db.session import init_db, close_db

# Setup logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for the application"""
    logger.info("🚀 Starting Course QA Chatbot Service...")
    
    # Initialize database
    await init_db()
    
    # Initialize cache
    await cache_service.initialize()
    
    # Warm up models (optional)
    logger.info("✅ Application started successfully")
    
    yield
    
    # Cleanup
    logger.info("🛑 Shutting down...")
    await cache_service.close()
    await close_db()
    logger.info("✅ Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Production-grade RAG system with GraphRAG, Adaptive Retrieval, and Self-Healing capabilities",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middleware (Order matters!)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_middleware(CircuitBreakerMiddleware)  # Innovation: Auto-fallback on failures

# Exception Handlers
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handle custom application exceptions"""
    logger.error(f"Application error: {exc.detail}", extra={
        "error_code": exc.status_code,
        "path": request.url.path
    })
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "code": exc.error_code,
            "request_id": request.state.request_id if hasattr(request.state, "request_id") else None
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "code": "INTERNAL_ERROR",
            "request_id": request.state.request_id if hasattr(request.state, "request_id") else None
        }
    )

# Include routers
app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])
app.include_router(query.router, prefix="/api/v1/query", tags=["Query"])
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Feedback"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])

# Metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return Response(generate_latest(metrics_registry), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "service": settings.PROJECT_NAME,
        "version": "2.0.0",
        "status": "operational",
        "features": [
            "GraphRAG (Hybrid Vector + Knowledge Graph)",
            "Semantic Caching (GPTCache + Redis)",
            "Adaptive Retrieval Router",
            "Self-Healing Query Pipeline",
            "Multi-tenant Data Isolation",
            "Circuit Breaker Pattern",
            "Active Learning Loop",
            "Deep Observability (Traces + Metrics)"
        ],
        "docs": "/api/docs"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_config=None  # Use custom logging
    )