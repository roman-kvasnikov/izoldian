import secrets

from fastapi import APIRouter, HTTPException, Request, Response

from auth import (
    authenticate_user,
    create_session,
    create_user,
    delete_session,
    exchange_oidc_code,
    get_oidc_auth_url,
    get_or_create_oidc_user,
    get_user_by_session,
)
from config import settings
from models import LoginRequest, RegisterRequest, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = "session_token"
SESSION_MAX_AGE = settings.session_max_age_days * 86400

# Store OIDC states in memory (simple approach)
_oidc_states: set[str] = set()


def set_session_cookie(response: Response, token: str):
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,  # Set True behind HTTPS proxy
    )


@router.post("/register", response_model=UserResponse)
async def register(req: RegisterRequest, response: Response):
    try:
        user = await create_user(req.username, req.password)
    except Exception:
        raise HTTPException(400, "Username already taken")

    token = await create_session(user["id"])
    set_session_cookie(response, token)
    return user


@router.post("/login", response_model=UserResponse)
async def login(req: LoginRequest, response: Response):
    user = await authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(401, "Invalid username or password")

    token = await create_session(user["id"])
    set_session_cookie(response, token)
    return user


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await delete_session(token)
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def me(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Not authenticated")
    user = await get_user_by_session(token)
    if not user:
        raise HTTPException(401, "Session expired")
    return user


@router.get("/oidc/enabled")
async def oidc_enabled():
    return {"enabled": settings.oidc_enabled}


@router.get("/oidc/login")
async def oidc_login():
    if not settings.oidc_enabled:
        raise HTTPException(400, "OIDC not configured")

    state = secrets.token_urlsafe(32)
    _oidc_states.add(state)
    url = get_oidc_auth_url(state)
    return {"url": url}


@router.get("/oidc/callback")
async def oidc_callback(code: str, state: str, response: Response):
    if state not in _oidc_states:
        raise HTTPException(400, "Invalid state")
    _oidc_states.discard(state)

    try:
        oidc_user = await exchange_oidc_code(code)
    except Exception as e:
        raise HTTPException(400, f"OIDC error: {e}")

    user = await get_or_create_oidc_user(oidc_user["sub"], oidc_user["username"])
    token = await create_session(user["id"])
    set_session_cookie(response, token)

    # Redirect to app
    from starlette.responses import RedirectResponse
    resp = RedirectResponse(url="/app", status_code=302)
    set_session_cookie(resp, token)
    return resp
