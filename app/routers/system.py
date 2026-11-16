"""系统控制：远程关机（服务跑在机主电脑上，仅机主可操作）。

安全说明：
- 关机只接受倒计时秒数，绝不接受任意命令；
- 写接口受 API_KEY 保护（配置后），公网部署务必设置 API_KEY；
- 默认至少 30 秒缓冲，期间可随时取消；
- 使用 Windows InitiateSystemShutdownExW / AbortSystemShutdownW 实现，
  不依赖本机 shutdown.exe（部分系统上该程序会异常报 203）；
- 仅支持 Windows 本机部署。
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .deps import require_api_key, require_owner

router = APIRouter(prefix="/api/system", tags=["system"])

MIN_DELAY_SECONDS = 30
MAX_DELAY_SECONDS = 3600
DRY_RUN = os.getenv("SHUTDOWN_DRY_RUN", "").strip() == "1"

_SHUTDOWN_MESSAGE = "星舟看板：机主通过网页发起了远程关机"


class ShutdownRequest(BaseModel):
    delay_seconds: int = Field(default=60, ge=MIN_DELAY_SECONDS, le=MAX_DELAY_SECONDS)


def _enable_shutdown_privilege() -> None:
    """标准用户令牌里 SeShutdownPrivilege 默认停用，先手动启用再调关机 API。"""
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    ker = ctypes.WinDLL("kernel32", use_last_error=True)
    HANDLE = wintypes.HANDLE
    DWORD = wintypes.DWORD
    BOOL = wintypes.BOOL

    class LUID(ctypes.Structure):
        _fields_ = [("LowPart", DWORD), ("HighPart", wintypes.LONG)]

    class LUID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Luid", LUID), ("Attributes", DWORD)]

    class TOKEN_PRIVILEGES(ctypes.Structure):
        _fields_ = [("PrivilegeCount", DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]

    ker.GetCurrentProcess.restype = HANDLE
    adv.OpenProcessToken.argtypes = [HANDLE, DWORD, ctypes.POINTER(HANDLE)]
    adv.OpenProcessToken.restype = BOOL
    adv.LookupPrivilegeValueW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(LUID)]
    adv.LookupPrivilegeValueW.restype = BOOL
    adv.AdjustTokenPrivileges.argtypes = [
        HANDLE, BOOL, ctypes.POINTER(TOKEN_PRIVILEGES), DWORD,
        ctypes.POINTER(TOKEN_PRIVILEGES), ctypes.POINTER(DWORD),
    ]
    adv.AdjustTokenPrivileges.restype = BOOL

    token = HANDLE()
    if not adv.OpenProcessToken(ker.GetCurrentProcess(), 0x20 | 0x8, ctypes.byref(token)):
        raise HTTPException(status_code=500, detail=f"读取关机权限失败（错误码 {ctypes.get_last_error()}）")
    luid = LUID()
    if not adv.LookupPrivilegeValueW(None, "SeShutdownPrivilege", ctypes.byref(luid)):
        raise HTTPException(status_code=500, detail=f"查询关机权限失败（错误码 {ctypes.get_last_error()}）")
    privileges = TOKEN_PRIVILEGES()
    privileges.PrivilegeCount = 1
    privileges.Privileges[0].Luid = luid
    privileges.Privileges[0].Attributes = 2  # SE_PRIVILEGE_ENABLED
    if not adv.AdjustTokenPrivileges(token, False, ctypes.byref(privileges), 0, None, None):
        raise HTTPException(status_code=500, detail=f"启用关机权限失败（错误码 {ctypes.get_last_error()}）")


def _run_shutdown_api(delay_seconds: int | None) -> dict:
    """通过 Windows API 排程/取消关机。delay_seconds 为 None 表示取消。"""
    if DRY_RUN:
        action = "cancel" if delay_seconds is None else f"schedule({delay_seconds}s)"
        return {"executed": False, "dry_run": True, "command": f"windows-api:{action}"}
    _enable_shutdown_privilege()
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    if delay_seconds is None:
        adv.AbortSystemShutdownW.argtypes = [wintypes.LPCWSTR]
        adv.AbortSystemShutdownW.restype = wintypes.BOOL
        if not adv.AbortSystemShutdownW(None):
            return {"executed": True, "note": "当前没有进行中的关机"}
        return {"executed": True}
    adv.InitiateSystemShutdownExW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.BOOL, wintypes.DWORD,
    ]
    adv.InitiateSystemShutdownExW.restype = wintypes.BOOL
    ok = adv.InitiateSystemShutdownExW(
        None, _SHUTDOWN_MESSAGE, delay_seconds, False, True, 0x80000000,
    )
    if not ok:
        raise HTTPException(status_code=500, detail=f"关机指令执行失败（错误码 {ctypes.get_last_error()}）")
    return {"executed": True}


@router.post("/shutdown", dependencies=[Depends(require_api_key), Depends(require_owner)])
def schedule_shutdown(request: ShutdownRequest) -> dict:
    if os.name != "nt":
        raise HTTPException(status_code=501, detail="远程关机仅支持 Windows 本机部署")
    result = _run_shutdown_api(request.delay_seconds)
    return {
        "shutdown": True,
        "delay_seconds": request.delay_seconds,
        "note": f"电脑将在 {request.delay_seconds} 秒后关机，期间可通过本接口或本机执行 shutdown /a 中止",
        **result,
    }


@router.post("/cancel-shutdown", dependencies=[Depends(require_api_key), Depends(require_owner)])
def cancel_shutdown() -> dict:
    if os.name != "nt":
        raise HTTPException(status_code=501, detail="远程关机仅支持 Windows 本机部署")
    result = _run_shutdown_api(None)
    return {"shutdown": False, **result}
