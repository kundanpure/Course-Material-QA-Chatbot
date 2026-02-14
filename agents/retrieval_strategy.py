"""
Retrieval Strategy Agent - Adaptive multi-modal retrieval
Innovation: Combines Vector Search, Keyword Search, and Knowledge Graph (GraphRAG)
"""
from typing import List, Dict, Optional
from enum import Enum

from core.config import settings
from core.logging import logger
from agents.query_classifier import QueryType
from services.embedding_service import embedding_service
from observability.tracing import trace_agent_step


class RetrievalStrategy:
    """
    Innovation: Adaptive retrieval that chooses the best method based on query type
    
    Strategies:
    1. vector_only: Pure semantic search (fast, good for factual queries)
    2. hybrid: Combines semantic + keyword search (best for most queries)  
    3. graph_enhanced: Adds knowledge graph traversal (for relationships/comparisons)
    """
    
    def __init__(self):
        from services.retrieval_service import retrieval_service
        self.retrieval_service = retrieval_service
    
    @trace_agent_step("retrieval.retrieve")
    async def retrieve(
        self,
        query: str,
        tenant_id: str,
        strategy: str,
        query_type: QueryType,
        top_k: int = 10
    ) -> List[Dict]:
        """
        Main retrieval method - routes to appropriate strategy
        """
        logger.info(
            f"Retrieving with strategy: {strategy}",
            extra={"query_type": query_type.value}
        )
        
        if strategy == "vector_only":
            return await self._vector_search(query, tenant_id, top_k)
        
        elif strategy == "hybrid":
            return await self._hybrid_search(query, tenant_id, top_k)
        
        elif strategy == "graph_enhanced":
            return await self._graph_enhanced_search(query, tenant_id, top_k)
        
        else:
            logger.warning(f"Unknown strategy {strategy}, falling back to hybrid")
            return await self._hybrid_search(query, tenant_id, top_k)
    
    async def _vector_search(
        self,
        query: str,
        tenant_id: str,
        top_k: int
    ) -> List[Dict]:
        """
        Pure vector/semantic search using Qdrant
        Fast and effective for factual queries
        """
        # Generate query embedding
        query_embedding = await embedding_service.embed_query(query)
        
        # Search in Qdrant with tenant filter
        results = await self.retrieval_service.vector_search(
            embedding=query_embedding,
            tenant_id=tenant_id,
            top_k=top_k,
            score_threshold=settings.RETRIEVAL_MIN_SCORE
        )
        
        logger.debug(f"Vector search returned {len(results)} results")
        return results
    
    async def _hybrid_search(
        self,
        query: str,
        tenant_id: str,
        top_k: int
    ) -> List[Dict]:
        """
        Innovation: Hybrid search combining semantic + keyword search
        Uses Reciprocal Rank Fusion (RRF) to merge results
        
        Formula: RRF_score = Σ 1/(k + rank_i) for each ranking
        where k=60 is a constant, rank_i is the position in each ranking
        """
        # 1. Vector search
        query_embedding = await embedding_service.embed_query(query)
        vector_results = await self.retrieval_service.vector_search(
            embedding=query_embedding,
            tenant_id=tenant_id,
            top_k=top_k * 2,  # Get more candidates
            score_threshold=settings.RETRIEVAL_MIN_SCORE * 0.8  # Lower threshold
        )
        
        # 2. Keyword search (BM25-like sparse search)
        keyword_results = await self.retrieval_service.keyword_search(
            query=query,
            tenant_id=tenant_id,
            top_k=top_k * 2
        )
        
        # 3. Merge using Reciprocal Rank Fusion
        merged = self._reciprocal_rank_fusion(
            vector_results,
            keyword_results,
            alpha=settings.HYBRID_SEARCH_ALPHA  # Weight towards semantic
        )
        
        logger.debug(
            f"Hybrid search merged {len(merged)} results",
            extra={
                "vector_count": len(vector_results),
                "keyword_count": len(keyword_results)
            }
        )
        
        return merged[:top_k]
    
    async def _graph_enhanced_search(
        self,
        query: str,
        tenant_id: str,
        top_k: int
    ) -> List[Dict]:
        """
        Innovation: GraphRAG - Combines vector search with knowledge graph traversal
        
        Process:
        1. Find initial relevant chunks via vector search
        2. Extract entities from those chunks
        3. Traverse knowledge graph to find related concepts
        4. Retrieve chunks for those related concepts
        5. Merge and deduplicate
        
        Perfect for: comparisons, multi-hop reasoning, relationship queries
        """
        if not settings.ENABLE_GRAPH_RETRIEVAL:
            logger.warning("Graph retrieval disabled, falling back to hybrid")
            return await self._hybrid_search(query, tenant_id, top_k)
        
        # Step 1: Initial vector search
        query_embedding = await embedding_service.embed_query(query)
        initial_results = await self.retrieval_service.vector_search(
            embedding=query_embedding,
            tenant_id=tenant_id,
            top_k=5,  # Get top candidates
            score_threshold=settings.RETRIEVAL_MIN_SCORE
        )
        
        if not initial_results:
            logger.warning("No initial results for graph expansion")
            return []
        
        # Step 2: Extract entities from initial results
        entities = await self._extract_entities(initial_results)
        logger.debug(f"Extracted {len(entities)} entities for graph traversal")
        
        # Step 3: Traverse knowledge graph
        related_concepts = await self.retrieval_service.traverse_knowledge_graph(
            entities=entities,
            tenant_id=tenant_id,
            max_depth=2  # 2-hop traversal
        )
        
        # Step 4: Retrieve chunks for related concepts
        expanded_results = []
        for concept in related_concepts:
            concept_results = await self.retrieval_service.search_by_metadata(
                metadata_filter={"concept": concept},
                tenant_id=tenant_id,
                top_k=3
            )
            expanded_results.extend(concept_results)
        
        # Step 5: Merge and deduplicate
        all_results = initial_results + expanded_results
        deduplicated = self._deduplicate_results(all_results)
        
        # Rerank by relevance to original query
        reranked = await self._rerank_by_query_relevance(
            query,
            query_embedding,
            deduplicated
        )
        
        logger.info(
            f"Graph-enhanced search completed",
            extra={
                "initial": len(initial_results),
                "expanded": len(expanded_results),
                "final": len(reranked)
            }
        )
        
        return reranked[:top_k]
    
    def _reciprocal_rank_fusion(
        self,
        results1: List[Dict],
        results2: List[Dict],
        alpha: float = 0.7,
        k: int = 60
    ) -> List[Dict]:
        """
        Merge two result sets using Reciprocal Rank Fusion
        alpha: weight for first result set (0-1)
        """
        scores = {}
        
        # Score from first result set
        for rank, result in enumerate(results1, start=1):
            doc_id = result.get("id") or result.get("chunk_id")
            scores[doc_id] = scores.get(doc_id, 0) + alpha * (1 / (k + rank))
            if doc_id not in [r.get("id") or r.get("chunk_id") for r in scores.values() if isinstance(r, dict)]:
                scores[doc_id] = {"data": result, "score": scores[doc_id]}
        
        # Score from second result set  
        for rank, result in enumerate(results2, start=1):
            doc_id = result.get("id") or result.get("chunk_id")
            if doc_id in scores and isinstance(scores[doc_id], dict):
                scores[doc_id]["score"] += (1 - alpha) * (1 / (k + rank))
            else:
                score_val = (1 - alpha) * (1 / (k + rank))
                scores[doc_id] = {"data": result, "score": score_val}
        
        # Sort by fused score
        merged = sorted(
            [v for v in scores.values() if isinstance(v, dict)],
            key=lambda x: x["score"],
            reverse=True
        )
        
        return [item["data"] for item in merged]
    
    async def _extract_entities(self, chunks: List[Dict]) -> List[str]:
        """
        Extract named entities from chunks for graph traversal
        Uses simple regex + keyword extraction for now
        In production, use NER model or LLM extraction
        """
        entities = set()
        
        for chunk in chunks:
            text = chunk.get("text", "")
            
            # Extract capitalized phrases (simple NER)
            import re
            capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
            entities.update(capitalized)
            
            # Extract from metadata if available
            metadata = chunk.get("metadata", {})
            if "concepts" in metadata:
                entities.update(metadata["concepts"])
        
        return list(entities)[:20]  # Limit to top 20 entities
    
    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicate chunks by ID"""
        seen = set()
        deduplicated = []
        
        for result in results:
            doc_id = result.get("id") or result.get("chunk_id")
            if doc_id not in seen:
                seen.add(doc_id)
                deduplicated.append(result)
        
        return deduplicated
    
    async def _rerank_by_query_relevance(
        self,
        query: str,
        query_embedding: List[float],
        results: List[Dict]
    ) -> List[Dict]:
        """Rerank results by semantic similarity to query"""
        import numpy as np
        
        query_vec = np.array(query_embedding)
        
        for result in results:
            chunk_embedding = result.get("embedding")
            if chunk_embedding:
                chunk_vec = np.array(chunk_embedding)
                similarity = np.dot(query_vec, chunk_vec) / (
                    np.linalg.norm(query_vec) * np.linalg.norm(chunk_vec)
                )
                result["query_similarity"] = float(similarity)
            else:
                result["query_similarity"] = 0.0
        
        # Sort by similarity
        results.sort(key=lambda x: x.get("query_similarity", 0), reverse=True)
        
        return results