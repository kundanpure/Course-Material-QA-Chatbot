"""
Admin API Routes - Document management
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
import json
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import get_current_user, TenantContext, require_permission
from core.config import settings
from core.logging import logger
from db.session import get_db
from db.repository import DocumentRepository

router = APIRouter()


class DocumentUploadResponse(BaseModel):
    """Document upload response"""
    document_id: str
    filename: str
    status: str
    task_id: Optional[str] = None


class DocumentListResponse(BaseModel):
    """Document list response"""
    documents: List[dict]
    total: int
    skip: int
    limit: int


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    context: TenantContext = Depends(require_permission("upload")),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a document for processing
    
    Requires 'upload' permission
    """
    
    try:
        # Validate file type
        file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
        if f".{file_ext}" not in settings.SUPPORTED_FILE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Supported: {settings.SUPPORTED_FILE_TYPES}"
            )
        
        # Read file
        file_content = await file.read()
        file_size = len(file_content)
        
        # Validate size
        if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {settings.MAX_FILE_SIZE_MB}MB"
            )
        
        # Parse metadata
        metadata_dict = {}
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid metadata JSON"
                )
        
        # Upload to S3
        s3_key = await upload_to_s3(
            file_content=file_content,
            filename=file.filename,
            tenant_id=context.tenant_id
        )
        
        # Create document record
        doc_repo = DocumentRepository(db)
        document = await doc_repo.create(
            tenant_id=context.tenant_id,
            filename=file.filename,
            file_type=file_ext,
            file_size=file_size,
            s3_key=s3_key,
            metadata=metadata_dict
        )
        
        # Queue for processing
        from workers.ingestion_worker import process_document_task
        task = process_document_task.delay(
            document_id=document.id,
            tenant_id=context.tenant_id
        )
        
        logger.info(
            f"Document uploaded",
            extra={
                "document_id": document.id,
                "filename": file.filename,
                "size": file_size,
                "tenant_id": context.tenant_id
            }
        )
        
        return DocumentUploadResponse(
            document_id=document.id,
            filename=file.filename,
            status="processing",
            task_id=str(task.id)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to upload document"
        )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    context: TenantContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List documents for the current tenant
    """
    
    try:
        doc_repo = DocumentRepository(db)
        documents = await doc_repo.list_by_tenant(
            tenant_id=context.tenant_id,
            skip=skip,
            limit=limit
        )
        
        # Convert to dict
        docs_list = []
        for doc in documents:
            docs_list.append({
                "id": doc.id,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "status": doc.status,
                "chunk_count": doc.chunk_count,
                "created_at": doc.created_at.isoformat(),
                "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
                "metadata": doc.metadata
            })
        
        return DocumentListResponse(
            documents=docs_list,
            total=len(docs_list),
            skip=skip,
            limit=limit
        )
        
    except Exception as e:
        logger.error(f"Failed to list documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to list documents"
        )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    context: TenantContext = Depends(require_permission("admin")),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a document and all its chunks
    Requires admin permission
    """
    
    try:
        # TODO: Implement document deletion
        # - Delete from S3
        # - Delete from Qdrant
        # - Delete from Neo4j
        # - Delete from database
        
        raise HTTPException(
            status_code=501,
            detail="Document deletion not yet implemented"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document deletion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete document"
        )


async def upload_to_s3(
    file_content: bytes,
    filename: str,
    tenant_id: str
) -> str:
    """Upload file to S3 and return key"""
    import boto3
    from datetime import datetime
    
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION
    )
    
    # Generate S3 key
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    s3_key = f"{tenant_id}/documents/{timestamp}_{filename}"
    
    # Upload
    s3_client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=s3_key,
        Body=file_content,
        ContentType=get_content_type(filename)
    )
    
    logger.info(f"Uploaded to S3: {s3_key}")
    return s3_key


def get_content_type(filename: str) -> str:
    """Get content type from filename"""
    ext = filename.split(".")[-1].lower()
    content_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
        "md": "text/markdown",
        "html": "text/html"
    }
    return content_types.get(ext, "application/octet-stream")