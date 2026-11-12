# StarWaves · 多游戏档案 + 官方资讯聚合

一个自托管的个人游戏数据看板：把《崩坏：星穹铁道》《鸣潮》《绝区零》的账号数据
（等级 / 活跃天数 / 成就 / 体力 / 角色 / 资源）汇总到同一个页面，
带体力回满倒计时与历史曲线，支持生成公开分享链接、自定义网页背景，
还能在看板上一键启动游戏，并内置一个实时聚合官方公告 / 动态的资讯中心。
游戏列表由注册表（`app/games.py`）驱动，后续接入新游戏无需改前端。

> 非官方工具，仅供个人学习使用。米游社接口为社区逆向协议，存在风控与失效风险。

官网首页（GitHub Pages，点开即见）：**<https://sryae07.github.io/starwaves/>**

## 功能特性

- 多游戏合并看板：体力进度条 + 回满倒计时、等级/活跃天数/成就统计、资源、角色图鉴
- 👤 账号系统：手机验证码注册、用户名（或手机号）+ 密码登录；用户名即档案名，
  不填自动生成「用户＋随机不重复编号」，多账号数据互相隔离、各自一条分享链接
- 🔗 官方式接入（星穹铁道）：看板输入 UID 一键拉取米游社「战绩」——
  等级 / 活跃天数 / 成就 / 体力 / 角色柜台（含命座与命途）/ 忘却之庭 / 虚构叙事 /
  末日幻影 / 模拟宇宙挑战进度，单个挑战接口失败不影响整体同步
- 📦 本地 JSON 导入（鸣潮等）：粘贴本地工具导出的 JSON 即入库，
  角色、资源与挑战进度（如逆境深塔）与星铁共用同一套展示
- 📡 资讯中心（`/news`）：聚合各游戏官方公告 / 新闻 / 活动（星铁·绝区零走米游社论坛、鸣潮走库洛官网 JSON），
  后端 5 分钟 TTL 缓存 + 页面自动轮询，数据源故障自动降级，支持关键词搜索过滤
- 注册表驱动的游戏接入：新增游戏只需在 `app/games.py` 登记一条 `GameSpec`
  （体力规则 / 主题色 / OCR 关键词 / 资讯源），看板与资讯页自动渲染
- ➕ 看板内「接入游戏」：不用改代码，网页上填张表单即可接入任意游戏
  （名称 / 体力规则 / 主题色 / 资源标签），手动录入与截图 OCR 立即可用
- 体力历史曲线：最近 30 条快照自动画成趋势图
- 网页背景自定义：上传一张图即全站生效（首页 / 看板 / 分享页），可一键恢复默认
- 一键启动游戏：服务跑在本机，看板上点一下直接拉起星铁 / 鸣潮
- 三种数据来源，任选其一或混用：
  1. 截图上传 + PaddleOCR 识别（先识别、人工核对、再入库，从流程上消化识别误差）
  2. 手动录入
  3. 星穹铁道米游社 Cookie 自动同步（可选，非官方接口）
- 页面内"米游社一键同步"按钮：配好 Cookie 后点一下即可刷新星铁数据
- 鸣潮本地导出桥接：本地辅助工具产出 JSON，`tools/wuwa_export.py` 一键上传
- 公开分享页：`/share/{share_id}` 只读展示，无需登录
- 官网首页：项目作用、功能介绍、"关于"版块
- SQLite 零配置存储，每次更新留存历史快照
- Docker 一键部署（OCR 作为可选构建参数）

## 页面结构

- `/` 官网首页：项目作用、功能介绍、关于版块
- `/dashboard` 数据看板：多游戏档案 + 更新数据（管理端）
- `/news` 资讯中心：官方公告 / 动态实时聚合，每 5 分钟自动刷新
- `/share/{share_id}` 公开档案：只读分享页，无需登录

## 架构

```
┌──────────────┐   截图/手动/JSON   ┌────────────────────────────┐
│   浏览器页面  │ ────────────────▶ │  FastAPI 后端               │
│  (Tailwind)  │                   │  ├─ /api/profiles  手动入库  │
└──────▲───────┘                   │  ├─ /api/upload   截图 OCR   │
       │ JSON 只读分享              │  ├─ /api/sync/hsr 米游社同步 │
       └───────────────────────────│  ├─ /api/news     官方资讯   │
                                   │  ├─ /api/launch   启动游戏   │
                                   │  └─ SQLite (SQLAlchemy)      │
                                   └────┬───────────┬────────────┘
                          PaddleOCR（可选） 米游社/库洛官网资讯源
```

