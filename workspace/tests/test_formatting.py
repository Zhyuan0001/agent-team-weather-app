"""core/formatting 单元测试：状况 -> 中文名/emoji 映射（含未知状况兜底）。"""
from __future__ import annotations

from datetime import date

import pytest

from weather_app.core import formatting, models


ALL_CONDITIONS = (
    models.SUNNY,
    models.CLOUDY,
    models.OVERCAST,
    models.RAIN,
    models.SNOW,
    models.FOG,
    models.DRIZZLE,
    models.THUNDER,
)


@pytest.mark.parametrize("condition", ALL_CONDITIONS)
def test_condition_label_is_chinese_and_not_unknown(condition):
    label = formatting.condition_label(condition)
    assert label != formatting._UNKNOWN_LABEL
    assert isinstance(label, str) and label != ""


@pytest.mark.parametrize("condition", ALL_CONDITIONS)
def test_condition_emoji_present(condition):
    emoji = formatting.condition_emoji(condition)
    assert emoji != formatting._UNKNOWN_EMOJI


def test_condition_labels_specific_values():
    assert formatting.condition_label(models.SUNNY) == "晴"
    assert formatting.condition_label(models.CLOUDY) == "多云"
    assert formatting.condition_label(models.RAIN) == "雨"
    assert formatting.condition_label(models.SNOW) == "雪"
    assert formatting.condition_label(models.THUNDER) == "雷阵雨"


# ---------------------------------------------------------------------------
# 未知状况的兜底行为
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("unknown", ["", "typhoon", "SUNNY", None, 0])
def test_condition_label_unknown_fallback(unknown):
    assert formatting.condition_label(unknown) == "未知"


@pytest.mark.parametrize("unknown", ["", "typhoon", None])
def test_condition_emoji_unknown_fallback(unknown):
    assert formatting.condition_emoji(unknown) == "❓"


# ---------------------------------------------------------------------------
# source_label
# ---------------------------------------------------------------------------
def test_source_label_known():
    assert formatting.source_label(models.SOURCE_OPEN_METEO) == "在线数据（open-meteo）"
    assert formatting.source_label(models.SOURCE_OFFLINE) == "离线示例数据"


def test_source_label_unknown_returns_input_then_fallback():
    assert formatting.source_label("custom-source") == "custom-source"
    assert formatting.source_label("") == "未知"


# ---------------------------------------------------------------------------
# render_record
# ---------------------------------------------------------------------------
def _record(**kw):
    base = dict(
        date=date(2023, 7, 15),
        condition=models.RAIN,
        temp_c=23.44,
        humidity=62.0,
        wind_kph=12.34,
        source=models.SOURCE_OPEN_METEO,
    )
    base.update(kw)
    return models.WeatherRecord(**base)


def test_render_record_celsius():
    view = formatting.render_record(_record())
    assert view["date"] == "2023-07-15"
    assert view["condition"] == models.RAIN
    assert view["condition_label"] == "雨"
    assert view["condition_emoji"] == "🌧️"
    assert view["temperature"] == "23.4 °C"
    assert view["humidity"] == "62%"
    assert view["wind"] == "12.3 km/h"
    assert view["source_label"] == "在线数据（open-meteo）"


def test_render_record_fahrenheit():
    view = formatting.render_record(_record(temp_c=0.0), unit="F")
    assert view["temperature"] == "32.0 °F"


def test_render_record_offline_source():
    view = formatting.render_record(_record(source=models.SOURCE_OFFLINE))
    assert view["source_label"] == "离线示例数据"


def test_render_record_unknown_condition_fallback():
    view = formatting.render_record(_record(condition="weird"))
    assert view["condition_label"] == "未知"
    assert view["condition_emoji"] == "❓"
