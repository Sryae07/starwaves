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

# 启动后等游戏进程出现的上限（秒）；确认到了就立刻返回，不必干等到超时
PROC_WAIT = 4.0
# 预启动器（如鸣潮 launcher）起来的等待上限（秒）
PRE_WAIT = 8.0
# 提权兜底杀进程后，等它真正消失的上限（秒）
KILL_WAIT = 12.0


def _proc_running(proc_name: str) -> bool:
    """用 tasklist 判断进程是否在跑（比 psutil 少一个依赖）。"""
    if not proc_name or os.name != "nt":
        return False
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {proc_name}", "/NH"],
            capture_output=True,
            timeout=8,
        ).stdout.decode("utf-8", "ignore")
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc_name.lower() in out.lower()


def _wait_proc(proc_name: str, timeout: float = PROC_WAIT) -> bool | None:
    """等到进程出现（或超时）。没配进程名时返回 None = 无法确认。"""
    if not proc_name:
        return None
    deadline = time.time() + timeout
    while True:
        if _proc_running(proc_name):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.4)


def _wait_proc_gone(proc_name: str, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while True:
        if not _proc_running(proc_name):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.3)


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
    if spec.platform and spec.launch_protocol.startswith("steam://"):
        return _steam_path_from_registry()
    return None


def _steam_path_from_registry() -> Path | None:
    """Steam 可能装在非默认目录，优先读注册表里记录的 SteamExe 路径。"""
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _ = winreg.QueryValueEx(key, "SteamExe")
        path = Path(str(value))
        return path if path.is_file() else None
    except (OSError, ImportError):
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


def _launch_direct(path: Path, extra_args: str = "") -> None:
    """普通权限直接拉起进程（带参数）。需要管理员权限的程序会抛 winerror 740，
    由调用方转最高权限计划任务兜底。"""
    args = [str(path)]
    if extra_args:
        args.extend(extra_args.split())
    subprocess.Popen(
        args,
        cwd=str(path.parent),
        creationflags=DETACH_FLAGS,
        close_fds=True,
    )


def _wait_target_consumed(timeout: float = 6.0) -> bool:
    """等到计划任务真的取走指令文件（文件被消费即代表命令已执行）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not TARGET_FILE.exists():
            return True
        time.sleep(0.25)
    return False


def _launch_elevated(path: Path, extra_args: str = "") -> None:
    """把目标路径（可选第二行：启动参数）写入文件，触发最高权限计划任务执行。
    等待任务取走指令文件，没取走就再触发一次，避免任务被占用时静默丢单。"""
    TARGET_FILE.write_text(f"{path}\n{extra_args}", encoding="utf-8")
    for _ in range(2):
        result = subprocess.run(
            ["schtasks", "/run", "/tn", TASK_NAME],
            capture_output=True,
            timeout=15,
        )
        if result.returncode != 0:
            message = result.stderr.decode("utf-8", "ignore").strip() or "计划任务触发失败"
            raise OSError(message)
        if _wait_target_consumed():
            return
    raise OSError("计划任务未能取走启动指令（任务可能被占用），请稍后重试")


def _kill_elevated(proc_name: str, timeout: float = KILL_WAIT) -> bool:
    """借最高权限计划任务结束进程：游戏是提权启动的，普通权限 taskkill 会被拒（Access is denied）。"""
    if not proc_name or os.name != "nt":
        return False
    try:
        TARGET_FILE.write_text(f"KILL:{proc_name}", encoding="utf-8")
        consumed = False
        for _ in range(2):
            result = subprocess.run(
                ["schtasks", "/run", "/tn", TASK_NAME],
                capture_output=True,
                timeout=15,
            )
            if result.returncode == 0 and _wait_target_consumed():
                consumed = True
                break
        if not consumed:
            return False
    except (OSError, subprocess.TimeoutExpired):
        return False
    return _wait_proc_gone(proc_name, timeout)


def _launch_protocol(url: str, game: str) -> dict:
    """协议启动（如 steam://rungameid/xxx）：无需管理员权限、不依赖安装路径。"""
    try:
        os.startfile(url)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"协议启动失败（Steam 等客户端可能未安装）: {exc}") from exc
    return {"launched": True, "game": game, "protocol": url, "elevated": False}


def _ensure_pre_launch(spec: GameSpec) -> None:
    """部分游戏（如鸣潮）需要启动器进程驻留，客户端通过管道向它索取加密密钥。
    启动器不存在时先拉起（普通权限即可），稍等其初始化后再启动游戏。"""
    pre = getattr(spec, "launch_pre", None) or None
    if not pre:
        return
    exe, proc_name = pre
    if not Path(exe).is_file():
        return
    if _proc_running(proc_name):
        return
    subprocess.Popen(
        [exe],
        cwd=str(Path(exe).parent),
        creationflags=DETACH_FLAGS,
        close_fds=True,
    )
    # 原来固定 sleep(8)：每次启动都白等 8 秒。改成轮询，launcher 一出现就走。
    deadline = time.time() + PRE_WAIT
    while not _proc_running(proc_name) and time.time() < deadline:
        time.sleep(0.5)


