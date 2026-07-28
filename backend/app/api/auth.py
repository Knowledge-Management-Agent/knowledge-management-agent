from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.security import authenticate, create_access_token
from app.config import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, settings: Settings = Depends(get_settings)):
    role = authenticate(body.username, body.password, settings)
    if role is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(body.username, role, settings)
    return LoginResponse(access_token=token, role=role)
