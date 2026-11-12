"""启动游戏：服务跑在玩家本机，可以直接拉起游戏进程。

安全说明：
- 只启动 .env 配置或自动探测到的固定路径，绝不接受前端传入的任意路径；
- 写接口受 API_KEY 保护（配置后），公网部署务必设置 API_KEY；
- 仅支持 Windows 本机部署。
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..database import get_db
from ..games import GameSpec, merged_games
from .deps import require_api_key, require_owner

router = APIRouter(prefix="/api", tags=["launch"])

# DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP：完全脱离服务进程
DETACH_FLAGS = 0x00000008 | 0x00000200

TASK_NAME = "StarWavesLaunchGame"
TARGET_FILE = DATA_DIR / "launch_target.txt"


def _resolve_path(game: str, spec: GameSpec | None = None) -> Path | None:
    if spec is None:
        from ..games import get_spec

        spec = get_spec(game)
    configured = os.getenv(spec.launch_env_key, "").strip() if spec.launch_env_key else ""
    if configured and Path(configured).is_file():
        return Path(configured)
    from glob import glob

    for candidate in spec.launch_candidates:
        if any(ch in candidate for ch in "*?["):
            for match in sorted(glob(candidate)):
                if Path(match).is_file():
                    return Path(match)
        elif Path(candidate).is_file():
            return Path(candidate)
    return None


def _elevated_task_available() -> bool:
    """最高权限计划任务是否已配置（一次性配置见 tools/setup_launch_task.ps1）。"""
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["schtasks", "/query", "/tn", TASK_NAME],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _launch_elevated(path: Path, extra_args: str = "") -> None:
    """把目标路径（可选第二行：启动参数）写入文件，触发最高权限计划任务执行。"""
    TARGET_FILE.write_text(f"{path}\n{extra_args}", encoding="utf-8")
    result = subprocess.run(
        ["schtasks", "/run", "/tn", TASK_NAME],
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "ignore").strip() or "计划任务触发失败"
        raise OSError(message)


def _ensure_pre_launch(spec: GameSpec) -> None:
    """部分游戏（如鸣潮）需要启动器进程驻留，客户端通过管道向它索取加密密钥。
    启动器不存在时先拉起（普通权限即可），稍等其初始化后再启动游戏。"""
    pre = getattr(spec, "launch_pre", None) or None
    if not pre:
        return
    exe, proc_name = pre
    if not Path(exe).is_file():
        return
    check = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {proc_name}"],
        capture_output=True,
        timeout=10,
    )
    if proc_name.lower() in check.stdout.decode("utf-8", "ignore").lower():
        return
    subprocess.Popen(
        [exe],
        cwd=str(Path(exe).parent),
        creationflags=DETACH_FLAGS,
        close_fds=True,
    )
    time.sleep(8)


@router.post("/launch/{game}", dependencies=[Depends(require_api_key), Depends(require_owner)])
def launch_game(game: str, db: Session = Depends(get_db)) -> dict:
    registry = merged_games(db)
    spec = registry.get(game)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"未知游戏: {game}，支持: {', '.join(registry)}")
    if os.name != "nt":
        raise HTTPException(status_code=501, detail="启动游戏仅支持 Windows 本机部署")
    path = _resolve_path(game, spec)
    if path is None:
        env_key = spec.launch_env_key
        if not env_key:
            raise HTTPException(status_code=400, detail=f"{spec.label}未配置启动路径（自定义游戏可在 .env 之外通过注册表扩展）")
        raise HTTPException(
            status_code=400,
            detail=f"未找到{spec.label}安装路径，请在 .env 中设置 {env_key}",
        )
    _ensure_pre_launch(spec)
    extra_args = getattr(spec, "launch_args", "") or ""
    if _elevated_task_available():
        try:
            _launch_elevated(path, extra_args)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"提权启动失败: {exc}") from exc
        return {"launched": True, "game": game, "path": str(path), "elevated": True}
    try:
        subprocess.Popen(
            [str(path)],
            cwd=str(path.parent),
            creationflags=DETACH_FLAGS,
            close_fds=True,
        )
    except OSError as exc:
        if getattr(exc, "winerror", None) == 740:
            raise HTTPException(
                status_code=500,
                detail=(
                    "游戏需要管理员权限：请在电脑上双击 setup-launch-task.bat "
                    "完成一次性配置（UAC 点“是”），之后手机即可一键启动"
                ),
            ) from exc
        raise HTTPException(status_code=500, detail=f"启动失败: {exc}") from exc
    return {"launched": True, "game": game, "path": str(path)}
