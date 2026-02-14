"""
Answer Composer Agent - Generates answers with citations
"""
from typing import List, Dict, Any, Optional
import re

from core.logging import logger
from agents.query_classifier import QueryType
from services.llm_router import llm_router
from observability.tracing import trace_agent_step


class AnswerComposer:
    """
    Generates natural language answers from retrieved context
    Ensures proper citation of sources
    """
    
    def __init__(self):
        self.system_prompts = {
            QueryType.FACTUAL: self._get_factual_prompt(),
            QueryType.CONCEPTUAL: self._get_conceptual_prompt(),
            QueryType.PROCEDURAL: self._get_procedural_prompt(),
            QueryType.COMPARISON: self._get_comparison_prompt(),
            QueryType.MULTI_HOP: self._get_multi_hop_prompt(),
        }
    
    @trace_agent_step("answer_composer.compose")
    async def compose(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        query_type: Optional[QueryType] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Generate answer with citations
        
        Returns:
            {
                "answer": str,
                "citations": List[Dict],
                "tokens_used": int
            }
        """
        
        if not context_chunks:
            return {
                "answer": "I couldn't find any relevant information to answer your question. Please try rephrasing or contact support.",
                "citations": [],
                "tokens_used": 0
            }
        
        # Build context from chunks
        context = self._build_context(context_chunks)
        
        # Get appropriate system prompt
        system_prompt = self._get_system_prompt(query_type)
        
        # Build conversation context
        messages = self._build_messages(
            query=query,
            context=context,
            system_prompt=system_prompt,
            conversation_history=conversation_history
        )
        
        # Generate answer
        try:
            response = await llm_router.chat(
                messages=messages,
                temperature=0.3,  # Lower temperature for factual accuracy
                max_tokens=1000
            )
            
            answer = response["content"]
            tokens_used = response["tokens_used"]
            
            # Extract citations
            citations = self._extract_citations(answer, context_chunks)
            
            # Clean up citation markers from answer
            answer = self._clean_citation_markers(answer)
            
            logger.debug(
                f"Answer composed",
                extra={
                    "query_type": query_type.value if query_type else "unknown",
                    "context_chunks": len(context_chunks),
                    "citations": len(citations),
                    "tokens": tokens_used
                }
            )
            
            return {
                "answer": answer,
                "citations": citations,
                "tokens_used": tokens_used
            }
            
        except Exception as e:
            logger.error(f"Answer composition failed: {e}", exc_info=True)
            raise
    
    def _build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Build formatted context from chunks"""
        context_parts = []
        
        for i, chunk in enumerate(chunks, 1):
            text = chunk.get("text", "")
            source = chunk.get("metadata", {}).get("source", "Unknown")
            page = chunk.get("metadata", {}).get("page", "")
            
            page_info = f", Page {page}" if page else ""
            context_parts.append(
                f"[{i}] (Source: {source}{page_info})\n{text}\n"
            )
        
        return "\n".join(context_parts)
    
    def _build_messages(
        self,
        query: str,
        context: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, str]]:
        """Build message array for LLM"""
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history[-6:])  # Last 3 turns
        
        # Add current query with context
        user_message = f"""Context Information:
{context}

Question: {query}

Please provide a clear, accurate answer based on the context above. Cite your sources using [1], [2], etc. to reference the context sections."""
        
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def _extract_citations(
        self,
        answer: str,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract citations from answer"""
        citations = []
        
        # Find all citation markers [1], [2], etc.
        citation_pattern = r'\[(\d+)\]'
        cited_indices = set(re.findall(citation_pattern, answer))
        
        for idx_str in cited_indices:
            idx = int(idx_str) - 1  # Convert to 0-indexed
            
            if 0 <= idx < len(chunks):
                chunk = chunks[idx]
                citations.append({
                    "text": chunk.get("text", "")[:200] + "...",  # First 200 chars
                    "source": chunk.get("metadata", {}).get("source", "Unknown"),
                    "page": chunk.get("metadata", {}).get("page"),
                    "score": chunk.get("score", 0.0)
                })
        
        return citations
    
    def _clean_citation_markers(self, answer: str) -> str:
        """Clean up citation markers - optionally keep them or remove"""
        # Keep citation markers for now
        return answer
    
    def _get_system_prompt(self, query_type: Optional[QueryType]) -> str:
        """Get appropriate system prompt based on query type"""
        if query_type and query_type in self.system_prompts:
            return self.system_prompts[query_type]
        return self.system_prompts[QueryType.FACTUAL]
    
    @staticmethod
    def _get_factual_prompt() -> str:
        return """You are a knowledgeable course assistant. Your role is to provide accurate, concise answers based on the provided course materials.

Guidelines:
- Answer directly and factually
- Cite sources using [1], [2], etc.
- If information is not in the context, say so
- Be precise and avoid speculation
- Keep answers clear and structured"""
    
    @staticmethod
    def _get_conceptual_prompt() -> str:
        return """You are a course assistant specializing in explaining concepts. Your role is to help students understand complex topics.

Guidelines:
- Explain concepts clearly and thoroughly
- Use analogies or examples when helpful
- Break down complex ideas into simpler parts
- Cite sources using [1], [2], etc.
- Ensure explanations are accessible"""
    
    @staticmethod
    def _get_procedural_prompt() -> str:
        return """You are a course assistant specializing in step-by-step guidance. Your role is to provide clear instructions.

Guidelines:
- Present steps in a clear, numbered format
- Explain the purpose of each step
- Include any prerequisites or warnings
- Cite sources using [1], [2], etc.
- Be thorough but concise"""
    
    @staticmethod
    def _get_comparison_prompt() -> str:
        return """You are a course assistant specializing in comparative analysis. Your role is to highlight similarities and differences.

Guidelines:
- Clearly structure comparisons
- Highlight key similarities and differences
- Use tables or bullet points when appropriate
- Cite sources using [1], [2], etc.
- Be balanced and objective"""
    
    @staticmethod
    def _get_multi_hop_prompt() -> str:
        return """You are a course assistant specializing in complex reasoning. Your role is to synthesize information from multiple sources.

Guidelines:
- Address all parts of multi-part questions
- Show logical connections between concepts
- Synthesize information coherently
- Cite sources using [1], [2], etc.
- Ensure comprehensive coverage"""


# Singleton instance
answer_composer = AnswerComposer()