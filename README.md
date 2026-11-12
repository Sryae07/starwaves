# StarWaves · 星穹铁道 × 鸣潮 双游档案

一个自托管的个人游戏数据看板：把《崩坏：星穹铁道》与《鸣潮》的账号数据
（等级 / 活跃天数 / 成就 / 体力 / 角色 / 资源）汇总到同一个页面，
带体力回满倒计时，支持生成公开分享链接。

> 非官方工具，仅供个人学习使用。米游社接口为社区逆向协议，存在风控与失效风险。

## 功能特性

- 双游戏合并看板：体力进度条 + 回满倒计时、等级/活跃天数/成就统计、资源、角色图鉴
- 体力历史曲线：最近 30 条快照自动画成趋势图，一眼看出体力波动
- 三种数据来源，任选其一或混用：
  1. 截图上传 + PaddleOCR 识别（先识别、人工核对、再入库，从流程上消化识别误差）
  2. 手动录入
  3. 星穹铁道米游社 Cookie 自动同步（可选，非官方接口）
- 页面内"米游社一键同步"按钮：配好 Cookie 后点一下即可刷新星铁数据
- 鸣潮本地导出桥接：本地辅助工具产出 JSON，`tools/wuwa_export.py` 一键上传
- 公开分享页：`https://你的域名/?share=xxx` 只读展示，无需登录
- SQLite 零配置存储，每次更新留存历史快照
- Docker 一键部署（OCR 作为可选构建参数）

## 架构

```
┌──────────────┐   截图/手动/JSON   ┌────────────────────────────┐
│   浏览器看板  │ ────────────────▶ │  FastAPI 后端               │
│  (Tailwind)  │                   │  ├─ /api/profiles  手动入库  │
└──────▲───────┘                   │  ├─ /api/upload   截图 OCR   │
       │ JSON 只读分享              │  ├─ /api/sync/hsr 米游社同步 │
       └───────────────────────────│  └─ SQLite (SQLAlchemy)      │
                                   └──────────┬──────────────────┘
                          PaddleOCR（可选）    米游社（可选，非官方）
```

## 快速开始

要求 Python 3.10+。