## 快速开始

要求 Python 3.10+（OCR 需要 ≤3.12）。

```powershell
git clone https://github.com/Sryae07/starwaves.git
cd starwaves
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

浏览器打开 <http://127.0.0.1:8000>（官网首页），看板在
<http://127.0.0.1:8000/dashboard>。Windows 下也可以直接双击 `start.bat`，
自动准备环境、启动服务并打开浏览器。

首次打开看板点「👤 登录 / 注册」：手机注册流程在开发模式下会把 6 位验证码
直接显示在弹窗里（未接入真实短信服务），填上即可注册登录。
若你的旧数据（无账号时代录的档案）存在，服务启动时会自动创建一个初始账号
接管它，随机初始密码写入 `data/initial_password.txt` 并打印到控制台。

### Docker 部署

```powershell
Copy-Item .env.example .env   # 填好 API_KEY 与 HKRPG_COOKIE
docker compose up -d --build
```

- 数据持久化在 `starwaves-data` 卷中，重启不丢
- 需要截图 OCR 时：`docker compose build --build-arg WITH_OCR=true`
  （镜像体积会明显变大，请自行评估）
- `.env` 中的变量会自动注入容器

## GitHub Pages 官网

仓库已开启 GitHub Pages，首页镜像托管于：
**<https://sryae07.github.io/starwaves/>**

- 镜像源文件在 `docs/index.html`，与 `app/static/home.html` 保持一致
- GitHub Pages 免费档要求仓库公开；仓库内不含任何密钥（.env / 数据目录均被 gitignore）
- 公网页面的"进入看板"按钮指向 `http://127.0.0.1:8000/dashboard`（本机服务）

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

配置 Cookie 两种方式任选：看板「🔗 接入」弹窗里直接粘贴保存（存本机数据库），
或按下面步骤写入 `.env`：

1. 浏览器登录米游社网页版（`webstatic.mihoyo.com`）
2. F12 打开开发者工具，抓任意 `api-takumi-record.mihoyo.com` 请求
3. 复制请求头里的完整 Cookie 串，写入 `.env` 的 `HKRPG_COOKIE`
4. 重启服务后，点击看板星铁卡片右上角的"🔄 米游社同步"按钮（或 `POST /api/sync/hsr`）

注意事项：

- Cookie 只保存在本机数据库 / `.env`，不写入日志与响应
- Cookie 过期或请求过频会被风控；接口字段随版本变化，容错解析见
  `app/services/hoyolab.py`，字段变化时改候选键即可
- 这是社区逆向协议，不要高频调用，后果自负

### 官方式接入：输入 UID 自动同步

看板任意星铁卡片点「🔗 接入」→ 输入游戏 UID → 自动同步：

- 基本信息：昵称 / 等级 / 活跃天数 / 成就 / 开拓力
- 角色柜台：稀有度、等级、属性、命座、命途
- 挑战进度：忘却之庭 / 虚构叙事 / 末日幻影（层数与星级）、模拟宇宙（积分与战绩）
- 自动同步只能读取你 Cookie 对应米游社账号下的角色，输入别人的 UID 会被拒绝

**鸣潮说明（实话实说）**：库洛没有公开玩家数据接口，输入 UID 自动同步不可行。
「🔗 接入」弹窗里的 JSON 导入通道即为其官方替代：本地辅助工具产出
`tools/wuwa_export.py` 约定的 JSON（可含 `challenges` 挑战进度），粘贴即可，
展示效果与星铁一致。也可以继续用截图 OCR / 手动录入。

## 启动游戏（仅 Windows 本机部署）

看板卡片上的"🚀 启动游戏"由本机后端拉起游戏进程：

- 默认自动探测常见安装路径（星铁找不到本体时退回米哈游启动器 HYP.exe）
- 自定义路径：在 `.env` 中设置 `LAUNCH_HSR_PATH` / `LAUNCH_WUWA_PATH`
- 安全：只启动服务端配置的固定路径，前端无法传入任意命令；公网部署务必设置 `API_KEY`

## 自定义网页背景

