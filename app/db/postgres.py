from datetime import datetime
from supabase import Client, create_client
from app.config import settings

_anon_client: Client | None = None
_admin_client: Client | None = None

def get_supabase_anon() -> Client:
    global _anon_client
    if _anon_client is None:
        _anon_client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return _anon_client

def get_supabase_admin() -> Client:
    global _admin_client
    if _admin_client is None:
        _admin_client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _admin_client

## --------------------------Document Ops----------------------------------------------------

async def create_document_record(
    document_id: str,
    user_id: str,
    filename: str,
    storage: str,
    file_size_bytes: int
) -> dict :
    client = get_supabase_admin()
    response = (
        client.table("documents")
        .insert({
            "id":document_id,
            "user_id":user_id,
            "filename":filename,
            "storage_path":storage,
            "file_size_bytes":file_size_bytes
        }).execute()
    )
    if not response.data:
        raise Exception("Document insert returned no data")
    return response.data[0]

async def update_document_analysis(
    document_id: str,
    overall_risk: str,
) -> None:
    client = get_supabase_admin()
    client.table("documents").update({
        "analyzed_at": datetime.utcnow().isoformat(),
        "overall_risk": overall_risk
    }).eq("id", document_id).execute()

async def get_user_document(user_id: str) -> list[dict]:
    client = get_supabase_admin()
    response = (
        client.table("documents")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", ascending=False)
        .execute()
    )
    return response.data or []

async def get_document_by_id(document_id: str, user_id: str) -> dict | None:
    client = get_supabase_admin()
    response = (
        client.table("documents")
        .select("*")
        .eq("id", document_id)
        .eq("user_id",user_id)
        .execute()
    )
    if response.data:
        return response.data[0]
    return None