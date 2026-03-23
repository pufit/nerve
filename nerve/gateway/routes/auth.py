"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi import HTTPException
from pydantic import BaseModel

from nerve.config import get_config
from nerve.gateway.auth import create_token, require_auth, verify_password

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str


@router.post("/api/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    config = get_config()
    if not config.auth.password_hash or not config.auth.jwt_secret:
        # Dev mode — accept any password
        return LoginResponse(token=create_token(config.auth.jwt_secret or "dev-secret"))

    if not verify_password(req.password, config.auth.password_hash):
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_token(config.auth.jwt_secret)
    return LoginResponse(token=token)


@router.get("/api/auth/check")
async def check_auth(user: dict = Depends(require_auth)):
    return {"authenticated": True}
