"""core.formatting —— 展示层格式化。

把内部数据（天气状况常量、WeatherRecord）渲染成界面可直接使用的展示字段：
    天气状况 -> 中文名 + emoji
    来源标识 -> 中文说明
    WeatherRecord -> 展示字段字典
"""
from __future__ import annotations

from . import models
from .units import UNIT_CELSIUS, format_temperature

# 天气状况 -> 中文名
_CONDITION_LABELS = {
    models.SUNNY: "晴",
    models.CLOUDY: "多云",
    models.OVERCAST: "阴",
    models.RAIN: "雨",
    models.SNOW: "雪",
    models.FOG: "雾",
    models.DRIZZLE: "小雨",
    models.THUNDER: "雷阵雨",
}

# 天气状况 -> emoji 图标
_CONDITION_EMOJIS = {
    models.SUNNY: "☀️",
    models.CLOUDY: "⛅",
    models.OVERCAST: "☁️",
    models.RAIN: "🌧️",
    models.SNOW: "❄️",
    models.FOG: "🌫️",
    models.DRIZZLE: "🌦️",
    models.THUNDER: "⛈️",
}

# 数据来源 -> 中文说明
_SOURCE_LABELS = {
    models.SOURCE_OPEN_METEO: "在线数据（open-meteo）",
    models.SOURCE_OFFLINE: "离线示例数据",
}

# 未知取值时的兜底文案
_UNKNOWN_LABEL = "未知"
_UNKNOWN_EMOJI = "❓"


def condition_label(condition: str) -> str:
    """天气状况 -> 中文名（未知取值回退为「未知」）。"""
    return _CONDITION_LABELS.get(condition, _UNKNOWN_LABEL)


def condition_emoji(condition: str) -> str:
    """天气状况 -> emoji（未知取值回退为问号）。"""
    return _CONDITION_EMOJIS.get(condition, _UNKNOWN_EMOJI)


def source_label(source: str) -> str:
    """数据来源标识 -> 中文说明。"""
    if source in _SOURCE_LABELS:
        return _SOURCE_LABELS[source]
    return source or _UNKNOWN_LABEL


def render_record(record: models.WeatherRecord, unit: str = UNIT_CELSIUS) -> dict:
    """把 WeatherRecord 渲染成展示用字段字典，供界面直接绑定。"""
    return {
        "date": record.date.isoformat(),
        "condition": record.condition,
        "condition_label": condition_label(record.condition),
        "condition_emoji": condition_emoji(record.condition),
        "temperature": format_temperature(record.temp_c, unit),
        "humidity": f"{record.humidity:.0f}%",
        "wind": f"{record.wind_kph:.1f} km/h",
        "source": record.source,
        "source_label": source_label(record.source),
    }
