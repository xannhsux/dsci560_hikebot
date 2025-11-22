# backend/auth_router.py

import re
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Header

from models import (
    SignupRequest,
    LoginRequest,
    AuthResponse,
    AuthUser,
)
from pg_db import fetch_one, fetch_one_returning


router = APIRouter(prefix="/auth", tags=["auth"])


# -------------------------
# 密码 hash
# -------------------------
def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# -------------------------
# 用户手动设置的 user_code 校验
# -------------------------
USER_CODE_REGEX = re.compile(r"^[A-Za-z0-9]{4,16}$")  # 可自行放宽


def _validate_user_code(user_code: str) -> None:
    if not USER_CODE_REGEX.match(user_code):
        raise HTTPException(
            400,
            "user_code 必须是 4~16 位的字母和数字（不能有空格、符号）",
        )


# ==============================================================
#                       /auth/signup
# ==============================================================

@router.post("/signup", response_model=AuthResponse)
def signup(payload: SignupRequest) -> AuthResponse:
    username = payload.username.strip()
    user_code = payload.user_code.strip()
    password = payload.password

    if not username or not password or not user_code:
        raise HTTPException(400, "username、password、user_code 都是必填的")

    # 校验 user_code 格式
    _validate_user_code(user_code)

    # 检查 username 是否重复
    existing_user = fetch_one(
        "SELECT id FROM users WHERE username = %(u)s",
        {"u": username},
    )
    if existing_user:
        raise HTTPException(400, "Username 已经存在")

    # 检查 user_code 是否重复
    existing_code = fetch_one(
        "SELECT id FROM users WHERE user_code = %(c)s",
        {"c": user_code},
    )
    if existing_code:
        raise HTTPException(400, "这个 user_code 已被使用，请换一个")

    # 写入数据库
    row = fetch_one_returning(
        """
        INSERT INTO users (username, user_code, password_hash)
        VALUES (%(u)s, %(code)s, %(pwd)s)
        RETURNING id, username, user_code
        """,
        {
            "u": username,
            "code": user_code,
            "pwd": _hash_password(password),
        },
    )

    user = AuthUser(
        id=row["id"],
        username=row["username"],
        user_code=row["user_code"],
    )

    return AuthResponse(user=user, message="Signup successful")


# ==============================================================
#                       /auth/login
# ==============================================================

@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    username = payload.username.strip()
    password = payload.password

    # 查用户
    row = fetch_one(
        """
        SELECT id, username, user_code, password_hash
        FROM users
        WHERE username = %(u)s
        """,
        {"u": username},
    )
    if not row:
        raise HTTPException(400, "Invalid username or password")

    if row["password_hash"] != _hash_password(password):
        raise HTTPException(400, "Invalid username or password")

    user = AuthUser(
        id=row["id"],
        username=row["username"],
        user_code=row["user_code"],
    )

    return AuthResponse(user=user, message="Login successful")


# ==============================================================
#           current user dependency (用于 /social/* )
# ==============================================================

def get_current_user(
    x_username: str = Header(..., alias="X-Username"),
    x_user_code: str = Header(..., alias="X-User-Code"),
) -> AuthUser:
    row = fetch_one(
        """
        SELECT id, username, user_code
        FROM users
        WHERE username = %(u)s AND user_code = %(c)s
        """,
        {"u": x_username, "c": x_user_code},
    )

    if not row:
        raise HTTPException(401, "Invalid auth headers")

    return AuthUser(
        id=row["id"],
        username=row["username"],
        user_code=row["user_code"],
    )