```powershell
git clone https://github.com/Sryae07/starwaves.git
cd starwaves
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

浏览器打开 <http://127.0.0.1:8000>，点右上角"更新数据"即可手动录入；
截图上传需要先安装 OCR（见下节）。

### Docker 部署

```powershell
Copy-Item .env.example .env   # 填好 API_KEY 与 HKRPG_COOKIE
docker compose up -d --build
```

- 数据持久化在 `starwaves-data` 卷中，重启不丢
- 需要截图 OCR 时：`docker compose build --build-arg WITH_OCR=true`
  （镜像体积会明显变大，请自行评估）
- `.env` 中的变量会自动注入容器

## OCR 安装（可选）

```powershell
pip install -r requirements-ocr.txt
```

首次识别会下载中文模型（约 25MB）。几点说明：

- 版本固定在 paddleocr 2.10 + paddlepaddle 2.6.2：3.x 在部分 Windows CPU
  上 oneDNN 推理会崩溃，代码同时兼容两代 API
- 需要 Python 3.12 及以下（PaddlePaddle 2.x 无 3.13+ 轮子）
- 中文用户名路径（如 `C:\Users\张三`）会导致 Paddle 的 C++ 推理层无法读取
  模型文件，`app/services/ocr.py` 会自动把模型缓存重定向到
  `C:\Users\Public\.paddleocr`，无需手动处理
- 若首次下载模型失败（网络原因），可设置
  `$env:PADDLE_PDX_MODEL_SOURCE='ModelScope'` 换模型源后重试

## 米游社自动同步（星穹铁道，可选、有风险）

1. 浏览器登录米游社网页版（`webstatic.mihoyo.com`）
2. F12 打开开发者工具，抓任意 `api-takumi-record.mihoyo.com` 请求
3. 复制请求头里的完整 Cookie 串，写入 `.env` 的 `HKRPG_COOKIE`
4. 重启服务后，点击看板星铁卡片右上角的"🔄 米游社同步"按钮（或 `POST /api/sync/hsr`）

> 看板页面的星铁卡片右上角已内置"🔄 米游社同步"按钮，配好 Cookie 后
> 直接点按钮即可，无需手动调接口。

注意事项：

- Cookie 只保存在本机 `.env`，不写入日志、数据库或响应
- Cookie 过期或请求过频会被风控；接口字段随版本变化，容错解析见
  `app/services/hoyolab.py`，字段变化时改候选键即可
- 这是社区逆向协议，不要高频调用，后果自负

## 鸣潮本地导出 JSON 格式

鸣潮没有官方开放数据接口。约定如下 JSON 契约，任何本地辅助工具
（读游戏日志 / 缓存 / 手动整理）产出该格式后即可上传：

```json
{
  "uid": "600012345",
  "nickname": "漂泊者",
  "level": 60,
  "active_days": 300,
  "achievements": 500,
  "stamina": {"current": 120, "max": 240},
  "resources": {"astrites": 12345, "shell_credits": 67890},
  "characters": [
    {"name": "忌炎", "rarity": 5, "level": 80, "element": "雷"}
  ]
}
```

```powershell
python tools/wuwa_export.py --file wuwa_data.json
# 服务端开了 API Key 时：
python tools/wuwa_export.py --file wuwa_data.json --api-key 你的Key
# 查看格式示例：
python tools/wuwa_export.py --example
```

## API 一览

| 方法 | 路径 | 说明 | 鉴权 |
| --- | --- | --- | --- |
| POST | `/api/profiles/{game}` | 手动 / OCR 校对后写入（game: hsr/wuwa） | X-API-Key |
| POST | `/api/upload/{game}` | 截图上传 OCR，`apply=true` 直接入库 | X-API-Key |
| POST | `/api/sync/hsr` | 米游社同步星铁数据 | X-API-Key |
| GET | `/api/me` | 我的档案（含分享 id） | X-API-Key |
| GET | `/api/share/{share_id}` | 公开只读档案 | 无 |
| GET | `/api/health` | 健康检查 | 无 |

写接口鉴权规则：`.env` 未配置 `API_KEY` 时放行（仅限本机调试），
配置后所有写接口要求 `X-API-Key` 请求头。

## 配置项（.env）

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy 连接串 | `sqlite:///./data/starwaves.db` |
| `API_KEY` | 写接口密钥，留空=本机调试模式 | 空 |
| `HOST` / `PORT` | 服务监听 | `127.0.0.1:8000` |
| `HKRPG_COOKIE` | 米游社 Cookie（可选） | 空 |
| `HKRPG_SERVER` | `cn` 国服 / `os` 国际服 | `cn` |
| `HKRPG_UID` | 指定角色 UID（可选） | 空 |

## 目录结构

```
app/
  main.py            # FastAPI 入口
  config.py          # 环境变量配置
  models.py          # SQLAlchemy 模型（Player/Profile/Snapshot/Character）
  schemas.py         # 请求体模型
  routers/           # public / profiles / uploads / sync
  services/          # parser(OCR解析) / ocr / profiles / serializers / hoyolab
  static/            # 前端看板（index.html + app.js）
tools/wuwa_export.py # 鸣潮 JSON 上传桥接
tests/               # pytest 测试
```

## 已知限制（实话实说）

1. **鸣潮无官方开放数据接口**：无法做到像星铁那样的全自动实时同步，
   只能靠本地工具导出 JSON 或截图 OCR，这是本项目最大的卡点
2. **米游社接口非官方**：随时可能失效或被风控，必须后端中转，
   绝不要把 Cookie 放到公网前端
3. **OCR 有识别误差**：字体、背景、模糊都会导致数字识别错误，
   所以设计成"先识别 → 人工校对 → 再入库"两段式流程

## Roadmap

- 鸣潮 PC 端本地缓存读取适配器（需要逆向本地数据格式，另开仓库更合适）
- 定时自动刷新（星铁侧，可配合系统计划任务调用 /api/sync/hsr）
- 多玩家注册登录、分享页自定义主题

## 免责声明

本项目与米哈游、库洛游戏无关，所有游戏数据归玩家本人所有。
仅用于个人学习与技术交流，请勿用于商业用途或高频抓取。
