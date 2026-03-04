import uuid
import secrets
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import httpx
import jwt

from config import settings
from database import get_db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def generate_session_token() -> str:
    return secrets.token_urlsafe(48)


def get_user_data_dir(user_id: str) -> str:
    return os.path.join(settings.data_dir, user_id)


async def create_user(username: str, password: str | None = None, oidc_sub: str | None = None) -> dict:
    user_id = str(uuid.uuid4())
    password_hash = hash_password(password) if password else None

    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO users (id, username, password_hash, oidc_sub) VALUES (?, ?, ?, ?)",
            (user_id, username, password_hash, oidc_sub),
        )
        await db.commit()
    finally:
        await db.close()

    # Create user data directory
    user_dir = get_user_data_dir(user_id)
    os.makedirs(user_dir, exist_ok=True)

    return {"id": user_id, "username": username}


async def authenticate_user(username: str, password: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,))
        row = await cursor.fetchone()
        if not row or not row["password_hash"]:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return {"id": row["id"], "username": row["username"]}
    finally:
        await db.close()


async def create_session(user_id: str) -> str:
    token = generate_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.session_max_age_days)

    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at.isoformat()),
        )
        await db.commit()
    finally:
        await db.close()

    return token


async def get_user_by_session(token: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT u.id, u.username FROM users u
               JOIN sessions s ON s.user_id = u.id
               WHERE s.token = ? AND s.expires_at > ?""",
            (token, datetime.now(timezone.utc).isoformat()),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {"id": row["id"], "username": row["username"]}
    finally:
        await db.close()


async def delete_session(token: str):
    db = await get_db()
    try:
        await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
        await db.commit()
    finally:
        await db.close()


# --- OIDC ---

_oidc_config_cache = None


async def get_oidc_config() -> dict:
    global _oidc_config_cache
    if _oidc_config_cache:
        return _oidc_config_cache

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{settings.oidc_issuer}/.well-known/openid-configuration")
        resp.raise_for_status()
        _oidc_config_cache = resp.json()
        return _oidc_config_cache


def get_oidc_auth_url(state: str) -> str:
    """Build OIDC authorization URL (synchronous, uses cached config or builds manually)."""
    base = f"{settings.oidc_issuer}/api/oidc/authorization"
    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scope": settings.oidc_scopes,
        "state": state,
    }
    from urllib.parse import urlencode
    return f"{base}?{urlencode(params)}"


async def exchange_oidc_code(code: str) -> dict:
    """Exchange authorization code for tokens and return user info."""
    oidc_config = await get_oidc_config()
    token_endpoint = oidc_config["token_endpoint"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.oidc_redirect_uri,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
            },
        )
        resp.raise_for_status()
        tokens = resp.json()

    # Decode ID token
    id_token = tokens["id_token"]
    claims = jwt.decode(id_token, options={"verify_signature": False})

    username = claims.get("preferred_username") or claims.get("name")

    # If username not in id_token, fetch from userinfo endpoint
    if not username:
        userinfo_endpoint = oidc_config.get("userinfo_endpoint")
        if userinfo_endpoint:
            async with httpx.AsyncClient() as client2:
                ui_resp = await client2.get(
                    userinfo_endpoint,
                    headers={"Authorization": f"Bearer {tokens['access_token']}"},
                )
                if ui_resp.status_code == 200:
                    userinfo = ui_resp.json()
                    username = userinfo.get("preferred_username") or userinfo.get("name")

    return {
        "sub": claims["sub"],
        "username": username or claims["sub"],
    }


async def get_or_create_oidc_user(oidc_sub: str, username: str) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id, username FROM users WHERE oidc_sub = ?", (oidc_sub,))
        row = await cursor.fetchone()
        if row:
            # Update username if changed
            if row["username"] != username:
                await db.execute("UPDATE users SET username = ? WHERE id = ?", (username, row["id"]))
                await db.commit()
            return {"id": row["id"], "username": username}
    finally:
        await db.close()

    # Create new user
    return await create_user(username=username, oidc_sub=oidc_sub)
