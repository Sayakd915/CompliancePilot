from fastapi import APIRouter, HTTPException, status

from app.models import SignupRequest, SigninRequest, TokenResponse
from app.auth.auth_service import (
    create_user,
    get_user_by_email,
    verify_password,
    create_access_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def sign_up(body: SignupRequest):
    existing = await get_user_by_email(body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists"
        )
    
    user = await create_user(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
    )

    token = create_access_token(
        user_id=user["id"], email=user["email"]
    )
    return TokenResponse(
        access_token=token,
        user_id=user["id"],
        email=user["email"]
    )


@router.post("/signin", response_model=TokenResponse)
async def sign_in(body:SigninRequest):
    user = await get_user_by_email(body.email)

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or passsword",
        )
    
    token =create_access_token(user_id=user["id"], email=user["email"])
    return TokenResponse(
        access_token=token,
        user_id=user["id"],
        email=user["email"]
    )