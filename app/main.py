"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401  确保模型注册到 Base.metadata
from .config import DATA_DIR, STATIC_DIR, UPLOAD_DIR
from .database import Base, engine
from .routers import launch, news, profiles, public, settings, sync, uploads


@asynccontextmanager
async def lifespan(_: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="StarWaves", description="多游戏个人档案 + 官方资讯聚合", version="0.2.0", lifespan=lifespan)

app.include_router(public.router)
app.include_router(profiles.router)
app.include_router(uploads.router)
app.include_router(sync.router)
app.include_router(settings.router)
app.include_router(launch.router)
app.include_router(news.router)


@app.get("/", include_in_schema=False)
def landing_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "home.html")


@app.get("/dashboard", include_in_schema=False)
def dashboard_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/news", include_in_schema=False)
def news_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "news.html")


@app.get("/share/{share_id}", include_in_schema=False)
def share_page(share_id: str) -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
