"""
Retrieval Service - Vector DB (Qdrant) and Knowledge Graph (Neo4j) integration
"""
from typing import List, Dict, Optional, Any
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, 
    FieldCondition, MatchValue, ScoredPoint
)
from neo4j import AsyncGraphDatabase

from core.config import settings
from core.logging import logger
from observability.tracing import trace_agent_step


class RetrievalService:
    """
    Handles all retrieval operations:
    - Vector search (Qdrant)
    - Keyword search (sparse vectors)
    - Knowledge graph traversal (Neo4j)
    """
    
    def __init__(self):
        self.qdrant_client: Optional[AsyncQdrantClient] = None
        self.neo4j_driver = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize connections to Qdrant and Neo4j"""
        if self._initialized:
            return
        
        try:
            # Initialize Qdrant
            self.qdrant_client = AsyncQdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                api_key=settings.QDRANT_API_KEY,
                timeout=30
            )
            
            # Create collection if it doesn't exist
            await self._ensure_collection_exists()
            
            logger.info("✅ Qdrant connection established")
            
            # Initialize Neo4j
            self.neo4j_driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            
            # Test connection
            async with self.neo4j_driver.session() as session:
                await session.run("RETURN 1")
            
            logger.info("✅ Neo4j connection established")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize retrieval service: {e}", exc_info=True)
            raise
    
    async def close(self):
        """Close connections"""
        if self.qdrant_client:
            await self.qdrant_client.close()
        if self.neo4j_driver:
            await self.neo4j_driver.close()
        logger.info("Retrieval service connections closed")
    
    async def _ensure_collection_exists(self):
        """Create Qdrant collection if it doesn't exist"""
        try:
            collections = await self.qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if settings.QDRANT_COLLECTION_NAME not in collection_names:
                await self.qdrant_client.create_collection(
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=settings.VECTOR_DIMENSION,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created Qdrant collection: {settings.QDRANT_COLLECTION_NAME}")
        except Exception as e:
            logger.warning(f"Error checking/creating collection: {e}")
    
    @trace_agent_step("retrieval.vector_search")
    async def vector_search(
        self,
        embedding: List[float],
        tenant_id: str,
        top_k: int = 10,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search in Qdrant
        Multi-tenant: Filters by tenant_id
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # Search with tenant filter
            results = await self.qdrant_client.search(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                query_vector=embedding,
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="tenant_id",
                            match=MatchValue(value=tenant_id)
                        )
                    ]
                )
            )
            
            # Convert to standard format
            chunks = []
            for hit in results:
                chunks.append({
                    "id": str(hit.id),
                    "text": hit.payload.get("text", ""),
                    "score": float(hit.score),
                    "metadata": {
                        "source": hit.payload.get("source", ""),
                        "page": hit.payload.get("page"),
                        "chunk_index": hit.payload.get("chunk_index"),
                        **hit.payload.get("metadata", {})
                    },
                    "embedding": hit.vector if hasattr(hit, 'vector') else None
                })
            
            logger.debug(
                f"Vector search returned {len(chunks)} results",
                extra={"tenant_id": tenant_id, "top_k": top_k}
            )
            
            return chunks
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}", exc_info=True)
            return []
    
    @trace_agent_step("retrieval.keyword_search")
    async def keyword_search(
        self,
        query: str,
        tenant_id: str,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Keyword-based search using BM25-like scoring
        This is a simplified version - in production, use a proper sparse vector index
        """
        # For now, we'll do a simple text match in Qdrant
        # In production, you'd want to use Elasticsearch or a dedicated BM25 index
        
        try:
            # Extract keywords from query
            keywords = query.lower().split()
            
            # Search with text filter (simplified BM25)
            # Note: Qdrant doesn't have built-in BM25, so this is approximate
            # Consider adding Elasticsearch for true keyword search
            
            results = await self.qdrant_client.scroll(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="tenant_id",
                            match=MatchValue(value=tenant_id)
                        )
                    ]
                ),
                limit=top_k * 3  # Get more candidates
            )
            
            # Score by keyword overlap
            scored_results = []
            for point in results[0]:
                text = point.payload.get("text", "").lower()
                score = sum(1 for kw in keywords if kw in text) / len(keywords)
                
                if score > 0:
                    scored_results.append({
                        "id": str(point.id),
                        "text": point.payload.get("text", ""),
                        "score": score,
                        "metadata": point.payload.get("metadata", {})
                    })
            
            # Sort by score and return top_k
            scored_results.sort(key=lambda x: x["score"], reverse=True)
            
            logger.debug(f"Keyword search returned {len(scored_results[:top_k])} results")
            
            return scored_results[:top_k]
            
        except Exception as e:
            logger.error(f"Keyword search failed: {e}", exc_info=True)
            return []
    
    @trace_agent_step("retrieval.search_by_metadata")
    async def search_by_metadata(
        self,
        metadata_filter: Dict[str, Any],
        tenant_id: str,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search by metadata fields (e.g., concept, source, etc.)
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # Build filter conditions
            conditions = [
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=tenant_id)
                )
            ]
            
            for key, value in metadata_filter.items():
                conditions.append(
                    FieldCondition(
                        key=f"metadata.{key}",
                        match=MatchValue(value=value)
                    )
                )
            
            results = await self.qdrant_client.scroll(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                scroll_filter=Filter(must=conditions),
                limit=top_k
            )
            
            chunks = []
            for point in results[0]:
                chunks.append({
                    "id": str(point.id),
                    "text": point.payload.get("text", ""),
                    "score": 1.0,  # No relevance score for metadata search
                    "metadata": point.payload.get("metadata", {})
                })
            
            return chunks
            
        except Exception as e:
            logger.error(f"Metadata search failed: {e}", exc_info=True)
            return []
    
    @trace_agent_step("retrieval.traverse_knowledge_graph")
    async def traverse_knowledge_graph(
        self,
        entities: List[str],
        tenant_id: str,
        max_depth: int = 2
    ) -> List[str]:
        """
        Traverse knowledge graph to find related concepts
        Returns list of related entity names
        """
        if not self._initialized:
            await self.initialize()
        
        if not entities:
            return []
        
        try:
            async with self.neo4j_driver.session() as session:
                # Cypher query to find related entities
                query = """
                MATCH (start)-[r*1..%d]-(related)
                WHERE start.name IN $entities 
                  AND start.tenant_id = $tenant_id
                  AND related.tenant_id = $tenant_id
                RETURN DISTINCT related.name as name, 
                       type(r) as relationship_type,
                       length(r) as distance
                ORDER BY distance ASC
                LIMIT 20
                """ % max_depth
                
                result = await session.run(
                    query,
                    entities=entities,
                    tenant_id=tenant_id
                )
                
                related_entities = []
                async for record in result:
                    if record["name"]:
                        related_entities.append(record["name"])
                
                logger.debug(
                    f"Graph traversal found {len(related_entities)} related entities",
                    extra={
                        "input_entities": len(entities),
                        "max_depth": max_depth
                    }
                )
                
                return related_entities
                
        except Exception as e:
            logger.error(f"Knowledge graph traversal failed: {e}", exc_info=True)
            return []
    
    async def add_document_chunks(
        self,
        chunks: List[Dict[str, Any]],
        tenant_id: str
    ) -> bool:
        """
        Add document chunks to Qdrant
        Each chunk should have: text, embedding, metadata
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            points = []
            for i, chunk in enumerate(chunks):
                point = PointStruct(
                    id=chunk.get("id", f"{tenant_id}_{i}"),
                    vector=chunk["embedding"],
                    payload={
                        "text": chunk["text"],
                        "tenant_id": tenant_id,
                        "source": chunk.get("source", ""),
                        "page": chunk.get("page"),
                        "chunk_index": i,
                        "metadata": chunk.get("metadata", {})
                    }
                )
                points.append(point)
            
            # Batch upload
            await self.qdrant_client.upsert(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points=points
            )
            
            logger.info(
                f"Added {len(points)} chunks to Qdrant",
                extra={"tenant_id": tenant_id}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to add chunks: {e}", exc_info=True)
            return False
    
    async def add_knowledge_graph_entities(
        self,
        entities: List[Dict[str, Any]],
        tenant_id: str
    ) -> bool:
        """
        Add entities and relationships to Neo4j knowledge graph
        entities format: [{"name": str, "type": str, "properties": dict, "relationships": []}]
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            async with self.neo4j_driver.session() as session:
                for entity in entities:
                    # Create entity node
                    await session.run(
                        """
                        MERGE (e:Entity {name: $name, tenant_id: $tenant_id})
                        SET e.type = $type,
                            e += $properties
                        """,
                        name=entity["name"],
                        tenant_id=tenant_id,
                        type=entity.get("type", "Concept"),
                        properties=entity.get("properties", {})
                    )
                    
                    # Create relationships
                    for rel in entity.get("relationships", []):
                        await session.run(
                            """
                            MATCH (a:Entity {name: $from, tenant_id: $tenant_id})
                            MATCH (b:Entity {name: $to, tenant_id: $tenant_id})
                            MERGE (a)-[r:%s]->(b)
                            SET r += $properties
                            """ % rel["type"],
                            from_name=entity["name"],
                            to=rel["to"],
                            tenant_id=tenant_id,
                            properties=rel.get("properties", {})
                        )
            
            logger.info(f"Added {len(entities)} entities to knowledge graph")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add graph entities: {e}", exc_info=True)
            return False


# Singleton instance
retrieval_service = RetrievalService()