"""
Reranker Service - Cross-encoder reranking for improved relevance
"""
from typing import List, Dict, Any
from sentence_transformers import CrossEncoder
import torch

from core.config import settings
from core.logging import logger
from observability.tracing import trace_agent_step


class RerankerService:
    """
    Rerank retrieved documents using a cross-encoder model
    Cross-encoders are more accurate than bi-encoders but slower
    """
    
    def __init__(self):
        self.model: CrossEncoder = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._load_model()
    
    def _load_model(self):
        """Load cross-encoder model"""
        try:
            self.model = CrossEncoder(
                settings.RERANKER_MODEL,
                max_length=512,
                device=self.device
            )
            logger.info(
                f"✅ Reranker model loaded: {settings.RERANKER_MODEL}",
                extra={"device": self.device}
            )
        except Exception as e:
            logger.error(f"Failed to load reranker model: {e}", exc_info=True)
            raise
    
    @trace_agent_step("reranker.rerank")
    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents by relevance to query
        
        Args:
            query: User query
            documents: List of document dicts with 'text' field
            top_k: Number of top documents to return (default: RERANKER_TOP_K)
        
        Returns:
            Reranked documents with updated scores
        """
        if not documents:
            return []
        
        if top_k is None:
            top_k = settings.RERANKER_TOP_K
        
        try:
            # Prepare query-document pairs
            pairs = [[query, doc.get("text", "")] for doc in documents]
            
            # Get relevance scores from cross-encoder
            scores = self.model.predict(
                pairs,
                show_progress_bar=False,
                batch_size=32
            )
            
            # Add reranker scores to documents
            for doc, score in zip(documents, scores):
                doc["rerank_score"] = float(score)
                # Keep original retrieval score
                if "score" in doc:
                    doc["retrieval_score"] = doc["score"]
                # Update score to reranker score
                doc["score"] = float(score)
            
            # Sort by reranker score
            reranked = sorted(
                documents,
                key=lambda x: x["rerank_score"],
                reverse=True
            )
            
            logger.debug(
                f"Reranked {len(documents)} documents",
                extra={
                    "top_score": reranked[0]["rerank_score"] if reranked else 0,
                    "returning": min(top_k, len(reranked))
                }
            )
            
            return reranked[:top_k]
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}", exc_info=True)
            # Return original documents if reranking fails
            return documents[:top_k]
    
    async def rerank_batch(
        self,
        queries: List[str],
        documents_list: List[List[Dict[str, Any]]],
        top_k: int = None
    ) -> List[List[Dict[str, Any]]]:
        """
        Rerank multiple query-document sets in batch
        More efficient for multiple queries
        """
        if top_k is None:
            top_k = settings.RERANKER_TOP_K
        
        results = []
        for query, documents in zip(queries, documents_list):
            reranked = await self.rerank(query, documents, top_k)
            results.append(reranked)
        
        return results
    
    def get_relevance_score(
        self,
        query: str,
        text: str
    ) -> float:
        """
        Get relevance score for a single query-text pair
        Useful for answer validation
        """
        try:
            score = self.model.predict([[query, text]])[0]
            return float(score)
        except Exception as e:
            logger.error(f"Failed to get relevance score: {e}")
            return 0.0


# Singleton instance
reranker_service = RerankerService()