看板右上角"🖼 背景"按钮：上传图片即全站生效（首页 / 看板 / 分享页），
可随时恢复默认星空背景。图片保存在本地 `data/`，不进 Git 仓库。

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
  ],
  "challenges": {
    "tower": {
      "name": "逆境深塔",
      "season": "1.4 版本",
      "progress": {"current": 24, "max": 30, "unit": "星"},
      "nodes": [{"name": "左塔", "value": 10, "max": 12}]
    }
  }
}
```

```powershell
python tools/wuwa_export.py --file wuwa_data.json
# 登录令牌（/api/auth/login 返回的 token）：
python tools/wuwa_export.py --file wuwa_data.json --token 你的token
# 服务端开了 API Key 时：
python tools/wuwa_export.py --file wuwa_data.json --token 你的token --api-key 你的Key
# 查看格式示例：
python tools/wuwa_export.py --example
```

## API 一览

| 方法 | 路径 | 说明 | 鉴权 |
| --- | --- | --- | --- |
| POST | `/api/auth/send-code` | 发送手机验证码（开发模式响应含 `dev_code`） | 无 |
| POST | `/api/auth/register` | 手机验证码注册（用户名留空自动生成） | 无 |
| POST | `/api/auth/login` | 用户名 / 手机号 + 密码登录，返回 Bearer token | 无 |
| POST | `/api/auth/logout` | 退出登录，令牌作废 | Bearer |
| POST | `/api/profiles/{game}` | 手动 / OCR 校对后写入（game: hsr/wuwa） | Bearer + X-API-Key |
| POST | `/api/upload/{game}` | 截图上传 OCR，`apply=true` 直接入库 | Bearer + X-API-Key |
| POST | `/api/sync/hsr` | 米游社同步星铁数据（请求体可选 `{"uid": "..."}`） | Bearer + X-API-Key |
| POST | `/api/bind/{game}` | 官方式接入：输入 UID 自动同步（仅星铁；鸣潮返回 501 说明） | Bearer + X-API-Key |
| POST | `/api/import/{game}` | 本地导出 JSON 一键导入（含 characters / challenges） | Bearer + X-API-Key |
| GET/PUT | `/api/settings/hoyolab-cookie` | 查看 / 保存米游社 Cookie（存本机数据库，.env 兜底） | Bearer + X-API-Key |
| POST | `/api/launch/{game}` | 启动本机游戏进程（仅 Windows） | Bearer + X-API-Key |
| POST | `/api/background` | 上传自定义背景图 | Bearer + X-API-Key |
| DELETE | `/api/background` | 恢复默认背景 | Bearer + X-API-Key |
| GET | `/api/background` | 获取当前背景图 | 无 |
| GET | `/api/me` | 我的档案（含用户名与分享 id） | Bearer + X-API-Key |
| GET | `/api/share/{share_id}` | 公开只读档案 | 无 |
| GET | `/api/games` | 游戏注册表元数据（前端动态渲染用） | 无 |
| GET | `/api/news?game=hsr&limit=12` | 官方资讯聚合（默认全部游戏） | 无 |
| POST | `/api/games` | 接入自定义游戏（表单见看板「➕ 接入游戏」） | Bearer + X-API-Key |
| DELETE | `/api/games/{key}` | 移除自定义游戏（已有数据时拒绝） | Bearer + X-API-Key |
| GET | `/api/health` | 健康检查 | 无 |

写接口鉴权规则：先要求登录（`Authorization: Bearer <token>`，注册/登录接口签发）；
`.env` 未配置 `API_KEY` 时不再要求密钥（仅限本机调试），
配置后写接口额外要求 `X-API-Key` 请求头（公网部署双保险）。

### 手机短信说明

默认是「开发模式」：没有接入短信服务商，`POST /api/auth/send-code` 会在响应里
直接返回 `dev_code`（同时打印到服务端日志），前端弹窗也会显示验证码。
接入真实短信时改 `app/routers/auth.py`：把 `dev_code` 从响应里移除，改为调用
阿里云 / 腾讯云短信 SDK 发送即可，其余流程（60s 冷却、5 分钟过期、
5 次错误锁定）无需改动。

## 配置项（.env）

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy 连接串 | `sqlite:///./data/starwaves.db` |
| `API_KEY` | 写接口密钥，留空=本机调试模式 | 空 |
| `HOST` / `PORT` | 服务监听 | `127.0.0.1:8000` |
| `HKRPG_COOKIE` | 米游社 Cookie（可选） | 空 |
| `HKRPG_SERVER` | `cn` 国服 / `os` 国际服 | `cn` |
| `HKRPG_UID` | 指定角色 UID（可选） | 空 |
| `LAUNCH_HSR_PATH` | 星铁启动路径（可选，自动探测兜底） | 空 |
| `LAUNCH_WUWA_PATH` | 鸣潮启动路径（可选，自动探测兜底） | 空 |
| `LAUNCH_ZZZ_PATH` | 绝区零启动路径（可选，自动探测兜底） | 空 |

