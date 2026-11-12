"""启动游戏：服务跑在玩家本机，可以直接拉起游戏进程。

安全说明：
- 只启动 .env 配置或自动探测到的固定路径，绝不接受前端传入的任意路径；
- 写接口受 API_KEY 保护（配置后），公网部署务必设置 API_KEY；
- 仅支持 Windows 本机部署。
"""

from __future__ import annotations

import glob
import os
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..config import GAME_RULES, LAUNCH_HSR_PATH, LAUNCH_WUWA_PATH
from .deps import require_api_key

router = APIRouter(prefix="/api", tags=["launch"])

# DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP：完全脱离服务进程
DETACH_FLAGS = 0x00000008 | 0x00000200


def _resolve_path(game: str) -> Path | None:
    configured = LAUNCH_HSR_PATH if game == "hsr" else LAUNCH_WUWA_PATH
    if configured and Path(configured).is_file():
        return Path(configured)
    candidates: list[str] = []
    if game == "hsr":
        candidates += [
            r"C:\Program Files\Star Rail\Games\StarRail.exe",
            r"C:\Program Files (x86)\Star Rail\Games\StarRail.exe",
        ]
        # 未找到星铁本体时，退回到米哈游启动器（用户再点一下进入游戏）
        candidates += sorted(glob.glob(r"C:\Program Files\miHoYo Launcher\*\HYP.exe"))
    else:
        candidates += [
            r"C:\Program Files\Wuthering Waves\Wuthering Waves Game\Client\Binaries\Win64\Client-Win64-Shipping.exe",
        ]
        candidates += sorted(
            glob.glob(r"C:\Program Files\Wuthering Waves\*\Client\Binaries\Win64\Client-Win64-Shipping.exe")
        )
    for candidate in candidates:
        if Path(candidate).is_file():
            return Path(candidate)
    return None


@router.post("/launch/{game}", dependencies=[Depends(require_api_key)])
def launch_game(game: str) -> dict:
    if game not in GAME_RULES:
        raise HTTPException(status_code=404, detail=f"未知游戏: {game}")
    if os.name != "nt":
        raise HTTPException(status_code=501, detail="启动游戏仅支持 Windows 本机部署")
    path = _resolve_path(game)
    if path is None:
        env_key = "LAUNCH_HSR_PATH" if game == "hsr" else "LAUNCH_WUWA_PATH"
        raise HTTPException(
            status_code=400,
            detail=f"未找到{GAME_RULES[game]['label']}安装路径，请在 .env 中设置 {env_key}",
        )
    try:
        subprocess.Popen(
            [str(path)],
            cwd=str(path.parent),
            creationflags=DETACH_FLAGS,
            close_fds=True,
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"启动失败: {exc}")
    return {"launched": True, "game": game, "path": str(path)}
