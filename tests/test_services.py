from datetime import datetime

from app.models import Profile, Snapshot
from app.services.serializers import _stamina_payload


def test_recharge_math():
    profile = Profile(game="hsr")
    profile.snapshots.append(
        Snapshot(stamina_current=100, stamina_max=240, captured_at=datetime(2026, 1, 1, 8, 0, 0))
    )
    info = _stamina_payload(profile)
    assert info["current"] == 100
    assert info["full"] is False
    assert info["minutes_to_full"] == (240 - 100) * 6
    assert info["full_at"].endswith("+00:00")


def test_recharge_full():
    profile = Profile(game="wuwa")
    profile.snapshots.append(Snapshot(stamina_current=240, stamina_max=240))
    info = _stamina_payload(profile)
    assert info["full"] is True
    assert info["minutes_to_full"] == 0
    assert info["full_at"] is None


def test_recharge_without_snapshot():
    profile = Profile(game="hsr")
    info = _stamina_payload(profile)
    assert info["name"] == "开拓力"
    assert info["max"] == 240
    assert info["full_at"] is None
