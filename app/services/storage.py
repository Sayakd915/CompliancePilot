import logging
from app.config import settings
from app.db.postgres import get_supabase_admin

logger = logging.getLogger(__name__)

BUCKET = settings.supabase_bucket


def _storage():
    return get_supabase_admin().storage


def upload_pdf(
    user_id: str,
    document_id: str,
    filename: str,
    pdf_bytes: bytes,
) -> str:

    storage_path = f"{user_id}/{document_id}/{filename}"

    _storage().from_(BUCKET).upload(
        path=storage_path,
        file=pdf_bytes,
        file_options={"content-type": "application/pdf"},
    )

    logger.info("Uploaded PDF to %s", storage_path)
    return storage_path


def get_signed_url(storage_path: str, expires_in: int = 3600) -> str:

    response = _storage().from_(BUCKET).create_signed_url(
        path=storage_path,
        expires_in=expires_in,
    )
    return response["signedURL"]


def delete_pdf(storage_path: str) -> None:
    
    try:
        _storage().from_(BUCKET).remove([storage_path])
        logger.info("Deleted PDF at %s", storage_path)
    except Exception as exc:
        logger.error("Failed to delete PDF at %s: %s", storage_path, exc)