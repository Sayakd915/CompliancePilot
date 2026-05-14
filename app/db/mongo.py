from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import DESCENDING, IndexModel

from app.config import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None

def get_db() -> AsyncIOMotorDatabase:
    global _client, _db
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_url)
        _db = _client[settings.mongodb_db_name]
    return _db

async def ensure_indexes():
    db = get_db()
    await db.logs.create_indexes([
        IndexModel([("user_id", DESCENDING)]),
        IndexModel([("document_id", DESCENDING)]),
        IndexModel([("created_at", DESCENDING)]),
    ])

async def save_conversation(
    user_id: str,
    document_id: str,
    document_name: str,
    chunks: list[dict],
    report: dict | None = None,
) -> str:
    db = get_db()
    doc = {
        "user_id": user_id,
        "document_id": document_id,
        "document_name": document_name,
        "chunks": chunks,
        "report": report,
        "updated_at": datetime.utcnow(),
    }
    result = await db.conversations.insert_one(doc)
    return str(result.inserted_id)

async def update_conversation_report( document_id: str, report: dict) -> None:
    db = get_db()
    await db.conversations.update_one(
        {"document_id": document_id},
        {"$set": {"report": report}}
    )

async def get_conversation_from_user(user_id: str) -> list[dict]:
    db = get_db()
    cur = db.conversations.find(
        {"user_id": user_id},
        {"_id": 0},
    ).sort("created_at", DESCENDING)
    return await cur.to_list(length=100)

async def get_conversation_from_document(document_id: str, user_id: str) -> dict | None:
    db = get_db()
    return await db.conversations.find_one(
        {"document_id": document_id, "user_id": user_id},
        {"_id": 0},
    )