## 添加新游戏（注册表驱动）

两条路任选：

**路线 A：看板网页直接接入（最简单）**
看板右上角「➕ 接入游戏」，填名称、英文标识、体力规则与主题色即可。
新游戏立刻出现在看板与更新弹窗中，支持手动录入和截图 OCR；
没有自动同步与官方资讯源（想加的话再走路线 B 补代码）。

**路线 B：代码注册（内置游戏，支持同步/资讯）**
接入新游戏不需要改前端。以新增「原神」为例：

1. 在 `app/games.py` 的 `GAMES` 里加一条 `GameSpec`：
   - 体力规则：`stamina_name`（如"原粹树脂"）、`minutes_per_point`（8）、`cap`（200）；
   - 主题色：`color_a` / `color_b`（看板卡片与进度条颜色）；
   - OCR 关键词：`ocr_keywords`（截图识别所需的字段关键词表）；
   - 资讯源：`news` 字段复用已有 Provider（如 `{"provider": "miyoushe", "forum_id": 26, ...}`）
     或先在 `app/services/news.py` 新写一个 Provider 类并登记到 `PROVIDERS`；
   - 可选：`syncable=True` + `services/hoyolab.py` 对应抓取函数 + `routers/sync.py` 一条路由（米游社同步）；
   - 可选：`launch_env_key` / `launch_candidates`（一键启动）。
2. 重启服务。看板、更新弹窗页签、资讯页筛选都会自动出现新游戏，
   数据库表结构无需变更（`Profile.game` 为字符串字段）。

注意：`key` 一旦有玩家数据就不要改名，历史快照按它归档。

## 目录结构

```
app/
  main.py            # FastAPI 入口（含页面路由）
  config.py          # 环境变量配置
  games.py           # 游戏注册表（新增游戏在这里登记）
  models.py          # SQLAlchemy 模型（User/AuthToken/PhoneCode/Player/Profile/Snapshot/Character）
  schemas.py         # 请求体模型
  security.py        # 密码散列 / 令牌 / 验证码 / 默认用户名
  routers/           # auth / public / profiles / uploads / sync / launch / settings / news / games
  services/          # parser(OCR解析) / ocr / profiles / serializers / hoyolab / news(资讯聚合)
  static/            # home.html(官网) / index.html + app.js(看板) / news.html(资讯中心)
tools/wuwa_export.py # 鸣潮 JSON 上传桥接
docs/                # GitHub Pages 官网镜像
tests/               # pytest 测试
start.bat            # Windows 一键启动脚本
```

## 已知限制（实话实说）

1. **鸣潮无官方开放数据接口**：无法做到像星铁那样的全自动实时同步，
   只能靠本地工具导出 JSON 或截图 OCR，这是本项目最大的卡点
2. **米游社接口非官方**：随时可能失效或被风控，必须后端中转，
   绝不要把 Cookie 放到公网前端
3. **OCR 有识别误差**：字体、背景、模糊都会导致数字识别错误，
   所以设计成"先识别 → 人工校对 → 再入库"两段式流程
4. **资讯源非官方承诺**：米游社论坛为社区协议、库洛官网 JSON 为官网静态资源，
   均可能随时调整字段或风控；后端做了 TTL 缓存与降级，失败时旧缓存兜底或显示为空

## Roadmap

- 鸣潮 PC 端本地缓存读取适配器（需要逆向本地数据格式，另开仓库更合适）
- 定时自动刷新（星铁侧，可配合系统计划任务调用 /api/sync/hsr）
- 鸣潮 B 站官方动态源（B 站 API 对本机 IP 有风控，暂以库洛官网资讯替代）
- 分享页自定义主题

## 免责声明

本项目与米哈游、库洛游戏无关，所有游戏数据归玩家本人所有。
仅用于个人学习与技术交流，请勿用于商业用途或高频抓取。
