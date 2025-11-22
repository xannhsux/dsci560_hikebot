# backend/auth_router.py
import re

import hashlib
import secrets
import string
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
from models import AuthUser  
from pg_db import fetch_one, fetch_all, execute, fetch_one_returning
from models import SignupRequest, LoginRequest, AuthResponse, AuthUser

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_password(password: str) -> str:
    
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

USER_CODE_REGEX = re.compile(r"^[A-Za-z0-9]{4,16}$")  # 举例：4~16位字母数字


def _validate_user_code(user_code: str) -> None:
    if not USER_CODE_REGEX.match(user_code):
        raise HTTPException(
            400,
            "user_code 需要是 4~16 位的字母和数字组合（不允许空格和符号）",
        )





@router.post("/signup", response_model=AuthResponse)
def signup(payload: SignupRequest) -> AuthResponse:
    username = payload.username.strip()
    user_code = payload.user_code.strip()

    if not username or not payload.password or not user_code:
        raise HTTPException(400, "username、password 和 user_code 都是必填的")

    # 校验 user_code 格式（字母数字 + 长度限制）
    _validate_user_code(user_code)

    # 检查 username 是否重复
    existing = fetch_one(
        "SELECT id FROM users WHERE username = %(u)s",
        {"u": username},
    )
    if existing:
        raise HTTPException(400, "Username already exists")

    # 检查 user_code 是否重复
    existing_code = fetch_one(
        "SELECT id FROM users WHERE user_code = %(c)s",
        {"c": user_code},
    )
    if existing_code:
        raise HTTPException(400, "这个 ID（user_code）已经被别人使用了，换一个吧")

    # 插入 DB
    row = fetch_one_returning(
        """
        INSERT INTO users (username, user_code, password_hash)
        VALUES (%(u)s, %(code)s, %(pwd)s)
        RETURNING id, username, user_code, created_at
        """,
        {
            "u": username,
            "code": user_code,
            "pwd": _hash_password(payload.password),
        },
    )

    user = AuthUser(id=row["id"], username=row["username"], user_code=row["user_code"])
    return AuthResponse(user=user, message="Signup successful")




@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    username = payload.username.strip()
    user = fetch_one(
        "SELECT id, username, user_code, password_hash FROM users WHERE username = %(u)s",
        {"u": username},
    )
    if not user or user["password_hash"] != _hash_password(payload.password):
        raise HTTPException(400, "Invalid username or password")

    auth_user = AuthUser(id=user["id"], username=user["username"], user_code=user["user_code"])
    return AuthResponse(user=auth_user, message="Login successful")


# -------- current user dependency (通过 header) --------

def get_current_user(
    x_username: str = Header(..., alias="X-Username"),
    x_user_code: str = Header(..., alias="X-User-Code"),
) -> AuthUser:
    user = fetch_one(
        "SELECT id, username, user_code FROM users WHERE username = %(u)s AND user_code = %(c)s",
        {"u": x_username, "c": x_user_code},
    )
    if not user:
        raise HTTPException(401, "Invalid auth headers")
    return AuthUser(id=user["id"], username=user["username"], user_code=user["user_code"])
