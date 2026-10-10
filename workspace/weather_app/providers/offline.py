"""providers.offline —— 离线样例数据源。

特点：
    * 完全离线，不依赖网络/requests；
    * 确定性：同一天永远返回同一结果（基于日期字符串的 SHA-256 稳定哈希）；
    * 用于断网演示与在线失败时的降级兜底。
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime

from ..core.models import (
    ALL_CONDITIONS,
    CLOUDY,
    DRIZZLE,
    FOG,
    OVERCAST,
    RAIN,
    SNOW,
    SOURCE_OFFLINE,
    SUNNY,
    THUNDER,
    WeatherRecord,
)
from .base import WeatherProvider

# 各月的基准气温（摄氏度，粗略模拟上海四季变化）
_MONTH_BASE_TEMP = {
    1: 5, 2: 7, 3: 12, 4: 18, 5: 23, 6: 27,
    7: 31, 8: 31, 9: 27, 10: 21, 11: 14, 12: 8,
}

# 各季节更可能出现的天气状况池（让样例数据更贴近真实季节）
_WINTER_POOL = (SUNNY, CLOUDY, OVERCAST, CLOUDY, SUNNY, FOG, SNOW)
_SPRING_POOL = (SUNNY, SUNNY, CLOUDY, CLOUDY, RAIN, DRIZZLE, OVERCAST)
_SUMMER_POOL = (SUNNY, SUNNY, CLOUDY, RAIN, THUNDER, RAIN, OVERCAST)
_AUTUMN_POOL = (SUNNY, CLOUDY, OVERCAST, RAIN, DRIZZLE, SUNNY, FOG)


def _pool_for_month(month: int) -> tuple:
    """按月份选择天气状况候选池。"""
    if month in (12, 1, 2):
        return _WINTER_POOL
    if month in (3, 4, 5):
        return _SPRING_POOL
    if month in (6, 7, 8):
        return _SUMMER_POOL
    return _AUTUMN_POOL


class OfflineProvider(WeatherProvider):
    """离线样例数据源（确定性、无网络）。"""

    name = "offline"

    def fetch(self, day: date) -> WeatherRecord:
        """基于日期的稳定哈希生成该日的样例天气。"""
        if isinstance(day, datetime):
            day = day.date()
        if not isinstance(day, date):
            raise ValueError("OfflineProvider.fetch 需要一个 datetime.date 表示日期")

        # 用日期字符串的 SHA-256 作为种子，保证同一天结果稳定可复现
        digest = hashlib.sha256(day.isoformat().encode("utf-8")).hexdigest()
        seed = int(digest, 16)

        # 温度：当月基准值上下浮动 -4 ~ +4 度
        base = _MONTH_BASE_TEMP.get(day.month, 20)
        temp_c = base + (seed % 9) - 4

        # 天气状况：按季节池结合种子选取
        pool = _pool_for_month(day.month)
        condition = pool[seed % len(pool)]

        # 湿度 40% ~ 94%
        humidity = 40 + (seed >> 8) % 55

        # 风速 2.0 ~ 31.9 km/h
        wind_kph = round(2 + ((seed >> 16) % 300) / 10.0, 1)

        return WeatherRecord(
            date=day,
            condition=condition,
            temp_c=float(temp_c),
            humidity=float(humidity),
            wind_kph=float(wind_kph),
            source=SOURCE_OFFLINE,
        )


# 供外部（如测试）了解可用状况的便捷导出
AVAILABLE_CONDITIONS = ALL_CONDITIONS
