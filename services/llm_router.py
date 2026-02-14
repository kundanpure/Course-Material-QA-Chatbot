"""
LLM Router Service - Multi-provider LLM with automatic fallback
Innovation: Circuit breaker pattern for resilient LLM calls
"""
from typing import Dict, List, Optional, Any
from enum import Enum
import time

from openai import AsyncOpenAI
from groq import AsyncGroq
from anthropic import AsyncAnthropic
import google.generativeai as genai

from core.config import settings
from core.logging import logger
from core.middleware import llm_circuit_breaker
from observability.metrics import llm_requests_total, llm_tokens_used_total
from observability.tracing import trace_agent_step


class LLMProvider(Enum):
    OPENAI = "openai"
    GROQ = "groq"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class LLMRouter:
    """
    Innovation: Intelligent LLM router with automatic fallback
    - Primary provider: OpenAI (most capable)
    - Fallback provider: Groq (fast, open-source models)
    - Circuit breaker prevents cascade failures
    """
    
    def __init__(self):
        # Initialize clients
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
        self.anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None
        
        # Initialize Gemini
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.gemini_model = genai.GenerativeModel(settings.GEMINI_MODEL)
        else:
            self.gemini_model = None
        
        self.primary_provider = LLMProvider(settings.PRIMARY_LLM_PROVIDER)
        self.fallback_provider = LLMProvider(settings.FALLBACK_LLM_PROVIDER) if settings.FALLBACK_LLM_PROVIDER else None
    
    @trace_agent_step("llm.chat")
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model: Optional[str] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send chat request with automatic provider fallback
        """
        # Try primary provider first
        try:
            if llm_circuit_breaker.should_attempt_request():
                result = await self._call_provider(
                    provider=self.primary_provider,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=model,
                    stream=stream,
                    **kwargs
                )
                
                llm_circuit_breaker.record_success()
                
                # Record metrics
                llm_requests_total.labels(
                    provider=self.primary_provider.value,
                    status="success"
                ).inc()
                
                if result.get("tokens_used"):
                    llm_tokens_used_total.labels(
                        provider=self.primary_provider.value
                    ).inc(result["tokens_used"])
                
                return result
            else:
                logger.warning("Primary LLM circuit breaker is OPEN, using fallback")
                raise Exception("Circuit breaker open")
                
        except Exception as e:
            logger.error(
                f"Primary LLM provider failed: {e}",
                extra={"provider": self.primary_provider.value}
            )
            
            llm_circuit_breaker.record_failure()
            
            llm_requests_total.labels(
                provider=self.primary_provider.value,
                status="error"
            ).inc()
            
            # Try fallback provider
            if self.fallback_provider:
                try:
                    logger.info(f"Attempting fallback provider: {self.fallback_provider.value}")
                    
                    result = await self._call_provider(
                        provider=self.fallback_provider,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        model=None,  # Use default model for fallback
                        stream=stream,
                        **kwargs
                    )
                    
                    llm_requests_total.labels(
                        provider=self.fallback_provider.value,
                        status="success"
                    ).inc()
                    
                    return result
                    
                except Exception as fallback_error:
                    logger.error(f"Fallback provider also failed: {fallback_error}")
                    llm_requests_total.labels(
                        provider=self.fallback_provider.value,
                        status="error"
                    ).inc()
                    raise
            else:
                raise  # No fallback available
    
    async def _call_provider(
        self,
        provider: LLMProvider,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        model: Optional[str],
        stream: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """Call specific LLM provider"""
        
        if provider == LLMProvider.OPENAI:
            return await self._call_openai(
                messages, temperature, max_tokens, model or settings.OPENAI_MODEL, stream, **kwargs
            )
        
        elif provider == LLMProvider.GROQ:
            return await self._call_groq(
                messages, temperature, max_tokens, model or settings.GROQ_MODEL, stream, **kwargs
            )
        
        elif provider == LLMProvider.ANTHROPIC:
            return await self._call_anthropic(
                messages, temperature, max_tokens, model or "claude-3-sonnet-20240229", stream, **kwargs
            )
        
        elif provider == LLMProvider.GEMINI:
            return await self._call_gemini(
                messages, temperature, max_tokens, model or settings.GEMINI_MODEL, stream, **kwargs
            )
        
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    async def _call_openai(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        model: str,
        stream: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """Call OpenAI API"""
        
        response = await self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            **kwargs
        )
        
        if stream:
            return {"stream": response}
        
        return {
            "content": response.choices[0].message.content,
            "model": response.model,
            "tokens_used": response.usage.total_tokens,
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "finish_reason": response.choices[0].finish_reason
        }
    
    async def _call_groq(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        model: str,
        stream: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """Call Groq API (fast open-source models)"""
        
        response = await self.groq_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream
        )
        
        if stream:
            return {"stream": response}
        
        return {
            "content": response.choices[0].message.content,
            "model": response.model,
            "tokens_used": response.usage.total_tokens,
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "finish_reason": response.choices[0].finish_reason
        }
    
    async def _call_anthropic(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        model: str,
        stream: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """Call Anthropic API"""
        
        # Convert OpenAI format to Anthropic format
        system_message = None
        converted_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                converted_messages.append(msg)
        
        response = await self.anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_message,
            messages=converted_messages,
            stream=stream
        )
        
        if stream:
            return {"stream": response}
        
        return {
            "content": response.content[0].text,
            "model": response.model,
            "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "finish_reason": response.stop_reason
        }
    
    async def _call_gemini(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        model: str,
        stream: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """Call Google Gemini API"""
        
        # Convert OpenAI message format to Gemini format
        system_instruction = None
        chat_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                chat_messages.append({"role": "user", "parts": [msg["content"]]})
            elif msg["role"] == "assistant":
                chat_messages.append({"role": "model", "parts": [msg["content"]]})
        
        # Configure generation
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        
        # Use GenerativeModel with system instruction if provided
        if system_instruction:
            model_instance = genai.GenerativeModel(
                model_name=model,
                system_instruction=system_instruction
            )
        else:
            model_instance = self.gemini_model
        
        # Generate response
        if stream:
            response = await model_instance.generate_content_async(
                chat_messages,
                generation_config=generation_config,
                stream=False
            )
            return {"stream": response}
        else:
            response = await model_instance.generate_content_async(
                chat_messages,
                generation_config=generation_config
            )
        
        # Extract token counts
        prompt_tokens = response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0
        completion_tokens = response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0
        
        return {
            "content": response.text,
            "model": model,
            "tokens_used": prompt_tokens + completion_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "finish_reason": "stop"
        }


# Singleton instance
llm_router = LLMRouter()