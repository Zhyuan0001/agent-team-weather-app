"""core/date_utils 单元测试：日期解析严格性、today、可查询范围判定。"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from weather_app.core import date_utils


# ---------------------------------------------------------------------------
# parse_date —— 严格性
# ---------------------------------------------------------------------------
def test_parse_date_accepts_leap_day():
    """闰年 2024-02-29 必须通过。"""
    assert date_utils.parse_date("2024-02-29") == date(2024, 2, 29)


def test_parse_date_accepts_normal_date():
    assert date_utils.parse_date("2023-07-15") == date(2023, 7, 15)


@pytest.mark.parametrize(
    "text",
    [
        "2023-02-30",     # 2 月不存在 30 日
        "2023-02-29",     # 非闰年没有 2 月 29 日
        "2023-13-01",     # 月份越界
        "2023-00-10",     # 月份为 0
        "2023-04-31",     # 4 月只有 30 天
        "2023-1-1",       # 未补零
        "2023-01-1",      # 日未补零
        "2023-1-01",      # 月未补零
        "2023/01/01",     # 分隔符错误
        "01-01-2023",     # 顺序错误
        "abc",
        "",
        "   ",            # 只有空白
    ],
)
def test_parse_date_rejects_invalid_strings(text):
    with pytest.raises(ValueError):
        date_utils.parse_date(text)


@pytest.mark.parametrize("value", [None, 20230101, 20230101.0, True, ["2023-01-01"]])
def test_parse_date_rejects_non_string(value):
    """非字符串类型（None / int / float / list …）必须拒绝。"""
    with pytest.raises(ValueError):
        date_utils.parse_date(value)


def test_parse_date_is_strict_about_padding_no_leniency():
    """严格校验：任何未补零写法都应被拒绝（防止回归为宽松解析）。"""
    for bad in ("2023-1-1", "2023-1-01", "2023-01-1"):
        with pytest.raises(ValueError):
            date_utils.parse_date(bad)


# ---------------------------------------------------------------------------
# today / max_supported_date
# ---------------------------------------------------------------------------
def test_today_returns_date():
    t = date_utils.today()
    assert isinstance(t, date) and not isinstance(t, datetime)


def test_max_supported_date_is_today_plus_window():
    assert date_utils.max_supported_date() == date_utils.today() + timedelta(
        days=date_utils.MAX_FORECAST_DAYS
    )


# ---------------------------------------------------------------------------
# is_supported_range —— 边界
# ---------------------------------------------------------------------------
def test_is_supported_range_lower_boundary():
    assert date_utils.is_supported_range(date_utils.MIN_SUPPORTED_DATE) is True
    assert date_utils.is_supported_range(
        date_utils.MIN_SUPPORTED_DATE - timedelta(days=1)
    ) is False


def test_is_supported_range_upper_boundary():
    assert date_utils.is_supported_range(date_utils.max_supported_date()) is True
    assert date_utils.is_supported_range(
        date_utils.max_supported_date() + timedelta(days=1)
    ) is False


def test_is_supported_range_today_ok():
    assert date_utils.is_supported_range(date_utils.today()) is True


@pytest.mark.parametrize("value", [None, "2023-01-01", 20230101, [date(2023, 1, 1)]])
def test_is_supported_range_rejects_non_date(value):
    assert date_utils.is_supported_range(value) is False


def test_is_supported_range_accepts_datetime():
    assert date_utils.is_supported_range(datetime(2023, 7, 15, 8, 30)) is True
