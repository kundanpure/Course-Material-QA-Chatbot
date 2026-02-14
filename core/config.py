"""
Core Configuration - Production-grade settings with environment management
"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator
import os
from functools import lru_cache


class Settings(BaseSettings):
    """Application Settings"""
    
    # Application
    PROJECT_NAME: str = "Course Material QA Chatbot"
    VERSION: str = "2.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    ENVIRONMENT: str = Field(default="production", env="ENVIRONMENT")
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    
    # Security
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000"],
        env="ALLOWED_ORIGINS"
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60
    API_KEY_HEADER: str = "X-API-Key"
    
    # Database - PostgreSQL (Optional - for production)
    POSTGRES_HOST: Optional[str] = Field(default="localhost", env="POSTGRES_HOST")
    POSTGRES_PORT: int = Field(default=5432, env="POSTGRES_PORT")
    POSTGRES_USER: Optional[str] = Field(default="postgres", env="POSTGRES_USER")
    POSTGRES_PASSWORD: Optional[str] = Field(default="postgres", env="POSTGRES_PASSWORD")
    POSTGRES_DB: Optional[str] = Field(default="courseqa", env="POSTGRES_DB")
    DATABASE_URL: Optional[str] = Field(default=None, env="DATABASE_URL")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40
    
    # Redis - Caching & Message Broker (Optional)
    REDIS_HOST: Optional[str] = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    CACHE_TTL: int = 3600  # 1 hour
    SEMANTIC_CACHE_THRESHOLD: float = 0.95  # Innovation: Similarity threshold for cache hits
    
    # Vector Database - Qdrant (Optional)
    QDRANT_HOST: Optional[str] = Field(default="localhost", env="QDRANT_HOST")
    QDRANT_PORT: int = Field(default=6333, env="QDRANT_PORT")
    QDRANT_API_KEY: Optional[str] = Field(default=None, env="QDRANT_API_KEY")
    QDRANT_COLLECTION_NAME: str = "course_materials"
    VECTOR_DIMENSION: int = 1536  # OpenAI ada-002 or text-embedding-3-small
    
    # Knowledge Graph - Neo4j (Optional)
    NEO4J_URI: Optional[str] = Field(default="bolt://localhost:7687", env="NEO4J_URI")
    NEO4J_USER: str = Field(default="neo4j", env="NEO4J_USER")
    NEO4J_PASSWORD: Optional[str] = Field(default="neo4j", env="NEO4J_PASSWORD")
    
    # LLM Configuration - Multi-provider with fallback
    PRIMARY_LLM_PROVIDER: str = Field(default="openai", env="PRIMARY_LLM_PROVIDER")
    FALLBACK_LLM_PROVIDER: str = Field(default="groq", env="FALLBACK_LLM_PROVIDER")
    
    # OpenAI (Optional)
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    OPENAI_MODEL: str = Field(default="gpt-4-turbo-preview", env="OPENAI_MODEL")
    OPENAI_EMBEDDING_MODEL: str = Field(default="text-embedding-3-small", env="OPENAI_EMBEDDING_MODEL")
    
    # Groq (Fallback - Fast inference)
    GROQ_API_KEY: Optional[str] = Field(default=None, env="GROQ_API_KEY")
    GROQ_MODEL: str = Field(default="llama3-70b-8192", env="GROQ_MODEL")
    
    # Anthropic (Alternative)
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    
    # Google Gemini (FREE - Recommended for students!)
    GEMINI_API_KEY: Optional[str] = Field(default=None, env="GEMINI_API_KEY")
    GEMINI_MODEL: str = Field(default="gemini-1.5-flash", env="GEMINI_MODEL")  # Fast & free
    GEMINI_EMBEDDING_MODEL: str = Field(default="models/embedding-001", env="GEMINI_EMBEDDING_MODEL")
    
    # Reranker Configuration
    RERANKER_MODEL: str = Field(default="cross-encoder/ms-marco-MiniLM-L-12-v2", env="RERANKER_MODEL")
    RERANKER_TOP_K: int = 3
    
    # Retrieval Configuration (Innovation: Adaptive Retrieval)
    RETRIEVAL_TOP_K: int = 10
    RETRIEVAL_MIN_SCORE: float = 0.7
    HYBRID_SEARCH_ALPHA: float = 0.7  # 0.7 = More semantic, 0.3 keyword
    ENABLE_GRAPH_RETRIEVAL: bool = True  # GraphRAG toggle
    
    # Circuit Breaker Configuration (Innovation: Resilience)
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_TIMEOUT: int = 60  # seconds
    CIRCUIT_BREAKER_HALF_OPEN_REQUESTS: int = 3
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    # Prompt Injection Detection (Innovation: Security)
    ENABLE_PROMPT_INJECTION_SHIELD: bool = True
    INJECTION_DETECTION_THRESHOLD: float = 0.8
    
    # Self-Healing Configuration (Innovation: Quality Control)
    ENABLE_ANSWER_VALIDATION: bool = True
    VALIDATION_MIN_CONFIDENCE: float = 0.75
    MAX_RETRY_ATTEMPTS: int = 2
    
    # Active Learning (Innovation: Continuous Improvement)
    ENABLE_ACTIVE_LEARNING: bool = True
    FEEDBACK_THRESHOLD_FOR_RETRAINING: int = 100
    
    # Observability
    ENABLE_TRACING: bool = True
    LANGSMITH_API_KEY: Optional[str] = Field(default=None, env="LANGSMITH_API_KEY")
    LANGSMITH_PROJECT: str = "course-qa-production"
    
    # Document Processing
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    SUPPORTED_FILE_TYPES: List[str] = [".pdf", ".docx", ".txt", ".md", ".html"]
    MAX_FILE_SIZE_MB: int = 50
    
    # Celery Workers (Async Processing) - Optional
    CELERY_BROKER_URL: Optional[str] = Field(default="redis://localhost:6379/1", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: Optional[str] = Field(default="redis://localhost:6379/2", env="CELERY_RESULT_BACKEND")
    
    # S3 Storage - Optional
    S3_BUCKET_NAME: Optional[str] = Field(default="course-materials", env="S3_BUCKET_NAME")
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = Field(default="us-east-1", env="AWS_REGION")
    
    @validator("ALLOWED_ORIGINS", pre=True)
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL"""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
    
    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()