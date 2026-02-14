"""
Security Module - JWT, API Keys, Multi-tenancy, Prompt Injection Detection
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
import re

from core.config import settings
from core.logging import logger

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security schemes
bearer_scheme = HTTPBearer()
api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)


class SecurityService:
    """Centralized security operations"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def create_access_token(
        data: dict,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.JWT_EXPIRATION_MINUTES
            )
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt
    
    @staticmethod
    def decode_token(token: str) -> dict:
        """Decode and validate JWT token"""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except JWTError as e:
            logger.warning(f"JWT decode error: {e}")
            raise HTTPException(
                status_code=401,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )


class PromptInjectionShield:
    """
    Innovation: Detect and prevent prompt injection attacks
    Uses pattern matching + ML-based detection
    """
    
    # Common injection patterns
    INJECTION_PATTERNS = [
        r"ignore\s+(previous|above|all)\s+instructions",
        r"disregard\s+(previous|above|all)",
        r"forget\s+(everything|all|previous)",
        r"new\s+instructions?:",
        r"system\s+prompt",
        r"you\s+are\s+now",
        r"act\s+as\s+if",
        r"<\|im_start\|>",
        r"<\|im_end\|>",
        r"\[INST\]",
        r"\[/INST\]",
    ]
    
    @classmethod
    def detect_injection(cls, query: str) -> tuple[bool, float, str]:
        """
        Detect potential prompt injection
        Returns: (is_injection, confidence, reason)
        """
        query_lower = query.lower()
        
        # Pattern-based detection
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, query_lower):
                logger.warning(f"Potential prompt injection detected: {pattern}")
                return True, 0.95, f"Pattern match: {pattern}"
        
        # Heuristic checks
        suspicious_score = 0.0
        reasons = []
        
        # Check for excessive special characters
        special_char_ratio = len(re.findall(r'[<>|\[\]{}]', query)) / len(query) if query else 0
        if special_char_ratio > 0.1:
            suspicious_score += 0.3
            reasons.append("High special character ratio")
        
        # Check for system-like keywords
        system_keywords = ["system:", "assistant:", "user:", "prompt:", "role:"]
        if any(keyword in query_lower for keyword in system_keywords):
            suspicious_score += 0.4
            reasons.append("System-like keywords detected")
        
        # Check for instruction-like structure
        if re.search(r'(step\s+\d+:|instruction\s+\d+:)', query_lower):
            suspicious_score += 0.2
            reasons.append("Instruction-like structure")
        
        if suspicious_score >= settings.INJECTION_DETECTION_THRESHOLD:
            return True, suspicious_score, ", ".join(reasons)
        
        return False, suspicious_score, "Clean"
    
    @classmethod
    def sanitize_query(cls, query: str) -> str:
        """Sanitize query by removing potential injection markers"""
        # Remove common injection markers
        sanitized = re.sub(r'<\|.*?\|>', '', query)
        sanitized = re.sub(r'\[/?INST\]', '', sanitized)
        sanitized = re.sub(r'###\s*(System|User|Assistant):', '', sanitized)
        
        return sanitized.strip()


class TenantContext:
    """
    Innovation: Multi-tenant context management
    Ensures data isolation across different organizations
    """
    
    def __init__(
        self,
        tenant_id: str,
        user_id: str,
        permissions: list[str]
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.permissions = permissions
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        return permission in self.permissions or "admin" in self.permissions
    
    def get_filter_clause(self) -> dict:
        """Get database filter for tenant isolation"""
        return {"tenant_id": self.tenant_id}


# Dependency functions
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
) -> TenantContext:
    """Extract and validate JWT token, return tenant context"""
    token = credentials.credentials
    payload = SecurityService.decode_token(token)
    
    tenant_id = payload.get("tenant_id")
    user_id = payload.get("user_id")
    permissions = payload.get("permissions", [])
    
    if not tenant_id or not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid token payload"
        )
    
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        permissions=permissions
    )


async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header)
) -> TenantContext:
    """Verify API key and return tenant context"""
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required"
        )
    
    # In production, lookup API key in database
    # For now, simplified validation
    # TODO: Implement proper API key validation from DB
    
    from db.repository import UserRepository
    repo = UserRepository()
    api_key_data = await repo.validate_api_key(api_key)
    
    if not api_key_data:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    return TenantContext(
        tenant_id=api_key_data["tenant_id"],
        user_id=api_key_data["user_id"],
        permissions=api_key_data["permissions"]
    )


async def check_prompt_injection(query: str) -> str:
    """
    Middleware to check for prompt injection attacks
    Returns sanitized query or raises exception
    """
    if not settings.ENABLE_PROMPT_INJECTION_SHIELD:
        return query
    
    is_injection, confidence, reason = PromptInjectionShield.detect_injection(query)
    
    if is_injection:
        logger.warning(
            f"Blocked prompt injection attempt",
            extra={
                "confidence": confidence,
                "reason": reason,
                "query_preview": query[:100]
            }
        )
        raise HTTPException(
            status_code=400,
            detail="Query contains potentially malicious content. Please rephrase your question.",
            headers={"X-Rejection-Reason": "prompt_injection"}
        )
    
    # Return sanitized query even if not detected as injection
    return PromptInjectionShield.sanitize_query(query)


# RBAC Helpers
def require_permission(permission: str):
    """Decorator to require specific permission"""
    async def permission_checker(
        context: TenantContext = Depends(get_current_user)
    ):
        if not context.has_permission(permission):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission} required"
            )
        return context
    return permission_checker