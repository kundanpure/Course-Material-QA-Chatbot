"""
Agentic Orchestrator - Coordinates the entire query pipeline with self-healing
Innovation: State machine-based flow with retry logic and validation
"""
import asyncio
from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from core.config import settings
from core.logging import logger
from agents.query_classifier import QueryClassifier, QueryType
from agents.retrieval_strategy import RetrievalStrategy
from agents.answer_composer import AnswerComposer
from agents.answer_validator import AnswerValidator
from services.cache_service import cache_service
from observability.tracing import trace_agent_step


class PipelineState(Enum):
    """States in the query processing pipeline"""
    INIT = "init"
    CLASSIFICATION = "classification"
    RETRIEVAL = "retrieval"
    RERANKING = "reranking"
    GENERATION = "generation"
    VALIDATION = "validation"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class QueryContext:
    """Context object passed through the pipeline"""
    # Input
    query: str
    tenant_id: str
    user_id: str
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    
    # Pipeline state
    state: PipelineState = PipelineState.INIT
    attempt: int = 0
    max_attempts: int = settings.MAX_RETRY_ATTEMPTS
    
    # Intermediate results
    query_type: Optional[QueryType] = None
    query_intent: Optional[str] = None
    search_strategy: Optional[str] = None
    retrieved_chunks: List[Dict] = field(default_factory=list)
    reranked_chunks: List[Dict] = field(default_factory=list)
    
    # Final output
    answer: Optional[str] = None
    citations: List[Dict] = field(default_factory=list)
    confidence: float = 0.0
    
    # Metadata
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    
    # Metrics
    tokens_used: int = 0
    retrieval_time_ms: float = 0
    generation_time_ms: float = 0
    total_time_ms: float = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/tracing"""
        return {
            "query": self.query,
            "tenant_id": self.tenant_id,
            "state": self.state.value,
            "attempt": self.attempt,
            "query_type": self.query_type.value if self.query_type else None,
            "confidence": self.confidence,
            "tokens_used": self.tokens_used,
            "total_time_ms": self.total_time_ms
        }


class AgenticOrchestrator:
    """
    Innovation: Self-healing orchestrator with adaptive retry logic
    - Classifies queries to choose optimal retrieval strategy
    - Validates answers and retries with different strategies if needed
    - Implements circuit breaker pattern for external services
    """
    
    def __init__(self):
        self.classifier = QueryClassifier()
        self.retrieval_strategy = RetrievalStrategy()
        self.answer_composer = AnswerComposer()
        self.answer_validator = AnswerValidator()
    
    @trace_agent_step("orchestrator.process_query")
    async def process_query(
        self,
        query: str,
        tenant_id: str,
        user_id: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point - orchestrates the entire pipeline
        """
        # Initialize context
        context = QueryContext(
            query=query,
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_history=conversation_history or []
        )
        
        logger.info(
            f"Starting query processing",
            extra={"query": query[:100], "tenant_id": tenant_id}
        )
        
        try:
            # Step 1: Check semantic cache
            cached_result = await self._check_cache(context)
            if cached_result:
                logger.info("Cache hit - returning cached result")
                return cached_result
            
            # Step 2: Main pipeline with retry logic
            while context.attempt < context.max_attempts:
                context.attempt += 1
                
                try:
                    # Classification
                    await self._classify_query(context)
                    
                    # Retrieval
                    await self._retrieve_documents(context)
                    
                    # Reranking
                    await self._rerank_documents(context)
                    
                    # Generation
                    await self._generate_answer(context)
                    
                    # Validation (Innovation: Self-healing)
                    if settings.ENABLE_ANSWER_VALIDATION:
                        is_valid = await self._validate_answer(context)
                        if not is_valid and context.attempt < context.max_attempts:
                            logger.warning(
                                f"Answer validation failed - retrying with different strategy",
                                extra={"attempt": context.attempt}
                            )
                            # Modify strategy for retry
                            await self._adjust_strategy_for_retry(context)
                            continue
                    
                    # Success!
                    context.state = PipelineState.COMPLETE
                    break
                    
                except Exception as e:
                    logger.error(
                        f"Pipeline error on attempt {context.attempt}",
                        exc_info=True
                    )
                    if context.attempt >= context.max_attempts:
                        raise
                    # Continue to retry
            
            # Calculate final metrics
            context.end_time = datetime.utcnow()
            context.total_time_ms = (
                context.end_time - context.start_time
            ).total_seconds() * 1000
            
            # Cache the result
            await self._cache_result(context)
            
            # Return response
            return self._build_response(context)
            
        except Exception as e:
            context.state = PipelineState.FAILED
            context.error = str(e)
            logger.error(f"Query processing failed: {e}", exc_info=True)
            raise
    
    async def _check_cache(self, context: QueryContext) -> Optional[Dict]:
        """Check semantic cache for similar queries"""
        cached = await cache_service.get_semantic(
            query=context.query,
            tenant_id=context.tenant_id
        )
        
        if cached:
            return {
                "answer": cached["answer"],
                "citations": cached["citations"],
                "confidence": cached["confidence"],
                "cached": True,
                "cache_hit_similarity": cached.get("similarity", 1.0)
            }
        
        return None
    
    @trace_agent_step("orchestrator.classify")
    async def _classify_query(self, context: QueryContext):
        """Step 1: Classify the query type and intent"""
        context.state = PipelineState.CLASSIFICATION
        
        classification = await self.classifier.classify(
            query=context.query,
            conversation_history=context.conversation_history
        )
        
        context.query_type = classification["type"]
        context.query_intent = classification["intent"]
        context.search_strategy = classification["recommended_strategy"]
        
        logger.info(
            f"Query classified",
            extra={
                "type": context.query_type.value,
                "intent": context.query_intent,
                "strategy": context.search_strategy
            }
        )
    
    @trace_agent_step("orchestrator.retrieve")
    async def _retrieve_documents(self, context: QueryContext):
        """Step 2: Retrieve relevant documents using adaptive strategy"""
        context.state = PipelineState.RETRIEVAL
        
        import time
        start = time.time()
        
        # Use the recommended strategy from classification
        retrieved = await self.retrieval_strategy.retrieve(
            query=context.query,
            tenant_id=context.tenant_id,
            strategy=context.search_strategy,
            query_type=context.query_type,
            top_k=settings.RETRIEVAL_TOP_K
        )
        
        context.retrieved_chunks = retrieved
        context.retrieval_time_ms = (time.time() - start) * 1000
        
        logger.info(
            f"Retrieved {len(retrieved)} documents",
            extra={
                "strategy": context.search_strategy,
                "time_ms": context.retrieval_time_ms
            }
        )
    
    @trace_agent_step("orchestrator.rerank")
    async def _rerank_documents(self, context: QueryContext):
        """Step 3: Rerank retrieved documents for relevance"""
        context.state = PipelineState.RERANKING
        
        from services.reranker_service import reranker_service
        
        reranked = await reranker_service.rerank(
            query=context.query,
            documents=context.retrieved_chunks,
            top_k=settings.RERANKER_TOP_K
        )
        
        context.reranked_chunks = reranked
        
        logger.info(f"Reranked to top {len(reranked)} documents")
    
    @trace_agent_step("orchestrator.generate")
    async def _generate_answer(self, context: QueryContext):
        """Step 4: Generate answer using LLM"""
        context.state = PipelineState.GENERATION
        
        import time
        start = time.time()
        
        result = await self.answer_composer.compose(
            query=context.query,
            context_chunks=context.reranked_chunks,
            query_type=context.query_type,
            conversation_history=context.conversation_history
        )
        
        context.answer = result["answer"]
        context.citations = result["citations"]
        context.tokens_used = result["tokens_used"]
        context.generation_time_ms = (time.time() - start) * 1000
        
        logger.info(
            f"Generated answer",
            extra={
                "tokens": context.tokens_used,
                "time_ms": context.generation_time_ms
            }
        )
    
    @trace_agent_step("orchestrator.validate")
    async def _validate_answer(self, context: QueryContext) -> bool:
        """
        Step 5: Validate answer quality (Innovation: Self-healing)
        Returns True if valid, False if needs retry
        """
        context.state = PipelineState.VALIDATION
        
        validation = await self.answer_validator.validate(
            query=context.query,
            answer=context.answer,
            context_chunks=context.reranked_chunks,
            citations=context.citations
        )
        
        context.confidence = validation["confidence"]
        is_valid = validation["is_valid"]
        
        logger.info(
            f"Answer validation: {'PASS' if is_valid else 'FAIL'}",
            extra={
                "confidence": context.confidence,
                "issues": validation.get("issues", [])
            }
        )
        
        return is_valid
    
    async def _adjust_strategy_for_retry(self, context: QueryContext):
        """
        Innovation: Adaptive retry strategy
        If validation fails, try a different retrieval approach
        """
        # Strategy escalation path
        strategy_fallbacks = {
            "vector_only": "hybrid",
            "hybrid": "graph_enhanced",
            "graph_enhanced": "vector_only"  # Full cycle
        }
        
        current = context.search_strategy
        context.search_strategy = strategy_fallbacks.get(current, "hybrid")
        
        logger.info(
            f"Adjusting strategy for retry",
            extra={
                "from": current,
                "to": context.search_strategy,
                "attempt": context.attempt
            }
        )
    
    async def _cache_result(self, context: QueryContext):
        """Cache the successful result"""
        if context.state == PipelineState.COMPLETE:
            await cache_service.set_semantic(
                query=context.query,
                tenant_id=context.tenant_id,
                data={
                    "answer": context.answer,
                    "citations": context.citations,
                    "confidence": context.confidence
                }
            )
    
    def _build_response(self, context: QueryContext) -> Dict[str, Any]:
        """Build the final response"""
        return {
            "answer": context.answer,
            "citations": context.citations,
            "confidence": context.confidence,
            "metadata": {
                "query_type": context.query_type.value if context.query_type else None,
                "retrieval_strategy": context.search_strategy,
                "chunks_retrieved": len(context.retrieved_chunks),
                "chunks_used": len(context.reranked_chunks),
                "attempts": context.attempt,
                "tokens_used": context.tokens_used,
                "retrieval_time_ms": context.retrieval_time_ms,
                "generation_time_ms": context.generation_time_ms,
                "total_time_ms": context.total_time_ms
            },
            "cached": False
        }


# Singleton instance
orchestrator = AgenticOrchestrator()