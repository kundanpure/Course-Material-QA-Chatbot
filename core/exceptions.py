"""
Custom Exceptions
"""
from typing import Optional


class AppException(Exception):
    """Base exception for application errors"""
    
    def __init__(
        self,
        detail: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR"
    ):
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(detail)


class AuthenticationError(AppException):
    """Authentication failed"""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            detail=detail,
            status_code=401,
            error_code="AUTH_ERROR"
        )


class AuthorizationError(AppException):
    """Authorization failed - insufficient permissions"""
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            detail=detail,
            status_code=403,
            error_code="FORBIDDEN"
        )


class ResourceNotFoundError(AppException):
    """Resource not found"""
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            detail=f"{resource} not found: {identifier}",
            status_code=404,
            error_code="NOT_FOUND"
        )


class ValidationError(AppException):
    """Input validation failed"""
    def __init__(self, detail: str):
        super().__init__(
            detail=detail,
            status_code=400,
            error_code="VALIDATION_ERROR"
        )


class RateLimitError(AppException):
    """Rate limit exceeded"""
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(
            detail=detail,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED"
        )


class LLMError(AppException):
    """LLM provider error"""
    def __init__(self, detail: str, provider: str):
        super().__init__(
            detail=f"LLM error ({provider}): {detail}",
            status_code=502,
            error_code="LLM_ERROR"
        )


class RetrievalError(AppException):
    """Retrieval service error"""
    def __init__(self, detail: str):
        super().__init__(
            detail=f"Retrieval error: {detail}",
            status_code=500,
            error_code="RETRIEVAL_ERROR"
        )


class EmbeddingError(AppException):
    """Embedding generation error"""
    def __init__(self, detail: str):
        super().__init__(
            detail=f"Embedding error: {detail}",
            status_code=500,
            error_code="EMBEDDING_ERROR"
        )


class CacheError(AppException):
    """Cache operation error"""
    def __init__(self, detail: str):
        super().__init__(
            detail=f"Cache error: {detail}",
            status_code=500,
            error_code="CACHE_ERROR"
        )


class CircuitBreakerOpenError(AppException):
    """Circuit breaker is open"""
    def __init__(self, service: str):
        super().__init__(
            detail=f"Service temporarily unavailable: {service}",
            status_code=503,
            error_code="CIRCUIT_BREAKER_OPEN"
        )


class DocumentProcessingError(AppException):
    """Document processing error"""
    def __init__(self, detail: str):
        super().__init__(
            detail=f"Document processing error: {detail}",
            status_code=500,
            error_code="DOCUMENT_ERROR"
        )


class PromptInjectionError(AppException):
    """Prompt injection detected"""
    def __init__(self, detail: str = "Potentially malicious query detected"):
        super().__init__(
            detail=detail,
            status_code=400,
            error_code="PROMPT_INJECTION"
        )