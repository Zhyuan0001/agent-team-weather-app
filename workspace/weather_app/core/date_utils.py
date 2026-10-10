"""core.date_utils —— 日期解析与范围校验（日期处理的唯一来源）。

集中处理日期字符串解析与可查询范围判定，避免各处重复实现导致行为不一致。
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

# 严格日期格式：必须是补零的 YYYY-MM-DD
DATE_FORMAT = "%Y-%m-%d"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 未来预报窗口：open-meteo 预报接口最多支持未来 16 天
MAX_FORECAST_DAYS = 16
# 历史归档起点：open-meteo 归档接口自 1940 年起提供数据
MIN_SUPPORTED_DATE = date(1940, 1, 1)


def today() -> date:
    """返回「今天」的日期。单独封装便于测试替换与统一调用点。"""
    return date.today()


def max_supported_date() -> date:
    """返回可查询的最晚日期（今天 + 预报窗口）。"""
    return today() + timedelta(days=MAX_FORECAST_DAYS)


def parse_date(text: str) -> date:
    """把字符串解析为 ``datetime.date``。

    严格校验：必须是补零的 ``YYYY-MM-DD``，且必须是真实存在的日期。
    非法输入一律抛出 ``ValueError``。
    """
    if not isinstance(text, str):
        raise ValueError("日期必须是字符串，格式为 YYYY-MM-DD")

    stripped = text.strip()
    if not _DATE_RE.match(stripped):
        raise ValueError(f"日期格式非法：{text!r}，应为补零的 YYYY-MM-DD")
    try:
        # strptime 已能识别「2023-02-30」这类不存在的日期并抛错
        return datetime.strptime(stripped, DATE_FORMAT).date()
    except ValueError as exc:
        raise ValueError(f"日期不存在：{text!r}") from exc


def is_supported_range(day: date) -> bool:
    """判断日期是否落在数据源可提供的范围内。

    范围 = [MIN_SUPPORTED_DATE, 今天 + MAX_FORECAST_DAYS]。
    非日期类型返回 False。
    """
    if isinstance(day, datetime):
        day = day.date()
    elif not isinstance(day, date):
        return False
    return MIN_SUPPORTED_DATE <= day <= max_supported_date()