@router.post("/launch/{game}", dependencies=[Depends(require_api_key), Depends(require_owner)])
def launch_game(game: str, db: Session = Depends(get_db)) -> dict:
    registry = merged_games(db)
    spec = registry.get(game)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"未知游戏: {game}，支持: {', '.join(registry)}")
    if os.name != "nt":
        raise HTTPException(status_code=501, detail="启动游戏仅支持 Windows 本机部署")
    path = _resolve_path(game, spec)
    protocol = spec.launch_protocol or (f"steam://rungameid/{spec.steam_appid}" if spec.steam_appid else "")
    proc_name = spec.proc_name or ""
    # 已经在跑就别再拉一遍（既省时间，也避免双开/重复请求串行卡住）
    if proc_name and _proc_running(proc_name):
        return {
            "launched": True,
            "already": True,
            "started": True,
            "game": game,
            "proc": proc_name,
            "message": f"{spec.label}已经在运行了",
        }
    if path is None and protocol:
        return _launch_protocol(protocol, game)
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
    elevated = False
    try:
        _launch_direct(path, extra_args)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 740:
            if not _elevated_task_available():
                raise HTTPException(
                    status_code=500,
                    detail=(
                        "游戏需要管理员权限：请在电脑上双击 setup-launch-task.bat "
                        "完成一次性配置（UAC 点“是”），之后手机即可一键启动"
                    ),
                ) from exc
            try:
                _launch_elevated(path, extra_args)
            except OSError as exc2:
                raise HTTPException(status_code=500, detail=f"提权启动失败: {exc2}") from exc2
            elevated = True
        else:
            raise HTTPException(status_code=500, detail=f"启动失败: {exc}") from exc

    # 指令发出就立刻回答：提权任务转到游戏进程真正出现要 5-15 秒（Unity/UE 客户端更久），
    # 在这里干等只会让手机端把「还没检测到」误读成失败。起来没有由前端轮询 /api/running 确认。
    started: bool | None = None
    if not proc_name:
        message = f"启动指令已发出：{spec.label}"
    elif _proc_running(proc_name):
        started = True
        message = f"{spec.label}已启动"
    else:
        message = f"启动指令已发出，正在等待 {proc_name} 启动…"
    return {
        "launched": True,
        "game": game,
        "path": str(path),
        "elevated": elevated,
        "started": started,
        "proc": proc_name,
        "message": message,
    }


@router.get("/running", dependencies=[Depends(require_api_key), Depends(require_owner)])
def running_games(db: Session = Depends(get_db)) -> dict:
    """哪些游戏正在运行（前端用来决定显示「启动」还是「关闭」）。"""
    if os.name != "nt":
        return {"games": {}}
    out: dict[str, bool] = {}
    for key, spec in merged_games(db).items():
        if spec.proc_name:
            out[key] = _proc_running(spec.proc_name)
    return {"games": out}


@router.post("/stop/{game}", dependencies=[Depends(require_api_key), Depends(require_owner)])
def stop_game(game: str, db: Session = Depends(get_db)) -> dict:
    """关闭游戏：只结束该游戏自己的进程（不动机主其它程序，也不关机）。"""
    registry = merged_games(db)
    spec = registry.get(game)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"未知游戏: {game}，支持: {', '.join(registry)}")
    if os.name != "nt":
        raise HTTPException(status_code=501, detail="关闭游戏仅支持 Windows 本机部署")
    proc_name = spec.proc_name or ""
    if not proc_name:
        raise HTTPException(status_code=400, detail=f"{spec.label}没有配置进程名，无法关闭")
    if not _proc_running(proc_name):
        return {
            "stopped": False,
            "running": False,
            "game": game,
            "proc": proc_name,
            "message": f"{spec.label}没有在运行",
        }
    try:
        result = subprocess.run(
            ["taskkill", "/IM", proc_name, "/T", "/F"],
            capture_output=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="结束进程超时") from exc
    if result.returncode != 0:
        raw = result.stderr.decode("utf-8", "ignore") or result.stdout.decode("utf-8", "ignore")
        message = raw.strip() or f"结束进程失败（taskkill 返回 {result.returncode}）"
        # 进程刚好自己退了也算关闭成功
        if _wait_proc_gone(proc_name, 2.0):
            return {
                "stopped": True,
                "running": False,
                "game": game,
                "proc": proc_name,
                "message": f"{spec.label}已关闭",
            }
        # 提权启动的游戏，普通权限 taskkill 会被拒；借最高权限计划任务再杀一次
        if _kill_elevated(proc_name):
            return {
                "stopped": True,
                "running": False,
                "elevated": True,
                "game": game,
                "proc": proc_name,
                "message": f"{spec.label}已关闭",
            }
        raise HTTPException(status_code=500, detail=f"关闭失败: {message}")
    gone = _wait_proc_gone(proc_name, 3.0)
    return {
        "stopped": gone,
        "running": not gone,
        "game": game,
        "proc": proc_name,
        "message": f"{spec.label}已关闭" if gone else f"已发出结束指令，{proc_name} 仍在退出中",
    }

