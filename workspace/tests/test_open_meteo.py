"""providers/open_meteo 单元测试。

全程使用伪造的 requests.Session/Response，**绝不发起真实网络请求**。
覆盖：正常解析、畸形 payload（应统一抛 WeatherUnavailableError）、
日期超范围、HTTP 错误、超时、非法 JSON，以及 WMO 码映射。
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
import requests

from weather_app.core import date_utils, models
from weather_app.core.errors import DateOutOfRangeError, WeatherUnavailableError
from weather_app.providers import open_meteo
from weather_app.providers.open_meteo import OpenMeteoProvider


# ---------------------------------------------------------------------------
# 伪造的 requests 对象
# ---------------------------------------------------------------------------
class FakeResponse:
    def __init__(self, payload=None, status_code=200, json_exc=None):
        self._payload = payload
        self.status_code = status_code
        self._json_exc = json_exc

    def json(self):
        if self._json_exc is not None:
            raise self._json_exc
        return self._payload


class FakeSession:
    """记录调用参数、按配置返回响应或抛异常。"""

    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if self.exc is not None:
            raise self.exc
        return self.response


def make_payload(day, t_max=30, t_min=20, code=0, humidity=62, wind=12.3):
    return {
        "daily": {
            "time": [day.isoformat()],
            "temperature_2m_max": [t_max],
            "temperature_2m_min": [t_min],
            "weather_code": [code],
            "relative_humidity_2m_mean": [humidity],
            "wind_speed_10m_max": [wind],
        }
    }


@pytest.fixture()
def today():
    return date_utils.today()


# ---------------------------------------------------------------------------
# 正常解析
# ---------------------------------------------------------------------------
def test_fetch_normal_payload(today):
    day = today
    session = FakeSession(FakeResponse(make_payload(day, t_max=30, t_min=20, code=61,
                                                    humidity=62, wind=12.3)))
    provider = OpenMeteoProvider(session=session)

    record = provider.fetch(day)

    assert record.date == day
    assert record.temp_c == pytest.approx(25.0)     # (30+20)/2
    assert record.condition == models.RAIN          # WMO 61
    assert record.humidity == pytest.approx(62.0)
    assert record.wind_kph == pytest.approx(12.3)
    assert record.source == models.SOURCE_OPEN_METEO
    assert len(session.calls) == 1


def test_fetch_uses_forecast_url_for_today(today):
    session = FakeSession(FakeResponse(make_payload(today)))
    OpenMeteoProvider(session=session).fetch(today)
    assert session.calls[0]["url"] == open_meteo.FORECAST_URL


def test_fetch_uses_archive_url_for_past():
    day = date(2000, 1, 1)
    session = FakeSession(FakeResponse(make_payload(day)))
    OpenMeteoProvider(session=session).fetch(day)
    assert session.calls[0]["url"] == open_meteo.ARCHIVE_URL


def test_request_passes_timeout(today):
    session = FakeSession(FakeResponse(make_payload(today)))
    OpenMeteoProvider(session=session, timeout=3).fetch(today)
    assert session.calls[0]["timeout"] == 3


# ---------------------------------------------------------------------------
# 畸形 payload：应统一抛 WeatherUnavailableError（不得漏出 AttributeError/ValueError）
# ---------------------------------------------------------------------------
def test_parse_non_dict_payload_raises_unavailable():
    """payload 非 dict（如 list）时应抛业务异常，而非 AttributeError。"""
    provider = OpenMeteoProvider(session=FakeSession())
    with pytest.raises(WeatherUnavailableError):
        provider._parse(["not", "a", "dict"], date(2023, 7, 15))


def test_parse_none_payload_raises_unavailable():
    provider = OpenMeteoProvider(session=FakeSession())
    with pytest.raises(WeatherUnavailableError):
        provider._parse(None, date(2023, 7, 15))


def test_parse_missing_daily_raises_unavailable():
    provider = OpenMeteoProvider(session=FakeSession())
    with pytest.raises(WeatherUnavailableError):
        provider._parse({}, date(2023, 7, 15))


def test_parse_missing_both_temps_raises_unavailable():
    """两个温度字段都缺失时应抛业务异常。"""
    day = date(2023, 7, 15)
    payload = {"daily": {"time": [day.isoformat()]}}
    provider = OpenMeteoProvider(session=FakeSession())
    with pytest.raises(WeatherUnavailableError):
        provider._parse(payload, day)


def test_parse_string_temperature_raises_unavailable():
    """温度字段为字符串（无法转 float）时应抛业务异常，而非 ValueError。"""
    day = date(2023, 7, 15)
    payload = {"daily": {"time": [day.isoformat()],
                         "temperature_2m_max": ["abc"],
                         "temperature_2m_min": [20]}}
    provider = OpenMeteoProvider(session=FakeSession())
    with pytest.raises(WeatherUnavailableError):
        provider._parse(payload, day)


def test_parse_string_humidity_raises_unavailable():
    """湿度字段为不可解析字符串时应抛业务异常，而非 ValueError。"""
    day = date(2023, 7, 15)
    payload = {"daily": {"time": [day.isoformat()],
                         "temperature_2m_max": [30],
                         "temperature_2m_min": [20],
                         "relative_humidity_2m_mean": ["abc"]}}
    provider = OpenMeteoProvider(session=FakeSession())
    with pytest.raises(WeatherUnavailableError):
        provider._parse(payload, day)


def test_parse_missing_humidity_raises_unavailable():
    """关键字段 relative_humidity_2m_mean 缺失时应报错，而非静默回填 0。"""
    day = date(2023, 7, 15)
    payload = {"daily": {"time": [day.isoformat()],
                         "temperature_2m_max": [30],
                         "temperature_2m_min": [20],
                         "weather_code": [0],
                         "wind_speed_10m_max": [10]}}
    provider = OpenMeteoProvider(session=FakeSession())
    with pytest.raises(WeatherUnavailableError):
        provider._parse(payload, day)


def test_parse_missing_wind_raises_unavailable():
    """关键字段 wind_speed_10m_max 缺失时应报错，而非静默回填 0。"""
    day = date(2023, 7, 15)
    payload = {"daily": {"time": [day.isoformat()],
                         "temperature_2m_max": [30],
                         "temperature_2m_min": [20],
                         "weather_code": [0],
                         "relative_humidity_2m_mean": [60]}}
    provider = OpenMeteoProvider(session=FakeSession())
    with pytest.raises(WeatherUnavailableError):
        provider._parse(payload, day)


def test_parse_null_humidity_raises_unavailable():
    """湿度字段为 null 时应报错，而非静默回填 0。"""
    day = date(2023, 7, 15)
    payload = {"daily": {"time": [day.isoformat()],
                         "temperature_2m_max": [30],
                         "temperature_2m_min": [20],
                         "weather_code": [0],
                         "relative_humidity_2m_mean": [None],
                         "wind_speed_10m_max": [10]}}
    provider = OpenMeteoProvider(session=FakeSession())
    with pytest.raises(WeatherUnavailableError):
        provider._parse(payload, day)


def test_parse_field_name_mismatch_raises_unavailable():
    """字段名不符（温度键被改名）时应报错。"""
    day = date(2023, 7, 15)
    payload = {"daily": {"time": [day.isoformat()],
                         "temp_max": [30],
                         "temp_min": [20]}}
    provider = OpenMeteoProvider(session=FakeSession())
    with pytest.raises(WeatherUnavailableError):
        provider._parse(payload, day)


def test_parse_date_not_in_times_raises_unavailable():
    """目标日期不在返回数组时应视为数据异常，而不是静默取首项（会造成数据错配）。"""
    day = date(2023, 7, 15)
    payload = {"daily": {"time": ["2000-01-01"],
                         "temperature_2m_max": [30],
                         "temperature_2m_min": [20],
                         "weather_code": [0]}}
    provider = OpenMeteoProvider(session=FakeSession())
    with pytest.raises(WeatherUnavailableError):
        provider._parse(payload, day)


# ---------------------------------------------------------------------------
# 日期超范围 -> DateOutOfRangeError（且不应发起请求）
# ---------------------------------------------------------------------------
def test_fetch_before_min_supported_date():
    session = FakeSession(FakeResponse(make_payload(date(1939, 12, 31))))
    provider = OpenMeteoProvider(session=session)
    with pytest.raises(DateOutOfRangeError):
        provider.fetch(date_utils.MIN_SUPPORTED_DATE - timedelta(days=1))
    assert session.calls == []


def test_fetch_beyond_forecast_window():
    session = FakeSession(FakeResponse(make_payload(date(2023, 7, 15))))
    provider = OpenMeteoProvider(session=session)
    with pytest.raises(DateOutOfRangeError):
        provider.fetch(date_utils.max_supported_date() + timedelta(days=1))
    assert session.calls == []


def test_fetch_non_date_type():
    provider = OpenMeteoProvider(session=FakeSession())
    with pytest.raises(DateOutOfRangeError):
        provider.fetch("2023-07-15")


# ---------------------------------------------------------------------------
# 网络 / HTTP / JSON 错误 -> WeatherUnavailableError
# ---------------------------------------------------------------------------
def test_http_error_status_raises_unavailable(today):
    session = FakeSession(FakeResponse({"error": True}, status_code=500))
    provider = OpenMeteoProvider(session=session)
    with pytest.raises(WeatherUnavailableError):
        provider.fetch(today)


def test_timeout_raises_unavailable(today):
    session = FakeSession(exc=requests.Timeout("timed out"))
    provider = OpenMeteoProvider(session=session)
    with pytest.raises(WeatherUnavailableError):
        provider.fetch(today)


def test_connection_error_raises_unavailable(today):
    session = FakeSession(exc=requests.ConnectionError("no network"))
    provider = OpenMeteoProvider(session=session)
    with pytest.raises(WeatherUnavailableError):
        provider.fetch(today)


def test_invalid_json_raises_unavailable(today):
    session = FakeSession(FakeResponse(json_exc=ValueError("bad json")))
    provider = OpenMeteoProvider(session=session)
    with pytest.raises(WeatherUnavailableError):
        provider.fetch(today)


# ---------------------------------------------------------------------------
# 通过 monkeypatch 伪造 requests.Session（不注入 session 的默认构造路径）
# ---------------------------------------------------------------------------
def test_default_construction_uses_monkeypatched_session(monkeypatch, today):
    fake = FakeSession(FakeResponse(make_payload(today)))
    monkeypatch.setattr(open_meteo.requests, "Session", lambda *a, **k: fake)
    provider = OpenMeteoProvider()  # 内部走 requests.Session()
    record = provider.fetch(today)
    assert record.source == models.SOURCE_OPEN_METEO
    assert len(fake.calls) == 1


# ---------------------------------------------------------------------------
# WMO 码映射
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "code, expected",
    [
        (0, models.SUNNY),
        (2, models.CLOUDY),
        (3, models.OVERCAST),
        (45, models.FOG),
        (48, models.FOG),
        (51, models.DRIZZLE),
        (61, models.RAIN),
        (80, models.RAIN),
        (71, models.SNOW),
        (95, models.THUNDER),
        (999, models.CLOUDY),   # 未知码兜底
        (None, models.CLOUDY),  # 非数值兜底
    ],
)
def test_map_wmo_code(code, expected):
    assert open_meteo.map_wmo_code(code) == expected


def test_map_wmo_code_1_mainly_clear_is_sunny():
    """WMO 1 = Mainly clear（大部晴朗），应映射为「晴」而非「多云」。"""
    assert open_meteo.map_wmo_code(1) == models.SUNNY
