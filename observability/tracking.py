"""
Tracing and Observability - LangSmith integration
"""
import functools
import time
from typing import Callable, Any
from datetime import datetime

from core.config import settings
from core.logging import logger

# LangSmith integration (optional)
LANGSMITH_ENABLED = settings.ENABLE_TRACING and settings.LANGSMITH_API_KEY

if LANGSMITH_ENABLED:
    try:
        from langsmith import Client
        from langsmith.run_helpers import traceable
        
        langsmith_client = Client(
            api_key=settings.LANGSMITH_API_KEY
        )
        logger.info("✅ LangSmith tracing enabled")
    except ImportError:
        logger.warning("LangSmith not installed, tracing disabled")
        LANGSMITH_ENABLED = False
        traceable = lambda **kwargs: lambda func: func
else:
    # No-op decorator if LangSmith not enabled
    def traceable(**kwargs):
        def decorator(func):
            return func
        return decorator


def trace_agent_step(step_name: str):
    """
    Decorator to trace agent steps
    Works with or without LangSmith
    """
    def decorator(func: Callable) -> Callable:
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            try:
                # Log start
                logger.debug(f"Starting {step_name}")
                
                # Execute function
                if LANGSMITH_ENABLED:
                    # Use LangSmith tracing
                    traced_func = traceable(
                        name=step_name,
                        project=settings.LANGSMITH_PROJECT
                    )(func)
                    result = await traced_func(*args, **kwargs)
                else:
                    result = await func(*args, **kwargs)
                
                # Log completion
                duration = time.time() - start_time
                logger.debug(
                    f"Completed {step_name}",
                    extra={"duration_ms": round(duration * 1000, 2)}
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Failed {step_name}: {e}",
                    extra={"duration_ms": round(duration * 1000, 2)},
                    exc_info=True
                )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            try:
                logger.debug(f"Starting {step_name}")
                
                if LANGSMITH_ENABLED:
                    traced_func = traceable(
                        name=step_name,
                        project=settings.LANGSMITH_PROJECT
                    )(func)
                    result = traced_func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                duration = time.time() - start_time
                logger.debug(
                    f"Completed {step_name}",
                    extra={"duration_ms": round(duration * 1000, 2)}
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Failed {step_name}: {e}",
                    extra={"duration_ms": round(duration * 1000, 2)},
                    exc_info=True
                )
                raise
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


import asyncio


def log_execution_time(func_name: str):
    """Simple execution time logger"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            result = await func(*args, **kwargs)
            duration = time.time() - start
            
            logger.info(
                f"{func_name} executed",
                extra={"duration_ms": round(duration * 1000, 2)}
            )
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start
            
            logger.info(
                f"{func_name} executed",
                extra={"duration_ms": round(duration * 1000, 2)}
            )
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator