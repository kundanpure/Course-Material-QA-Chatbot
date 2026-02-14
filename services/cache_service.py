"""
Semantic Cache Service - Innovation: Cache based on semantic similarity
Uses GPTCache with Redis backend for intelligent caching
"""
import hashlib
import json
from typing import Optional, Dict, Any
import redis.asyncio as redis
from sentence_transformers import SentenceTransformer
import numpy as np

from core.config import settings
from core.logging import logger


class SemanticCacheService:
    """
    Innovation: Semantic caching - cache hits based on meaning, not exact match
    
    Example:
    - Query 1: "What is machine learning?"
    - Query 2: "Can you explain machine learning?" 
    -> These should hit the same cache (high semantic similarity)
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.embedding_model: Optional[SentenceTransformer] = None
        self.similarity_threshold = settings.SEMANTIC_CACHE_THRESHOLD
        
    async def initialize(self):
        """Initialize Redis connection and embedding model"""
        try:
            # Initialize Redis
            self.redis_client = await redis.from_url(
                settings.redis_url,
                decode_responses=False,  # We'll handle encoding
                max_connections=20
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info("✅ Redis cache connection established")
            
            # Load lightweight embedding model for cache keys
            # Using a small model for speed (cache should be fast!)
            self.embedding_model = SentenceTransformer(
                'sentence-transformers/all-MiniLM-L6-v2'  # 384 dimensions, fast
            )
            logger.info("✅ Cache embedding model loaded")
            
        except Exception as e:
            logger.error(f"Failed to initialize cache: {e}", exc_info=True)
            raise
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis cache connection closed")
    
    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for cache key"""
        return self.embedding_model.encode(text, convert_to_numpy=True)
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
    
    async def get_semantic(
        self,
        query: str,
        tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached result using semantic similarity
        
        Returns cached data if similarity >= threshold, None otherwise
        """
        try:
            # Generate query embedding
            query_embedding = self._generate_embedding(query)
            
            # Get all cache keys for this tenant
            pattern = f"semantic_cache:{tenant_id}:*"
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if not keys:
                logger.debug(f"No cache entries found for tenant {tenant_id}")
                return None
            
            # Find best matching cache entry
            best_match = None
            best_similarity = 0.0
            
            for key in keys:
                # Get cached query embedding and data
                cached_data = await self.redis_client.get(key)
                if not cached_data:
                    continue
                
                cached = json.loads(cached_data.decode('utf-8'))
                cached_embedding = np.array(cached["query_embedding"])
                
                # Calculate similarity
                similarity = self._cosine_similarity(query_embedding, cached_embedding)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = cached
            
            # Check if best match meets threshold
            if best_similarity >= self.similarity_threshold:
                logger.info(
                    f"Semantic cache HIT",
                    extra={
                        "similarity": round(best_similarity, 3),
                        "cached_query": best_match["query"][:100]
                    }
                )
                
                result = best_match["data"]
                result["similarity"] = best_similarity
                return result
            
            logger.debug(
                f"Semantic cache MISS",
                extra={
                    "best_similarity": round(best_similarity, 3),
                    "threshold": self.similarity_threshold
                }
            )
            return None
            
        except Exception as e:
            logger.error(f"Semantic cache get error: {e}", exc_info=True)
            return None
    
    async def set_semantic(
        self,
        query: str,
        tenant_id: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None
    ):
        """
        Cache a query result with semantic indexing
        """
        try:
            # Generate query embedding
            query_embedding = self._generate_embedding(query)
            
            # Create cache key (hash of query for uniqueness)
            query_hash = hashlib.md5(query.encode()).hexdigest()[:12]
            cache_key = f"semantic_cache:{tenant_id}:{query_hash}"
            
            # Store embedding and data together
            cache_value = {
                "query": query,
                "query_embedding": query_embedding.tolist(),
                "data": data,
                "timestamp": str(np.datetime64('now'))
            }
            
            # Serialize and store
            await self.redis_client.set(
                cache_key,
                json.dumps(cache_value).encode('utf-8'),
                ex=ttl or settings.CACHE_TTL
            )
            
            logger.debug(f"Cached query result: {query[:100]}")
            
        except Exception as e:
            logger.error(f"Semantic cache set error: {e}", exc_info=True)
    
    async def invalidate_tenant(self, tenant_id: str):
        """Invalidate all cache entries for a tenant"""
        try:
            pattern = f"semantic_cache:{tenant_id}:*"
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                await self.redis_client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache entries for tenant {tenant_id}")
                
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}", exc_info=True)
    
    # Standard string-based caching (for exact matches)
    async def get(self, key: str) -> Optional[str]:
        """Get exact cache entry"""
        try:
            value = await self.redis_client.get(key)
            return value.decode('utf-8') if value else None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None
    ):
        """Set exact cache entry"""
        try:
            await self.redis_client.set(
                key,
                value,
                ex=ttl or settings.CACHE_TTL
            )
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    async def delete(self, key: str):
        """Delete cache entry"""
        try:
            await self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            return await self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error: {e}")
            return False


# Singleton instance
cache_service = SemanticCacheService()