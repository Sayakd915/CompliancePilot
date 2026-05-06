import hashlib
import json
import logging
from upstash_redis import Redis
from app.config import settings

logger = logging.getLogger(__name__)

_redis: Redis | None = None

def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis(
            url = settings.upstash_redis_rest_url,
            token = settings.upstash_redis_rest_token 
        )
    return _redis

def make_cache_key(chunk_text: str) -> str:
    digest = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
    return f"chunk:{digest}"

async def get_cached_result(chunk_text: str) -> dict | None:
    try:
        redis = get_redis()
        key = make_cache_key(chunk_text)
        raw = redis.get(key)
        if raw is not None:
            logger.debug("Cache HIT for key %s", key[:20])
            return json.loads(raw)
        logger.debug("Cache MISS for key %s", key[:20])
        return None
    except Exception as exc:
        logger.warning("Cache read failed (non-fatal): %s", exc)
        return None

async def set_cached_result(chunk_text: str, result: dict) -> None:
    try:
        redis = get_redis()
        key = make_cache_key(chunk_text)
        redis.set(key, json.dumps(result), ex=settings.cache_ttl_seconds)
        logger.debug("Cache SET for key %s", key[:20])
    except Exception as exc:
        logger.warning("Redis set failed (non-fatal): %s", exc)

async def invalidate_chunk(chunk_text: str) -> None:
    try:
        redis = get_redis()
        redis.delete(make_cache_key(chunk_text))
    except Exception as exc:
        logger.warning("Redis delete failed (non-fatal): %s", exc)