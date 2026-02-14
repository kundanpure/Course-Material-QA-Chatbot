"""
Embedding Service - Generate embeddings for queries and documents
"""
from typing import List, Optional, Dict, Any
import asyncio
from functools import lru_cache
import numpy as np

from openai import AsyncOpenAI
from sentence_transformers import SentenceTransformer

from core.config import settings
from core.logging import logger
from observability.tracing import trace_agent_step
from services.cache_service import cache_service


class EmbeddingService:
    """
    Service for generating embeddings
    Supports: OpenAI API, local sentence-transformers
    """
    
    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.local_model: Optional[SentenceTransformer] = None
        self.use_local = False  # Set to True to use local model
        
        # Load local model if needed (for fallback or cost savings)
        if self.use_local:
            self._load_local_model()
    
    def _load_local_model(self):
        """Load local sentence transformer model"""
        try:
            # Using same model as cache for consistency
            self.local_model = SentenceTransformer(
                'sentence-transformers/all-MiniLM-L6-v2'
            )
            logger.info("Local embedding model loaded")
        except Exception as e:
            logger.error(f"Failed to load local model: {e}")
    
    @trace_agent_step("embedding.embed_query")
    async def embed_query(
        self,
        text: str,
        use_cache: bool = True
    ) -> List[float]:
        """
        Generate embedding for a single query
        Uses caching to avoid redundant API calls
        """
        # Check cache first
        if use_cache:
            cache_key = f"embedding:query:{hash(text)}"
            cached = await cache_service.get(cache_key)
            if cached:
                import json
                return json.loads(cached)
        
        # Generate embedding
        if self.use_local and self.local_model:
            embedding = self._embed_local([text])[0]
        else:
            embedding = await self._embed_openai([text])
            embedding = embedding[0]
        
        # Cache the result
        if use_cache:
            import json
            await cache_service.set(
                cache_key,
                json.dumps(embedding),
                ttl=86400  # 24 hours
            )
        
        return embedding
    
    @trace_agent_step("embedding.embed_documents")
    async def embed_documents(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple documents with batching
        """
        if not texts:
            return []
        
        logger.info(f"Generating embeddings for {len(texts)} documents")
        
        # Process in batches to avoid API limits
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            if self.use_local and self.local_model:
                batch_embeddings = self._embed_local(batch)
            else:
                batch_embeddings = await self._embed_openai(batch)
            
            all_embeddings.extend(batch_embeddings)
            
            # Rate limiting
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)
        
        logger.info(f"Generated {len(all_embeddings)} embeddings")
        return all_embeddings
    
    async def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API"""
        try:
            response = await self.openai_client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=texts
            )
            
            embeddings = [item.embedding for item in response.data]
            
            logger.debug(
                f"OpenAI embeddings generated",
                extra={
                    "model": settings.OPENAI_EMBEDDING_MODEL,
                    "count": len(embeddings),
                    "tokens": response.usage.total_tokens
                }
            )
            
            return embeddings
            
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}", exc_info=True)
            
            # Fallback to local model if available
            if self.local_model:
                logger.warning("Falling back to local embedding model")
                return self._embed_local(texts)
            raise
    
    def _embed_local(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using local model"""
        embeddings = self.local_model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False
        )
        return embeddings.tolist()
    
    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
    
    @staticmethod
    def normalize_embedding(embedding: List[float]) -> List[float]:
        """Normalize embedding to unit length"""
        vec = np.array(embedding)
        norm = np.linalg.norm(vec)
        if norm == 0:
            return embedding
        return (vec / norm).tolist()


# Singleton instance
embedding_service = EmbeddingService()