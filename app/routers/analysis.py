import json
import logging
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.auth.dependency import get_current_user
from app.agent.graph import run_analysis_stream
from app.db.postgres import (
    create_document_record,
    get_user_document,
    get_document_by_id,
    update_document_analysis,
)
from app.db.mongo import (
    save_conversation,
    get_conversation_from_document,
)
from app.services.storage import upload_pdf, get_signed_url, delete_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])

# Maximum PDF size: 20MB
MAX_FILE_SIZE = 20 * 1024 * 1024

async def _analysis_event_generator(
    pdf_bytes: bytes,
    user_id: str,
    document_id: str,
    filename: str,
) -> AsyncIterator[str]:

    chunk_results = []
    final_report = None

    try:
        async for event in run_analysis_stream(
            pdf_bytes=pdf_bytes,
            user_id=user_id,
            document_id=document_id,
            document_name=filename,
        ):
            if event["event"] == "chunk_done":
                chunk_results.append(event["data"])
            elif event["event"] == "synthesis_done":
                final_report = event["data"]

            yield f"data: {json.dumps(event)}\n\n"

    except Exception as exc:
        logger.error("Stream error for document %s: %s", document_id, exc)
        yield f"data: {json.dumps({'event': 'error', 'data': str(exc)})}\n\n"

    finally:
        try:
            await save_conversation(
                user_id=user_id,
                document_id=document_id,
                document_name=filename,
                chunks=chunk_results,
                report=final_report,
            )
            if final_report:
                await update_document_analysis(
                    document_id=document_id,
                    overall_risk=final_report.get("overall_risk", "Unknown"),
                )
            logger.info("Saved results for document %s to MongoDB", document_id)
        except Exception as save_exc:
            logger.error("Failed to save results for %s: %s", document_id, save_exc)


@router.post("/upload")
async def upload_and_analyze(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted.",
        )

    pdf_bytes = await file.read()

    if len(pdf_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 20MB limit.",
        )

    if len(pdf_bytes) < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File appears to be empty or corrupt.",
        )

    document_id = str(uuid.uuid4())
    user_id = user["id"]
    filename = file.filename
    storage_path = upload_pdf(
        user_id=user_id,
        document_id=document_id,
        filename=filename,
        pdf_bytes=pdf_bytes,
    )

    await create_document_record(
        document_id=document_id,
        user_id=user_id,
        filename=filename,
        storage=storage_path,
        file_size_bytes=len(pdf_bytes),
    )

    logger.info("Starting analysis for document %s (user %s)", document_id, user_id)

    return StreamingResponse(
        _analysis_event_generator(
            pdf_bytes=pdf_bytes,
            user_id=user_id,
            document_id=document_id,
            filename=filename,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no", 
            "Connection": "keep-alive",
        },
    )


@router.get("/history")
async def get_history(user: dict = Depends(get_current_user)):
    documents = await get_user_document(user["id"])
    return {"documents": documents}


@router.get("/{document_id}")
async def get_analysis_result(
    document_id: str,
    user: dict = Depends(get_current_user),
):
    doc = await get_document_by_id(document_id, user["id"])
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    conversation = await get_conversation_from_document(document_id, user["id"])
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis results not found. The analysis may still be running.",
        )

    pdf_url = get_signed_url(doc["storage_path"])

    return {
        "document": doc,
        "pdf_url": pdf_url,
        "conversation": conversation,
    }


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(
    document_id: str,
    user: dict = Depends(get_current_user),
):
    doc = await get_document_by_id(document_id, user["id"])
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    delete_pdf(doc["storage_path"])

    from app.db.postgres import get_supabase_admin
    get_supabase_admin().table("documents").delete().eq("id", document_id).execute()

    from app.db.mongo import get_db
    await get_db().conversations.delete_one({"document_id": document_id})

    logger.info("Deleted document %s for user %s", document_id, user["id"])