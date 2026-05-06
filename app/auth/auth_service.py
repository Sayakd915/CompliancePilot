from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.db.postgres import get_supabase_admin

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

##-----------------------Password helpers---------------------------

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

## --------------------JWT Helpers-------------------------------------

def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub" : user_id,
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

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
        .maybe_single()
        .execute()
    )
    return response.data

async def get_user_by_id(user_id:str) -> Optional[dict]:
    client = get_supabase_admin()
    response = (
        client.table("users")
        .select("*")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return response.data