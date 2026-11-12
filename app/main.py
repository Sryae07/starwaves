"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401  确保模型注册到 Base.metadata
from .config import DATA_DIR, STATIC_DIR, UPLOAD_DIR
from .database import Base, engine
from .routers import profiles, public, sync, uploads


@asynccontextmanager
async def lifespan(_: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="StarWaves", description="星穹铁道 × 鸣潮 双游档案", version="0.1.0", lifespan=lifespan)

app.include_router(public.router)
app.include_router(profiles.router)
app.include_router(uploads.router)
app.include_router(sync.router)

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
