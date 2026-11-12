"""OCR 引擎封装：PaddleOCR 为可选依赖，未安装时给出明确提示。

设计上 OCR 只是"识别"环节，识别结果永远先返回给前端人工核对，
确认后才入库（对应 /api/upload 的两段式流程），从流程上消化识别误差。
"""

from __future__ import annotations

from pathlib import Path

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
    try:
        _engine = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    except Exception as exc:
        raise OcrUnavailable(f"PaddleOCR 初始化失败: {exc}") from exc
    return _engine


def ocr_image(path: str | Path) -> str:
    engine = _load_engine()
    try:
        result = engine.ocr(str(path), cls=True)
    except Exception as exc:
        raise OcrUnavailable(f"OCR 识别失败: {exc}") from exc
    lines: list[str] = []
    for page in result or []:
        if not page:
            continue
        for item in page:
            text = item[1][0] if len(item) > 1 and item[1] else ""
            if text and text.strip():
                lines.append(text.strip())
    return "\n".join(lines)
