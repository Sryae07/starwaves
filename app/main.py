"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager
import logging
import secrets

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from . import models  # noqa: F401  确保模型注册到 Base.metadata
from .config import DATA_DIR, DATABASE_URL, OWNER_USERNAME, STATIC_DIR, UPLOAD_DIR
from .database import Base, SessionLocal, engine
from .models import Player, User
from .security import hash_password
from .routers import auth, games, launch, news, profiles, public, settings, sync, uploads

logger = logging.getLogger("starwaves.bootstrap")


def ensure_schema() -> None:
    """create_all 只建新表；SQLite 下对已有旧表补列（轻量迁移）。
    Postgres 云端部署跳过 PRAGMA 逻辑。"""
    Base.metadata.create_all(engine)
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.connect() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(players)")}
        if "user_id" not in cols:
            conn.exec_driver_sql("ALTER TABLE players ADD COLUMN user_id INTEGER REFERENCES users(id)")
            conn.commit()
        pcols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(profiles)")}
        if "challenges" not in pcols:
            conn.exec_driver_sql("ALTER TABLE profiles ADD COLUMN challenges TEXT DEFAULT '{}'")
            conn.commit()
        ucols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)")}
        if "is_owner" not in ucols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN is_owner INTEGER DEFAULT 0")
            conn.commit()
        gcols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(custom_games)")}
        if "steam_appid" not in gcols:
            conn.exec_driver_sql("ALTER TABLE custom_games ADD COLUMN steam_appid TEXT DEFAULT ''")
            conn.commit()


def migrate_legacy_player() -> None:
    """老版本没有账号体系：若存在无主玩家且还没有任何账号，自动建一个初始账号接管，
    随机初始密码写入 data/initial_password.txt 并打印到控制台。"""
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return
        orphans = db.query(Player).filter(Player.user_id.is_(None)).order_by(Player.id.asc()).all()
        if not orphans:
            return
        password = secrets.token_urlsafe(9)
        user = User(username=orphans[0].nickname or "用户", password_hash=hash_password(password))
        db.add(user)
        db.flush()
        for player in orphans:
            player.user_id = user.id
        db.commit()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "initial_password.txt").write_text(
            f"Sryaestart 初始账号（由旧数据自动迁移）\n用户名: {user.username}\n密码: {password}\n"
            "首次登录后请尽快通过注册新账号或直接使用本账号管理数据。\n",
            encoding="utf-8",
        )
        logger.info("旧数据迁移完成：初始账号 %s 密码已写入 data/initial_password.txt", user.username)
    finally:
        db.close()


def ensure_owner() -> None:
    """机主账号：服务运行在机主电脑上，启动游戏 / 改背景 / 换 Cookie 等
    本机控制类操作只允许机主执行。.env 的 OWNER_USERNAME 一旦设置即为
    唯一机主（每次启动都会校验并纠正）；未设置时默认最早注册的账号为机主。"""
    db = SessionLocal()
    try:
        target = None
        if OWNER_USERNAME:
            target = db.query(User).filter(User.username == OWNER_USERNAME).first()
            if target is None:
                logger.warning("OWNER_USERNAME=%s 未匹配到账号，回退为最早注册账号", OWNER_USERNAME)
        if target is None:
            owner = db.query(User).filter(User.is_owner.is_(True)).first()
            if owner is not None:
                return
            target = db.query(User).order_by(User.id.asc()).first()
        if target is None:
            return
        target.is_owner = True
        for row in db.query(User).filter(User.is_owner.is_(True), User.id != target.id).all():
            row.is_owner = False
        db.commit()
        logger.info("机主账号：%s", target.username)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ensure_schema()
    migrate_legacy_player()
    ensure_owner()
    yield


app = FastAPI(title="Sryaestart", description="游戏启动器 + 多游戏档案 + 官方资讯聚合", version="0.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sryae07.github.io",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(profiles.router)
app.include_router(uploads.router)
app.include_router(sync.router)
app.include_router(settings.router)
app.include_router(launch.router)
app.include_router(news.router)
app.include_router(games.router)


@app.get("/", include_in_schema=False)
def landing_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "home.html", headers={"Cache-Control": "no-store, must-revalidate"})


@app.get("/dashboard", include_in_schema=False)
def dashboard_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store, must-revalidate"})


@app.get("/news", include_in_schema=False)
def news_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "news.html", headers={"Cache-Control": "no-store, must-revalidate"})


@app.get("/share/{share_id}", include_in_schema=False)
def share_page(share_id: str) -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store, must-revalidate"})


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, must-revalidate"
        return response


app.mount("/", NoCacheStaticFiles(directory=STATIC_DIR, html=True), name="static")
