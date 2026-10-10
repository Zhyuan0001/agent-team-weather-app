"""providers/offline 单元测试：确定性与字段合法范围。"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from weather_app.core import models
from weather_app.providers.offline import OfflineProvider


@pytest.fixture()
def provider():
    return OfflineProvider()


# ---------------------------------------------------------------------------
# 确定性
# ---------------------------------------------------------------------------
def test_same_day_returns_identical_record(provider):
    day = date(2023, 7, 15)
    first = provider.fetch(day)
    second = provider.fetch(day)
    assert first == second


def test_determinism_over_many_repeats(provider):
    day = date(2024, 2, 29)
    records = [provider.fetch(day) for _ in range(20)]
    assert all(r == records[0] for r in records)


def test_datetime_is_normalised_to_date(provider):
    r = provider.fetch(datetime(2023, 7, 15, 23, 59))
    assert r.date == date(2023, 7, 15)


def test_non_date_raises_value_error(provider):
    with pytest.raises(ValueError):
        provider.fetch("2023-07-15")


# ---------------------------------------------------------------------------
# 字段合法性（遍历一年，逐日校验）
# ---------------------------------------------------------------------------
def test_field_ranges_over_full_year(provider):
    start = date(2024, 1, 1)
    for offset in range(366):
        day = start + timedelta(days=offset)
        r = provider.fetch(day)
        assert isinstance(r.date, date) and r.date == day
        assert r.condition in models.ALL_CONDITIONS, f"{day} 状况非法：{r.condition}"
        assert 0 <= r.humidity <= 100, f"{day} 湿度越界：{r.humidity}"
        assert r.wind_kph >= 0, f"{day} 风速为负：{r.wind_kph}"
        assert r.source == models.SOURCE_OFFLINE
        assert isinstance(r.temp_c, float)


def test_temperature_within_expected_month_band(provider):
    """温度应落在「当月基准 ±4℃」的构造区间内。"""
    from weather_app.providers.offline import _MONTH_BASE_TEMP

    for month in range(1, 13):
        base = _MONTH_BASE_TEMP[month]
        for d in (1, 15, 28):
            r = provider.fetch(date(2023, month, d))
            assert base - 4 <= r.temp_c <= base + 4
