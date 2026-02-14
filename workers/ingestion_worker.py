"""
Celery Worker - Document Ingestion Pipeline
"""
from celery import Celery
import asyncio
from typing import List, Dict, Any
import boto3

from core.config import settings
from core.logging import logger

# Initialize Celery
celery_app = Celery(
    'course_qa_worker',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
)


@celery_app.task(bind=True, name='process_document')
def process_document_task(self, document_id: str, tenant_id: str):
    """
    Process document: extract text, chunk, embed, store
    """
    try:
        logger.info(f"Starting document processing: {document_id}")
        
        # Run async processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            process_document_async(document_id, tenant_id)
        )
        loop.close()
        
        logger.info(f"Document processing completed: {document_id}")
        return result
        
    except Exception as e:
        logger.error(f"Document processing failed: {e}", exc_info=True)
        
        # Update document status to failed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            update_document_status(document_id, "failed", str(e))
        )
        loop.close()
        
        raise


async def process_document_async(document_id: str, tenant_id: str) -> Dict[str, Any]:
    """Async document processing"""
    from db.session import AsyncSessionLocal
    from db.repository import DocumentRepository
    from services.embedding_service import embedding_service
    from services.retrieval_service import retrieval_service
    
    async with AsyncSessionLocal() as session:
        doc_repo = DocumentRepository(session)
        
        # Get document
        from db.models import Document
        from sqlalchemy import select
        result = await session.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise ValueError(f"Document not found: {document_id}")
        
        # Update status to processing
        await doc_repo.update_status(document_id, "processing")
        await session.commit()
        
        # Download from S3
        file_content = download_from_s3(document.s3_key)
        
        # Extract text based on file type
        text = extract_text(file_content, document.file_type)
        
        # Chunk the text
        chunks = chunk_text(text, document.filename)
        
        # Generate embeddings
        chunk_texts = [chunk["text"] for chunk in chunks]
        embeddings = await embedding_service.embed_documents(chunk_texts)
        
        # Add embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding
            chunk["vector_id"] = f"{document_id}_{chunk['chunk_index']}"
        
        # Store in Qdrant
        await retrieval_service.initialize()
        await retrieval_service.add_document_chunks(
            chunks=chunks,
            tenant_id=tenant_id
        )
        
        # Store chunks in database
        await doc_repo.add_chunks(document_id, chunks)
        
        # Extract entities and build knowledge graph
        if settings.ENABLE_GRAPH_RETRIEVAL:
            entities = await extract_entities_from_text(text)
            if entities:
                await retrieval_service.add_knowledge_graph_entities(
                    entities=entities,
                    tenant_id=tenant_id
                )
        
        # Update status to completed
        await doc_repo.update_status(
            document_id,
            "completed",
            chunk_count=len(chunks)
        )
        await session.commit()
        
        return {
            "document_id": document_id,
            "chunks_created": len(chunks),
            "status": "completed"
        }


def download_from_s3(s3_key: str) -> bytes:
    """Download file from S3"""
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION
    )
    
    response = s3_client.get_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=s3_key
    )
    
    return response['Body'].read()


def extract_text(file_content: bytes, file_type: str) -> str:
    """Extract text from file"""
    from io import BytesIO
    
    if file_type == "pdf":
        # Use PyPDF2
        from PyPDF2 import PdfReader
        pdf_file = BytesIO(file_content)
        reader = PdfReader(pdf_file)
        
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n\n"
        
        return text
    
    elif file_type == "docx":
        # Use python-docx
        from docx import Document
        docx_file = BytesIO(file_content)
        doc = Document(docx_file)
        
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    
    elif file_type in ["txt", "md"]:
        # Plain text
        return file_content.decode('utf-8')
    
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def chunk_text(text: str, source: str) -> List[Dict[str, Any]]:
    """Chunk text into smaller pieces"""
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    text_chunks = splitter.split_text(text)
    
    chunks = []
    for i, chunk_text in enumerate(text_chunks):
        chunks.append({
            "chunk_index": i,
            "text": chunk_text,
            "source": source,
            "metadata": {
                "source": source,
                "chunk_index": i
            }
        })
    
    return chunks


async def extract_entities_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Extract entities for knowledge graph
    Simplified version - in production, use NER model or LLM
    """
    # For now, return empty list
    # TODO: Implement proper entity extraction
    return []


async def update_document_status(
    document_id: str,
    status: str,
    error_message: str = None
):
    """Update document status"""
    from db.session import AsyncSessionLocal
    from db.repository import DocumentRepository
    
    async with AsyncSessionLocal() as session:
        doc_repo = DocumentRepository(session)
        await doc_repo.update_status(
            document_id,
            status,
            error_message=error_message
        )
        await session.commit()


# Celery beat schedule (periodic tasks)
celery_app.conf.beat_schedule = {
    'cleanup-old-logs': {
        'task': 'cleanup_old_logs',
        'schedule': 86400.0,  # Daily
    },
}


@celery_app.task(name='cleanup_old_logs')
def cleanup_old_logs():
    """Cleanup old query logs (retention policy)"""
    # TODO: Implement log cleanup
    logger.info("Log cleanup task executed")