"""
Answer Validator Agent - Validates answer quality (Self-healing innovation)
"""
from typing import List, Dict, Any
import re

from core.config import settings
from core.logging import logger
from services.llm_router import llm_router
from services.reranker_service import reranker_service
from observability.tracing import trace_agent_step


class AnswerValidator:
    """
    Innovation: Validates answer quality before returning to user
    If validation fails, orchestrator retries with different strategy
    """
    
    @trace_agent_step("validator.validate")
    async def validate(
        self,
        query: str,
        answer: str,
        context_chunks: List[Dict[str, Any]],
        citations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate answer quality
        
        Returns:
            {
                "is_valid": bool,
                "confidence": float,
                "issues": List[str]
            }
        """
        
        issues = []
        confidence = 1.0
        
        # Check 1: Answer is not too short
        if len(answer.split()) < 10:
            issues.append("Answer too short")
            confidence *= 0.5
        
        # Check 2: Answer is not a refusal
        refusal_patterns = [
            r"i (don't|do not|can't|cannot) (know|have|find)",
            r"(no|not) (information|data|content)",
            r"unable to (answer|help|find)",
            r"i apologize",
        ]
        
        answer_lower = answer.lower()
        for pattern in refusal_patterns:
            if re.search(pattern, answer_lower):
                issues.append("Answer appears to be a refusal")
                confidence *= 0.3
                break
        
        # Check 3: Answer relevance to query
        relevance_score = await self._check_relevance(query, answer)
        if relevance_score < 0.5:
            issues.append(f"Low relevance to query ({relevance_score:.2f})")
            confidence *= 0.6
        
        # Check 4: Citations exist and are valid
        if not citations:
            issues.append("No citations provided")
            confidence *= 0.7
        else:
            # Check if citations are actually used in answer
            citation_pattern = r'\[\d+\]'
            cited_in_answer = len(re.findall(citation_pattern, answer))
            
            if cited_in_answer == 0:
                issues.append("Citations not referenced in answer")
                confidence *= 0.8
        
        # Check 5: Answer is grounded in context
        if context_chunks:
            grounding_score = await self._check_grounding(answer, context_chunks)
            if grounding_score < 0.4:
                issues.append(f"Answer poorly grounded in context ({grounding_score:.2f})")
                confidence *= 0.5
        
        # Check 6: No hallucination indicators
        hallucination_patterns = [
            r"in my (opinion|experience)",
            r"i (think|believe|feel)",
            r"(probably|maybe|possibly)",
        ]
        
        hallucination_count = 0
        for pattern in hallucination_patterns:
            if re.search(pattern, answer_lower):
                hallucination_count += 1
        
        if hallucination_count >= 2:
            issues.append("Potential hallucination indicators")
            confidence *= 0.7
        
        # Overall validation
        is_valid = confidence >= settings.VALIDATION_MIN_CONFIDENCE
        
        logger.info(
            f"Answer validation: {'PASS' if is_valid else 'FAIL'}",
            extra={
                "confidence": confidence,
                "issues": issues,
                "relevance": relevance_score if 'relevance_score' in locals() else None
            }
        )
        
        return {
            "is_valid": is_valid,
            "confidence": confidence,
            "issues": issues
        }
    
    async def _check_relevance(self, query: str, answer: str) -> float:
        """Check if answer is relevant to query using cross-encoder"""
        try:
            score = reranker_service.get_relevance_score(query, answer)
            return max(0.0, min(1.0, score))  # Normalize to 0-1
        except Exception as e:
            logger.warning(f"Relevance check failed: {e}")
            return 0.5  # Default to neutral
    
    async def _check_grounding(
        self,
        answer: str,
        context_chunks: List[Dict[str, Any]]
    ) -> float:
        """
        Check if answer is grounded in provided context
        Uses entailment checking
        """
        try:
            # Combine context
            context = " ".join([chunk.get("text", "") for chunk in context_chunks[:3]])
            
            # Use LLM to check if answer is supported by context
            validation_prompt = f"""Does the following answer contain information that is supported by the context?
Answer "YES" if the answer is fully grounded in the context.
Answer "PARTIAL" if some parts are grounded but not all.
Answer "NO" if the answer contains information not in the context.

Context:
{context[:1000]}

Answer:
{answer[:500]}

Response (just YES, PARTIAL, or NO):"""
            
            response = await llm_router.chat(
                messages=[
                    {"role": "system", "content": "You are a fact checker. Be strict and precise."},
                    {"role": "user", "content": validation_prompt}
                ],
                temperature=0.0,
                max_tokens=10
            )
            
            result = response["content"].strip().upper()
            
            if "YES" in result:
                return 1.0
            elif "PARTIAL" in result:
                return 0.6
            else:
                return 0.2
                
        except Exception as e:
            logger.warning(f"Grounding check failed: {e}")
            return 0.5  # Default to neutral
    
    async def validate_streaming(
        self,
        query: str,
        answer_stream: str,
        context_chunks: List[Dict[str, Any]]
    ) -> bool:
        """
        Simplified validation for streaming responses
        Checks only basic criteria
        """
        issues = []
        
        # Basic checks only
        if len(answer_stream.split()) < 10:
            return False
        
        refusal_patterns = [
            r"i (don't|do not|can't|cannot) (know|have|find)",
            r"unable to (answer|help|find)",
        ]
        
        answer_lower = answer_stream.lower()
        for pattern in refusal_patterns:
            if re.search(pattern, answer_lower):
                return False
        
        return True


# Singleton instance
answer_validator = AnswerValidator()