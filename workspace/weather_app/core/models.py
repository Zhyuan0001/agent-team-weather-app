"""core.models —— 天气记录数据结构与天气状况常量。

provider 无论来自在线还是离线，都必须返回统一的 ``WeatherRecord``，
从而让 service 与 ui 层与具体数据源解耦，也便于测试时构造/mock。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# ---------------------------------------------------------------------------
# 天气状况常量集合（provider 与界面统一使用这些字符串标识）
# ---------------------------------------------------------------------------
SUNNY = "sunny"          # 晴
CLOUDY = "cloudy"        # 多云
OVERCAST = "overcast"    # 阴
RAIN = "rain"            # 雨
SNOW = "snow"            # 雪
FOG = "fog"              # 雾
DRIZZLE = "drizzle"      # 小雨/毛毛雨
THUNDER = "thunder"      # 雷阵雨

# 全部合法天气状况，供遍历/校验使用
ALL_CONDITIONS = (SUNNY, CLOUDY, OVERCAST, RAIN, SNOW, FOG, DRIZZLE, THUNDER)

# ---------------------------------------------------------------------------
# 数据来源标识（用于界面展示「在线」还是「离线示例」）
# ---------------------------------------------------------------------------
SOURCE_OPEN_METEO = "open-meteo"   # 在线：open-meteo 免 key 接口
SOURCE_OFFLINE = "offline"         # 离线：内置样例数据


@dataclass
class WeatherRecord:
    """某一天的天气记录（与数据源无关的统一数据结构）。

    属性：
        date:      日期（datetime.date）
        condition: 天气状况，取值见上方常量集合
        temp_c:    摄氏温度（内部一律以摄氏度存储）
        humidity:  相对湿度（百分比数值，如 62 表示 62%）
        wind_kph:  风速（公里/小时）
        source:    数据来源标识
    """

    date: date
    condition: str
    temp_c: float
    humidity: float
    wind_kph: float
    source: str = SOURCE_OFFLINE
