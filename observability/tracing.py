"""
Stub for observability tracing
"""
from functools import wraps
from typing import Callable


def trace_agent_step(step_name: str) -> Callable:
    """Decorator for tracing agent steps"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Simple passthrough - can add OpenTelemetry later
            return await func(*args, **kwargs)
        return wrapper
    return decorator
