"""游戏注册表：项目支持哪些游戏、各自的规则与主题，全部集中在此登记。

新增一款游戏只需四步，业务代码与前端几乎不用改动：

1. 在下方 GAMES 中新增一条 GameSpec（体力规则 / 主题色 / OCR 关键词 / 资讯源）；
2. 如需米游社自动同步，在 services/hoyolab.py 增加对应抓取函数，
   并在 routers/sync.py 增加一条 /api/sync/{game} 路由；
3. 如需独立的资讯数据源，在 services/news.py 增加一个 Provider 并引用；
4. 前端看板与资讯页均按注册表动态渲染，无需修改 HTML。

字段说明：
- key: 唯一标识，写入数据库的 game 字段，发布后不要修改（历史数据按它归档）；
- stamina_name / minutes_per_point / cap: 体力名称、每点恢复分钟数、体力上限；
- syncable: 是否提供官方(逆向)接口自动同步；
- launch_env_key: 启动游戏可执行文件的环境变量覆盖名（留空则只走候选路径探测）；
- launch_candidates: Windows 安装路径候选，支持 glob 通配；
- ocr_keywords: 截图 OCR 关键词表，截图上"关键词: 数字"的格式即可被解析；
- resource_labels: 资源字段中文名（前端展示、OCR 解析共用）；
- news: 资讯数据源配置，由 services/news.py 的 Provider 消费。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GameSpec:
    key: str
    label: str
    tagline: str
    emoji: str
    color_a: str
    color_b: str
    stamina_name: str
    minutes_per_point: int
    cap: int
    syncable: bool = False
    launch_env_key: str = ""
    launch_candidates: tuple[str, ...] = ()
    ocr_keywords: dict = field(default_factory=dict)
    resource_labels: dict = field(default_factory=dict)
    news: dict = field(default_factory=dict)


GAMES: dict[str, GameSpec] = {
    "hsr": GameSpec(
        key="hsr",
        label="星穹铁道",
        tagline="愿此行，终抵群星",
        emoji="🚂",
        color_a="#fcd34d",
        color_b="#8b5cf6",
        stamina_name="开拓力",
        minutes_per_point=6,
        cap=240,
        syncable=True,
        launch_env_key="LAUNCH_HSR_PATH",
        launch_candidates=(
            r"C:\Program Files\Star Rail\Games\StarRail.exe",
            r"C:\Program Files (x86)\Star Rail\Games\StarRail.exe",
            r"C:\Program Files\HoYoPlay\games\*\Games\StarRail.exe",
            r"C:\Program Files\miHoYo Launcher\*\HYP.exe",
        ),
        ocr_keywords={
            "uid": ["uid"],
            "level": ["开拓等级", "等级"],
            "active_days": ["活跃天数"],
            "achievements": ["成就"],
            "stamina": ["开拓力"],
            "characters": ["角色数量", "拥有角色", "角色数"],
        },
        resource_labels={
            "jades": "星琼", "credits": "信用点", "starlight": "星芒",
            "embers": "余烬", "special_pass": "星轨专票", "star_pass": "星轨通票",
        },
        news={
            "provider": "miyoushe",
            "source_label": "米游社",
            "forum_id": 53,
            "article_base": "https://www.miyoushe.com/hsr/article/",
        },
    ),
    "wuwa": GameSpec(
        key="wuwa",
        label="鸣潮",
        tagline="浪潮退去，故人归乡",
        emoji="🌊",
        color_a="#67e8f9",
        color_b="#3b82f6",
        stamina_name="结晶波片",
        minutes_per_point=6,
        cap=240,
        launch_env_key="LAUNCH_WUWA_PATH",
        launch_candidates=(
            r"C:\Program Files\Wuthering Waves\Wuthering Waves Game\Client\Binaries\Win64\Client-Win64-Shipping.exe",
            r"C:\Program Files\Wuthering Waves\*\Client\Binaries\Win64\Client-Win64-Shipping.exe",
        ),
        ocr_keywords={
            "uid": ["uid"],
            "level": ["联觉等级", "等级"],
            "active_days": ["活跃天数"],
            "achievements": ["成就"],
            "stamina": ["结晶波片", "波片"],
            "characters": ["角色数量", "共鸣者数量", "角色数"],
        },
        resource_labels={
            "astrites": "星声", "shell_credits": "贝币", "waveplates": "结晶波片",
        },
        news={
            "provider": "kuro_site",
            "source_label": "鸣潮官网",
            "json_url": "https://media-cdn-mingchao.kurogame.com/akiwebsite/website2.0/json/G152/zh/ArticleMenu.json",
            "article_base": "https://mc.kurogames.com/main/news/detail/",
        },
    ),
    "zzz": GameSpec(
        key="zzz",
        label="绝区零",
        tagline="不惧喧嚣，加入绳匠",
        emoji="⚡",
        color_a="#fbbf24",
        color_b="#06b6d4",
        stamina_name="电量",
        minutes_per_point=6,
        cap=240,
        launch_env_key="LAUNCH_ZZZ_PATH",
        launch_candidates=(
            r"C:\Program Files\HoYoPlay\games\*\ZenlessZoneZero.exe",
            r"C:\Program Files\HoYoPlay\games\*\Game\ZenlessZoneZero.exe",
        ),
        ocr_keywords={
            "uid": ["uid"],
            "level": ["绳网等级", "等级"],
            "active_days": ["活跃天数"],
            "achievements": ["成就"],
            "stamina": ["电量"],
            "characters": ["代理人数量", "角色数量", "角色数"],
        },
        resource_labels={
            "polychrome": "菲林", "denny": "丁尼", "master_tape": "加密母带",
            "boopons": "邦布券", "battery": "电量",
        },
        news={
            "provider": "miyoushe",
            "source_label": "米游社",
            "forum_id": 58,
            "article_base": "https://www.miyoushe.com/zzz/article/",
        },
    ),
}


def known_game(key: str) -> bool:
    return key in GAMES


def get_spec(key: str) -> GameSpec:
    try:
        return GAMES[key]
    except KeyError:
        raise ValueError(f"未知游戏: {key}，支持: {', '.join(GAMES)}") from None


def game_rules() -> dict:
    """兼容旧代码的体力规则视图。"""
    return {
        spec.key: {
            "label": spec.label,
            "stamina_name": spec.stamina_name,
            "minutes_per_point": spec.minutes_per_point,
            "cap": spec.cap,
        }
        for spec in GAMES.values()
    }


def game_meta() -> list[dict]:
    """前端 /api/games 使用的注册表元数据。"""
    return [
        {
            "key": spec.key,
            "label": spec.label,
            "tagline": spec.tagline,
            "emoji": spec.emoji,
            "stamina_name": spec.stamina_name,
            "minutes_per_point": spec.minutes_per_point,
            "cap": spec.cap,
            "syncable": spec.syncable,
            "colors": {"a": spec.color_a, "b": spec.color_b},
            "resource_labels": spec.resource_labels,
        }
        for spec in GAMES.values()
    ]
