#!/usr/bin/env python3
"""鸣潮本地数据导出桥接工具。

背景：鸣潮没有官方开放数据接口。本工具定义了一份"本地导出 JSON"契约，
任何本地辅助工具（读日志 / 读缓存 / 手动整理）只要产出这份 JSON，
就能用本工具一键上传到 StarWaves 服务端。

用法：
    python tools/wuwa_export.py --file wuwa_data.json
    python tools/wuwa_export.py --file wuwa_data.json --server http://127.0.0.1:8000
    python tools/wuwa_export.py --example   # 查看 JSON 格式示例

登录令牌与 API Key：--token <登录返回的 token>；服务端开启 API_KEY 时再追加 --api-key xxx。
"""

import argparse
import json
import sys
import urllib.request

DEFAULT_SERVER = "http://127.0.0.1:8000"

EXAMPLE = {
    "uid": "600012345",
    "nickname": "漂泊者",
    "level": 60,
    "active_days": 300,
    "achievements": 500,
    "stamina": {"current": 120, "max": 240},
    "resources": {"astrites": 12345, "shell_credits": 67890},
    "characters": [
        {"name": "忌炎", "rarity": 5, "level": 80, "element": "雷"},
        {"name": "漂泊者", "rarity": 5, "level": 70, "element": "气动"},
    ],
    "challenges": {
        "tower": {
            "name": "逆境深塔",
            "season": "1.4 版本",
            "progress": {"current": 24, "max": 30, "unit": "星"},
            "nodes": [
                {"name": "左塔", "value": 10, "max": 12},
                {"name": "右塔", "value": 14, "max": 18},
            ],
        }
    },
}


def build_payload(raw: dict) -> dict:
    """本地导出 JSON 契约原样上传（含 characters / challenges），由服务端 /api/import 解析。"""
    return raw


def upload(server: str, payload: dict, token: str | None, api_key: str | None) -> None:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(
        f"{server.rstrip('/')}/api/import/wuwa",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(f"上传成功：HTTP {resp.status}")
        print(resp.read().decode("utf-8")[:800])


def main() -> int:
    parser = argparse.ArgumentParser(description="鸣潮本地数据导出桥接工具")
    parser.add_argument("--file", help="本地 JSON 数据文件路径")
    parser.add_argument("--server", default=DEFAULT_SERVER, help=f"StarWaves 服务地址（默认 {DEFAULT_SERVER}）")
    parser.add_argument("--token", default=None, help="登录令牌（/api/auth/login 返回的 token）")
    parser.add_argument("--api-key", default=None, help="服务端 API_KEY（未配置时可省略）")
    parser.add_argument("--example", action="store_true", help="打印 JSON 格式示例")
    args = parser.parse_args()

    if args.example:
        print(json.dumps(EXAMPLE, ensure_ascii=False, indent=2))
        return 0
    if not args.file:
        parser.print_help()
        return 1

    try:
        with open(args.file, encoding="utf-8") as f:
            raw = json.load(f)
        upload(args.server, build_payload(raw), args.token, args.api_key)
        return 0
    except (OSError, json.JSONDecodeError) as exc:
        print(f"读取 JSON 失败：{exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # 网络 / 服务端错误
        print(f"上传失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
