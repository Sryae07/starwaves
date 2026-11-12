"""OCR 引擎封装：PaddleOCR 为可选依赖，未安装时给出明确提示。

设计上 OCR 只是"识别"环节，识别结果永远先返回给前端人工核对，
确认后才入库（对应 /api/upload 的两段式流程），从流程上消化识别误差。
PaddleOCR 2.x 与 3.x 的构造参数和返回结构不同，这里做了双版本兼容。
"""

from __future__ import annotations

import os
from pathlib import Path

# PaddleOCR 3.x 在部分网络环境下模型源连通性检查会失败，绕过该检查
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


def _fix_non_ascii_cache_path() -> None:
    """PaddlePaddle 的 C++ 推理层在中文用户名目录下会读取模型配置失败，
    Windows 上把用户目录与模型缓存重定向到纯 ASCII 路径（C:\\Users\\Public）。
    覆盖 2.x（~/.paddleocr）与 3.x（~/.paddlex）两代缓存位置。"""
    if os.name != "nt":
        return
    home = os.environ.get("USERPROFILE") or ""
    public = os.environ.get("PUBLIC", "C:/Users/Public")
    if not home.isascii():
        os.environ["USERPROFILE"] = public
    cache = os.environ.get("PADDLE_PDX_CACHE_HOME")
    if not (cache and cache.isascii()):
        os.environ["PADDLE_PDX_CACHE_HOME"] = str(Path(public) / ".paddlex")


_fix_non_ascii_cache_path()

_engine = None


class OcrUnavailable(RuntimeError):
    pass


def _load_engine():
    global _engine
    if _engine is not None:
        return _engine
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise OcrUnavailable(
            "未安装 PaddleOCR，无法识别截图。请执行 pip install -r requirements-ocr.txt"
            "（需要 Python <= 3.12），或改用页面上的手动录入 / JSON 上传方式更新数据。"
        ) from exc
    attempts = (
        dict(use_angle_cls=True, lang="ch", show_log=False),  # 2.x
        dict(lang="ch"),  # 3.x
        dict(),  # 兜底：使用默认配置
    )
    last_error = None
    for kwargs in attempts:
        try:
            _engine = PaddleOCR(**kwargs)
            break
        except Exception as exc:  # 参数不兼容时尝试下一组
            last_error = exc
    if _engine is None:
        raise OcrUnavailable(f"PaddleOCR 初始化失败: {last_error}")
    return _engine


def ocr_image(path: str | Path) -> str:
    engine = _load_engine()
    try:
        try:
            result = engine.ocr(str(path), cls=True)  # 2.x
        except TypeError:
            result = engine.ocr(str(path))  # 3.x 不再支持 cls 参数
    except Exception as exc:
        raise OcrUnavailable(f"OCR 识别失败: {exc}") from exc
    lines: list[str] = []
    pages = result if isinstance(result, list) else [result]
    for page in pages:
        if isinstance(page, dict):  # 3.x：{"rec_texts": [...], ...}
            for text in page.get("rec_texts") or []:
                if text and text.strip():
                    lines.append(text.strip())
        elif page:  # 2.x：[[box, (text, score)], ...]
            for item in page:
                text = item[1][0] if len(item) > 1 and item[1] else ""
                if text and text.strip():
                    lines.append(text.strip())
    return "\n".join(lines)
