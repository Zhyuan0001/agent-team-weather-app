"""services/weather_service 集成测试：在线成功 / 失败降级 / 不降级 / 缓存。

使用假 provider 注入，绝不联网。
"""
from __future__ import annotations

from datetime import date

import pytest

from weather_app.core import models
from weather_app.core.errors import DateOutOfRangeError, WeatherUnavailableError
from weather_app.core.models import WeatherRecord
from weather_app.providers.base import WeatherProvider
from weather_app.services.weather_service import WeatherService


DAY = date(2023, 7, 15)


def _online_record(day=DAY):
    return WeatherRecord(date=day, condition=models.SUNNY, temp_c=25.0,
                         humidity=60.0, wind_kph=10.0, source=models.SOURCE_OPEN_METEO)


def _offline_record(day=DAY):
    return WeatherRecord(date=day, condition=models.CLOUDY, temp_c=18.0,
                         humidity=55.0, wind_kph=8.0, source=models.SOURCE_OFFLINE)


class FakeProvider(WeatherProvider):
    """可配置的假 provider：记录调用次数，按需返回记录或抛异常。"""

    def __init__(self, record=None, exc=None, name="fake"):
        self.name = name
        self.record = record
        self.exc = exc
        self.calls = 0

    def fetch(self, day):
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        return self.record if self.record is not None else _offline_record(day)


def make_service(online=None, offline=None):
    online = online if online is not None else FakeProvider(_online_record())
    offline = offline if offline is not None else FakeProvider(_offline_record())
    return WeatherService(online_provider=online, offline_provider=offline), online, offline


# ---------------------------------------------------------------------------
# 在线成功
# ---------------------------------------------------------------------------
def test_online_success():
    service, online, offline = make_service()
    record = service.get_weather(DAY, use_online=True)
    assert record.source == models.SOURCE_OPEN_METEO
    assert record == _online_record()
    assert service.last_fallback is False
    assert online.calls == 1
    assert offline.calls == 0


# ---------------------------------------------------------------------------
# 在线失败 -> 自动降级
# ---------------------------------------------------------------------------
def test_online_failure_degrades_to_offline():
    service, online, offline = make_service(
        online=FakeProvider(exc=WeatherUnavailableError("boom"))
    )
    record = service.get_weather(DAY, use_online=True)
    assert record.source == models.SOURCE_OFFLINE
    assert service.last_fallback is True
    assert online.calls == 1
    assert offline.calls == 1


# ---------------------------------------------------------------------------
# DateOutOfRangeError 不得降级
# ---------------------------------------------------------------------------
def test_date_out_of_range_is_not_degraded():
    service, online, offline = make_service(
        online=FakeProvider(exc=DateOutOfRangeError("out of range"))
    )
    with pytest.raises(DateOutOfRangeError):
        service.get_weather(DAY, use_online=True)
    assert offline.calls == 0
    assert service.last_fallback is False


# ---------------------------------------------------------------------------
# use_online=False 直接走离线
# ---------------------------------------------------------------------------
def test_use_online_false_goes_offline_directly():
    service, online, offline = make_service()
    record = service.get_weather(DAY, use_online=False)
    assert record.source == models.SOURCE_OFFLINE
    assert online.calls == 0
    assert offline.calls == 1
    assert service.last_fallback is False


# ---------------------------------------------------------------------------
# 缓存命中：provider 只被调用一次
# ---------------------------------------------------------------------------
def test_online_cache_hit_calls_provider_once():
    service, online, offline = make_service()
    service.get_weather(DAY, use_online=True)
    service.get_weather(DAY, use_online=True)
    assert online.calls == 1
    assert offline.calls == 0


def test_offline_cache_hit_calls_offline_once():
    service, online, offline = make_service()
    service.get_weather(DAY, use_online=False)
    service.get_weather(DAY, use_online=False)
    assert offline.calls == 1


def test_clear_cache_forces_refetch():
    service, online, offline = make_service()
    service.get_weather(DAY, use_online=True)
    service.clear_cache()
    service.get_weather(DAY, use_online=True)
    assert online.calls == 2


# ---------------------------------------------------------------------------
# 参数校验
# ---------------------------------------------------------------------------
def test_non_date_raises_value_error():
    service, _, _ = make_service()
    with pytest.raises(ValueError):
        service.get_weather("2023-07-15")


# ---------------------------------------------------------------------------
# 降级完备性：provider 抛出的非业务异常也应触发降级（SPEC F4）
# ---------------------------------------------------------------------------
def test_parse_style_exception_should_degrade():
    """上游解析类异常（AttributeError/ValueError）本质上属于“取不到数据”，
    按 SPEC F4 应降级为离线，而非直接穿透到界面。"""
    service, online, offline = make_service(
        online=FakeProvider(exc=AttributeError("'list' object has no attribute 'get'"))
    )
    record = service.get_weather(DAY, use_online=True)
    assert record.source == models.SOURCE_OFFLINE
    assert service.last_fallback is True


# ---------------------------------------------------------------------------
# 降级后无负缓存：持续失败会反复发起在线请求（影响“完全离线可演示”）
# ---------------------------------------------------------------------------
def test_repeated_offline_demo_should_not_retry_online_every_time():
    """降级演示场景下，连续查询不应每次都重新尝试（并重新等待超时）。"""
    service, online, offline = make_service(
        online=FakeProvider(exc=WeatherUnavailableError("no network"))
    )
    service.get_weather(DAY, use_online=True)
    service.get_weather(DAY, use_online=True)
    assert online.calls == 1, f"在线被重复尝试 {online.calls} 次（缺少失败记忆/负缓存）"
    assert offline.calls == 1
