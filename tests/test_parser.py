import pytest

from app.services.parser import parse_ocr_text

HSR_TEXT = """
UID 123456789
开拓等级 70
活跃天数 512
成就 999/1000
开拓力 90 / 240
角色数量 42
"""

WUWA_TEXT = """
UID　６０００１２３４５
联觉等级 ６０
活跃天数 ３００
成就 ５００
结晶波片 １２０／２４０
"""


def test_parse_hsr():
    p = parse_ocr_text(HSR_TEXT, "hsr")
    assert p["uid"] == "123456789"
    assert p["level"] == 70
    assert p["active_days"] == 512
    assert p["achievements"] == 999
    assert p["stamina_current"] == 90
    assert p["stamina_max"] == 240
    assert p["characters"] == 42
    assert p["missing_fields"] == []


def test_parse_wuwa_fullwidth():
    p = parse_ocr_text(WUWA_TEXT, "wuwa")
    assert p["uid"] == "600012345"
    assert p["level"] == 60
    assert p["active_days"] == 300
    assert p["achievements"] == 500
    assert p["stamina_current"] == 120
    assert p["stamina_max"] == 240
    assert "characters" in p["missing_fields"]


def test_unknown_game():
    with pytest.raises(ValueError):
        parse_ocr_text("", "genshin")
