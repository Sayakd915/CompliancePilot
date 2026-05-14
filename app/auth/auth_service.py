from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.config import settings
from app.db.postgres import get_supabase_admin

##-----------------------Password helpers---------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

## --------------------JWT Helpers-------------------------------------

def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub" : user_id,
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

## ----------------------------User Ops--------------------------------------------

async def create_user(email: str, password: str, full_name: str) -> dict:
    client = get_supabase_admin()
    hashed = hash_password(password)

    response = (
        client.table("users")
        .insert({
            "email": email,
            "password_hash": hashed,
            "full_name": full_name
        })
        .execute()
    )

    if not response.data:
        raise ValueError("Failed to create user - no row returned")
    
    return response.data[0]

async def get_user_by_email(email:str) -> Optional[dict]:
    client = get_supabase_admin()
    response = (
        client.table("users")
        .select("*")
        .eq("email", email)
        .execute()
    )
    if response.data:
        return response.data[0]
    return None

async def get_user_by_id(user_id:str) -> Optional[dict]:
    client = get_supabase_admin()
    response = (
        client.table("users")
        .select("*")
        .eq("id", user_id)
        .execute()
    )
    if response.data:
        return response.data[0]
    return None