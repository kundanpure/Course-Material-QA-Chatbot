"""
Query Classifier Agent - Intelligently categorizes queries
Innovation: LLM-based classification with rule-based fallbacks
"""
from enum import Enum
from typing import Dict, List, Optional
import re

from core.logging import logger
from services.llm_router import llm_router
from observability.tracing import trace_agent_step


class QueryType(Enum):
    """Types of queries the system can handle"""
    FACTUAL = "factual"  # Direct fact lookup
    CONCEPTUAL = "conceptual"  # Explanation/understanding
    PROCEDURAL = "procedural"  # How-to questions
    COMPARISON = "comparison"  # Compare A vs B
    CALCULATION = "calculation"  # Math/computation
    MULTI_HOP = "multi_hop"  # Requires multiple pieces of info
    CONVERSATIONAL = "conversational"  # Follow-up questions


class QueryClassifier:
    """
    Classifies queries to determine optimal retrieval strategy
    """
    
    # Rule-based patterns for quick classification
    CALCULATION_PATTERNS = [
        r'\bcalculate\b', r'\bcompute\b', r'\bsolve\b',
        r'\d+\s*[\+\-\*\/]\s*\d+', r'\bsum\b', r'\bmean\b'
    ]
    
    COMPARISON_PATTERNS = [
        r'\bcompare\b', r'\bdifference between\b', r'\bvs\b',
        r'\bbetter than\b', r'\bworse than\b', r'\bsimilar to\b'
    ]
    
    PROCEDURAL_PATTERNS = [
        r'\bhow to\b', r'\bsteps to\b', r'\bprocess of\b',
        r'\bguide\b', r'\btutorial\b', r'\binstruct'
    ]
    
    @trace_agent_step("classifier.classify")
    async def classify(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict:
        """
        Classify the query and recommend retrieval strategy
        Returns: {type, intent, recommended_strategy, confidence}
        """
        
        # Quick rule-based classification first (fast path)
        rule_based = self._rule_based_classification(query)
        if rule_based["confidence"] > 0.8:
            logger.debug(f"Rule-based classification: {rule_based['type']}")
            return rule_based
        
        # LLM-based classification for complex queries
        llm_classification = await self._llm_classification(
            query,
            conversation_history
        )
        
        return llm_classification
    
    def _rule_based_classification(self, query: str) -> Dict:
        """Fast rule-based classification using patterns"""
        query_lower = query.lower()
        
        # Check for calculations
        if any(re.search(p, query_lower) for p in self.CALCULATION_PATTERNS):
            return {
                "type": QueryType.CALCULATION,
                "intent": "perform_calculation",
                "recommended_strategy": "tool_use",  # Use Python tool
                "confidence": 0.9
            }
        
        # Check for comparisons
        if any(re.search(p, query_lower) for p in self.COMPARISON_PATTERNS):
            return {
                "type": QueryType.COMPARISON,
                "intent": "compare_concepts",
                "recommended_strategy": "graph_enhanced",  # Use knowledge graph
                "confidence": 0.85
            }
        
        # Check for procedural
        if any(re.search(p, query_lower) for p in self.PROCEDURAL_PATTERNS):
            return {
                "type": QueryType.PROCEDURAL,
                "intent": "get_instructions",
                "recommended_strategy": "hybrid",
                "confidence": 0.8
            }
        
        # Check for multi-hop (contains multiple questions)
        if query_lower.count('?') > 1 or ' and ' in query_lower:
            return {
                "type": QueryType.MULTI_HOP,
                "intent": "complex_reasoning",
                "recommended_strategy": "graph_enhanced",
                "confidence": 0.75
            }
        
        # Default: factual
        return {
            "type": QueryType.FACTUAL,
            "intent": "retrieve_facts",
            "recommended_strategy": "vector_only",
            "confidence": 0.6
        }
    
    async def _llm_classification(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict:
        """
        Use LLM to classify complex queries
        Innovation: Few-shot classification with structured output
        """
        
        classification_prompt = f"""Classify the following user query into one of these categories:

Categories:
- FACTUAL: Direct fact lookup (e.g., "What is X?", "Define Y")
- CONCEPTUAL: Explanation needed (e.g., "Explain how X works", "Why does Y happen?")
- PROCEDURAL: How-to question (e.g., "How to implement X?", "Steps to achieve Y")
- COMPARISON: Comparing multiple things (e.g., "X vs Y", "Difference between A and B")
- CALCULATION: Math or computation (e.g., "Calculate X", "What's 10% of Y?")
- MULTI_HOP: Requires multiple pieces of information (e.g., "What is X and how does it relate to Y?")
- CONVERSATIONAL: Follow-up or contextual question (e.g., "What about that?", "Can you elaborate?")

Query: "{query}"

Respond with JSON only:
{{
    "type": "CATEGORY_NAME",
    "intent": "brief description of user intent",
    "reasoning": "why you chose this category",
    "recommended_strategy": "vector_only" | "hybrid" | "graph_enhanced" | "tool_use",
    "confidence": 0.0-1.0
}}

Strategy guidelines:
- vector_only: Simple factual queries
- hybrid: Most queries (combines semantic + keyword search)
- graph_enhanced: Comparisons, relationships, multi-hop reasoning
- tool_use: Calculations or code execution needed
"""
        
        try:
            response = await llm_router.chat(
                messages=[
                    {"role": "system", "content": "You are a query classification expert. Respond only with valid JSON."},
                    {"role": "user", "content": classification_prompt}
                ],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=200
            )
            
            # Parse JSON response
            import json
            result = json.loads(response["content"])
            
            # Convert string type to enum
            result["type"] = QueryType[result["type"]]
            
            logger.debug(
                f"LLM classification",
                extra={
                    "type": result["type"].value,
                    "confidence": result["confidence"]
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"LLM classification failed: {e}", exc_info=True)
            # Fallback to rule-based
            return self._rule_based_classification(query)
    
    def should_use_graph(self, query_type: QueryType) -> bool:
        """Determine if knowledge graph should be used"""
        return query_type in [
            QueryType.COMPARISON,
            QueryType.MULTI_HOP,
            QueryType.CONCEPTUAL
        ]