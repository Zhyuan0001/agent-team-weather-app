"""ui/main_window 冒烟测试（QT_QPA_PLATFORM=offscreen）。

不安装 pytest-qt，手工使用 QApplication 夹具构造窗口并触发交互。
覆盖：构造、查询渲染、单位切换重渲染、异常不崩溃、降级提示、
以及「查询进行中按钮应禁用」的忙碌态问题。
"""
from __future__ import annotations

from datetime import date

import pytest

from weather_app.core import models
from weather_app.core.errors import DateOutOfRangeError, WeatherUnavailableError
from weather_app.core.models import WeatherRecord
from weather_app.ui.main_window import MainWindow


def _record(source=models.SOURCE_OPEN_METEO, temp_c=25.0, condition=models.SUNNY):
    return WeatherRecord(date=date(2023, 7, 15), condition=condition, temp_c=temp_c,
                         humidity=62.0, wind_kph=12.3, source=source)


class FakeService:
    """替身 service：可配置返回记录或抛异常，并记录调用次数。"""

    def __init__(self, record=None, exc=None):
        self.record = record
        self.exc = exc
        self.calls = 0
        self.last_fallback = False

    def get_weather(self, day, use_online=True):
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        return self.record


@pytest.fixture()
def window(qapp):
    w = MainWindow(service=FakeService(_record()))
    yield w
    w.close()


# ---------------------------------------------------------------------------
# 构造冒烟
# ---------------------------------------------------------------------------
def test_window_constructs(window):
    assert window.windowTitle() == "天气查询 - 按日期查看天气"
    assert window.unit_combo.currentData() == "C"
    assert window.online_checkbox.isChecked() is True


def test_default_date_is_today(window):
    from weather_app.core import date_utils

    qd = window.date_edit.date()
    assert date(qd.year(), qd.month(), qd.day()) == date_utils.today()


# ---------------------------------------------------------------------------
# 查询成功渲染
# ---------------------------------------------------------------------------
def test_query_renders_online_record(window):
    window._on_query()
    assert window.temp_value.text() == "25.0 °C"
    assert window.humidity_value.text() == "62%"
    assert window.wind_value.text() == "12.3 km/h"
    assert window.source_value.text() == "在线数据（open-meteo）"
    assert "晴" in window.condition_label.text()


def test_query_button_triggers_render(window):
    window.query_button.click()
    assert window.temp_value.text() != "—"


# ---------------------------------------------------------------------------
# 单位切换：重渲染但不重新请求
# ---------------------------------------------------------------------------
def test_unit_switch_rerenders_without_refetch(window):
    window._on_query()
    assert window.temp_value.text() == "25.0 °C"
    calls_before = window.service.calls

    window.unit_combo.setCurrentIndex(1)  # 切到华氏度，触发 currentIndexChanged

    assert window.temp_value.text() == "77.0 °F"
    assert window.service.calls == calls_before  # 未重新请求


# ---------------------------------------------------------------------------
# 异常不崩溃
# ---------------------------------------------------------------------------
def test_date_out_of_range_shows_message_not_crash(qapp):
    w = MainWindow(service=FakeService(exc=DateOutOfRangeError("out of range")))
    w._on_query()  # 不应抛异常
    assert "超出可查询范围" in w.message_label.text()
    assert w._current_record is None
    w.close()


def test_weather_unavailable_shows_message_not_crash(qapp):
    w = MainWindow(service=FakeService(exc=WeatherUnavailableError("no network")))
    w._on_query()
    assert "不可用" in w.message_label.text()
    w.close()


def test_unexpected_exception_shows_message_not_crash(qapp):
    w = MainWindow(service=FakeService(exc=RuntimeError("unexpected boom")))
    w._on_query()  # 兜底 except 应吸收
    assert "查询失败" in w.message_label.text()
    w.close()


# ---------------------------------------------------------------------------
# 降级提示
# ---------------------------------------------------------------------------
def test_fallback_message_when_online_failed(qapp):
    svc = FakeService(_record(source=models.SOURCE_OFFLINE))
    svc.last_fallback = True
    w = MainWindow(service=svc)
    w.online_checkbox.setChecked(True)
    w._on_query()
    assert "降级" in w.message_label.text()
    assert w.source_value.text() == "离线示例数据"
    w.close()


def test_offline_only_message_when_online_disabled(qapp):
    svc = FakeService(_record(source=models.SOURCE_OFFLINE))
    svc.last_fallback = False
    w = MainWindow(service=svc)
    w.online_checkbox.setChecked(False)
    w._on_query()
    assert "离线" in w.message_label.text()
    w.close()


# ---------------------------------------------------------------------------
# 「今天」按钮
# ---------------------------------------------------------------------------
def test_today_button_resets_date(window):
    from weather_app.core import date_utils

    window.date_edit.setDate(window.date_edit.date().addDays(-30))
    window.today_button.click()
    qd = window.date_edit.date()
    assert date(qd.year(), qd.month(), qd.day()) == date_utils.today()


# ---------------------------------------------------------------------------
# 忙碌态：查询进行中按钮应禁用（防止重复点击/误判卡死）
# ---------------------------------------------------------------------------
def test_query_button_disabled_during_query(qapp):
    class BusyCheckService(FakeService):
        def __init__(self, record):
            super().__init__(record)
            self.window = None
            self.enabled_during_query = None

        def get_weather(self, day, use_online=True):
            self.enabled_during_query = self.window.query_button.isEnabled()
            return super().get_weather(day, use_online)

    svc = BusyCheckService(_record())
    w = MainWindow(service=svc)
    svc.window = w

    w._on_query()

    assert svc.enabled_during_query is False, (
        "查询进行中「查询天气」按钮仍可用，用户可重复点击导致重复请求"
    )
    w.close()
