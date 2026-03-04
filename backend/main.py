import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse, RedirectResponse

from auth import get_user_by_session
from config import settings
from database import init_db
from routes.auth_routes import SESSION_COOKIE, router as auth_router
from routes.notes_routes import router as notes_router
from routes.folders_routes import router as folders_router
from routes.search_routes import router as search_router
from routes.graph_routes import router as graph_router
from routes.media_routes import router as media_router
from routes.share_routes import router as share_router
from routes.theme_routes import router as theme_router
from routes.locale_routes import router as locale_router

app = FastAPI(title="Izoldian", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth paths that don't require session
AUTH_EXEMPT = {
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/oidc/enabled",
    "/api/auth/oidc/login",
    "/api/auth/oidc/callback",
}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # Skip auth for non-API paths, auth endpoints, and public APIs (themes, locales)
    if not path.startswith("/api/") or path in AUTH_EXEMPT or path.startswith("/api/themes") or path.startswith("/api/locales"):
        return await call_next(request)

    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        from starlette.responses import JSONResponse
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    user = await get_user_by_session(token)
    if not user:
        from starlette.responses import JSONResponse
        return JSONResponse({"detail": "Session expired"}, status_code=401)

    request.state.user = user
    return await call_next(request)


# Register API routers
app.include_router(auth_router)
app.include_router(notes_router)
app.include_router(folders_router)
app.include_router(search_router)
app.include_router(graph_router)
app.include_router(media_router)
app.include_router(share_router)
app.include_router(theme_router)
app.include_router(locale_router)

# Frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/")
async def root():
    return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.get("/app")
async def app_page():
    return FileResponse(os.path.join(frontend_dir, "app.html"))



# Serve static assets
app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")


@app.on_event("startup")
async def startup():
    os.makedirs(settings.data_dir, exist_ok=True)
    await init_db()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
