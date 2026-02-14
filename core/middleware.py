"""
Advanced Middleware - Circuit Breaker, Rate Limiting, Request Tracking
"""
import time
import uuid
from typing import Callable
from collections import defaultdict, deque
from datetime import datetime, timedelta
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.config import settings
from core.logging import logger
from observability.metrics import (
    http_requests_total,
    http_request_duration_seconds,
    circuit_breaker_state,
    rate_limit_exceeded_total
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all incoming requests with timing and tracing"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID for tracing
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timer
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else "unknown"
            }
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            f"Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2)
            }
        )
        
        # Add headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        
        return response


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Track Prometheus metrics for all requests"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)
        
        start_time = time.time()
        
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            logger.error(f"Request failed: {e}", exc_info=True)
            raise
        finally:
            # Record metrics
            duration = time.time() - start_time
            
            http_requests_total.labels(
                method=request.method,
                endpoint=request.url.path,
                status=status_code
            ).inc()
            
            http_request_duration_seconds.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)
        
        return response


class CircuitBreakerState:
    """
    Innovation: Circuit Breaker Pattern for resilience
    States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (testing)
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker implementation"""
    
    def __init__(
        self,
        failure_threshold: int = settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        timeout: int = settings.CIRCUIT_BREAKER_TIMEOUT,
        half_open_requests: int = settings.CIRCUIT_BREAKER_HALF_OPEN_REQUESTS
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_requests = half_open_requests
        
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        self.last_failure_time = None
        self.half_open_attempts = 0
    
    def record_success(self):
        """Record successful request"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_attempts += 1
            if self.half_open_attempts >= self.half_open_requests:
                logger.info("Circuit breaker closing - service recovered")
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.half_open_attempts = 0
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self):
        """Record failed request"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            logger.warning("Circuit breaker reopening - service still failing")
            self.state = CircuitBreakerState.OPEN
            self.half_open_attempts = 0
        elif self.failure_count >= self.failure_threshold:
            logger.error(
                f"Circuit breaker opening - {self.failure_count} failures detected"
            )
            self.state = CircuitBreakerState.OPEN
    
    def should_attempt_request(self) -> bool:
        """Check if request should be attempted"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            # Check if timeout expired
            if time.time() - self.last_failure_time > self.timeout:
                logger.info("Circuit breaker entering half-open state")
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_attempts = 0
                return True
            return False
        
        # HALF_OPEN state
        return True
    
    def get_state(self) -> str:
        return self.state


# Global circuit breaker instances (per service)
llm_circuit_breaker = CircuitBreaker()
retrieval_circuit_breaker = CircuitBreaker()


class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """Apply circuit breaker pattern to requests"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only apply to query endpoints
        if not request.url.path.startswith("/api/v1/query"):
            return await call_next(request)
        
        # Check circuit breaker state
        if not llm_circuit_breaker.should_attempt_request():
            logger.warning("Circuit breaker open - request rejected")
            circuit_breaker_state.labels(service="llm").set(1)  # OPEN
            
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service temporarily unavailable",
                    "code": "CIRCUIT_BREAKER_OPEN",
                    "message": "The service is experiencing issues. Please try again later.",
                    "retry_after": settings.CIRCUIT_BREAKER_TIMEOUT
                }
            )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Record success for non-error status codes
            if response.status_code < 500:
                llm_circuit_breaker.record_success()
                circuit_breaker_state.labels(service="llm").set(0)  # CLOSED
            else:
                llm_circuit_breaker.record_failure()
            
            return response
            
        except Exception as e:
            llm_circuit_breaker.record_failure()
            circuit_breaker_state.labels(service="llm").set(1)
            raise


class RateLimiter:
    """
    Token bucket rate limiter
    Tracks requests per tenant/API key
    """
    
    def __init__(
        self,
        requests: int = settings.RATE_LIMIT_REQUESTS,
        window: int = settings.RATE_LIMIT_WINDOW
    ):
        self.requests = requests
        self.window = window
        self.buckets = defaultdict(lambda: deque())
    
    def is_allowed(self, identifier: str) -> tuple[bool, dict]:
        """
        Check if request is allowed
        Returns: (allowed, info_dict)
        """
        now = time.time()
        bucket = self.buckets[identifier]
        
        # Remove old requests outside the window
        while bucket and bucket[0] < now - self.window:
            bucket.popleft()
        
        # Check limit
        if len(bucket) >= self.requests:
            oldest_request = bucket[0]
            reset_time = oldest_request + self.window
            return False, {
                "limit": self.requests,
                "remaining": 0,
                "reset": int(reset_time)
            }
        
        # Add current request
        bucket.append(now)
        
        return True, {
            "limit": self.requests,
            "remaining": self.requests - len(bucket),
            "reset": int(now + self.window)
        }


# Global rate limiter
rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip for health checks
        if request.url.path.startswith("/api/v1/health"):
            return await call_next(request)
        
        # Get identifier (tenant_id or IP)
        identifier = getattr(request.state, "tenant_id", None)
        if not identifier:
            identifier = request.client.host if request.client else "unknown"
        
        # Check rate limit
        allowed, info = rate_limiter.is_allowed(identifier)
        
        if not allowed:
            logger.warning(
                f"Rate limit exceeded",
                extra={
                    "identifier": identifier,
                    "path": request.url.path
                }
            )
            
            rate_limit_exceeded_total.labels(
                identifier=identifier
            ).inc()
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "limit": info["limit"],
                    "reset": info["reset"]
                },
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": str(info["remaining"]),
                    "X-RateLimit-Reset": str(info["reset"]),
                    "Retry-After": str(info["reset"] - int(time.time()))
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])
        
        return response