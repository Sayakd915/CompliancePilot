from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependency import get_current_user
from app.db.postgres import get_supabase_admin

router = APIRouter(prefix="/profile", tags=["profile"])

class UpdateProfileRequest(BaseModel):
    full_name: str

@router.get("")
async def get_profile(user: dict = Depends(get_current_user)):
    return {
        "user_id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "created_at": user["created_at"]
    }

@router.put("")
async def update_profile(body: UpdateProfileRequest, user: dict = Depends(get_current_user)):

    if not body.full_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full name cannot be empty"
        )

    client = get_supabase_admin()
    response = (
        client.table("users")
        .update({"full_name": body.full_name.strip()})
        .eq("id", user["id"])
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )
    
    return {"message": "Profile updated", "full_name": body.full_name.strip()}