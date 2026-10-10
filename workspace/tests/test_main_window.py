"""ui/main_window 冒烟测试（QT_QPA_PLATFORM=offscreen）。

不安装 pytest-qt，手工使用 QApplication 夹具构造窗口并触发交互。
覆盖：构造、查询渲染、单位切换重渲染、异常不崩溃、降级提示、
「查询进行中按钮应禁用」的忙碌态问题，以及第 2 轮 H1 修复后的
「异步不阻塞主线程 / 默认线程执行器 / 忙碌防抖」验证。

时序策略（第 2 轮 H1 修复适配）：
* 既有「调用 → 断言」同步风格用例，在构造 `MainWindow` 时注入
  `SyncQueryRunner`，回调与查询在同一调用栈内完成，断言完全确定；
* H1 异步路径用例使用默认 `ThreadQueryRunner`，配合 `qapp.processEvents()`
  轮询 + 超时收敛，不依赖固定 sleep、不引入重型新依赖。
"""
from __future__ import annotations

import time
from datetime import date

import pytest

from weather_app.core import models
from weather_app.core.errors import DateOutOfRangeError, WeatherUnavailableError
from weather_app.core.models import WeatherRecord
from weather_app.ui.main_window import MainWindow
from weather_app.ui.query_runner import SyncQueryRunner, ThreadQueryRunner


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


def _wait_until(qapp, predicate, timeout=3.0, interval=0.01):
    """在 Qt 事件循环中就绪地轮询 predicate，直到为真或超时。

    使用 `processEvents()` 驱动队列信号投递（后台线程结果回到主线程），
    不使用固定 sleep 收敛，避免不确定等待。返回最终是否满足条件。
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(interval)
    qapp.processEvents()
    return bool(predicate())


@pytest.fixture()
def window(qapp):
    # 注入同步执行器：既有断言保持原同步风格、结果确定
    w = MainWindow(service=FakeService(_record()), runner=SyncQueryRunner())
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
    w = MainWindow(service=FakeService(exc=DateOutOfRangeError("out of range")),
                   runner=SyncQueryRunner())
    w._on_query()  # 不应抛异常
    assert "超出可查询范围" in w.message_label.text()
    assert w._current_record is None
    w.close()


def test_weather_unavailable_shows_message_not_crash(qapp):
    w = MainWindow(service=FakeService(exc=WeatherUnavailableError("no network")),
                   runner=SyncQueryRunner())
    w._on_query()
    assert "不可用" in w.message_label.text()
    w.close()


def test_unexpected_exception_shows_message_not_crash(qapp):
    w = MainWindow(service=FakeService(exc=RuntimeError("unexpected boom")),
                   runner=SyncQueryRunner())
    w._on_query()  # 兜底 except 应吸收
    assert "查询失败" in w.message_label.text()
    w.close()


# ---------------------------------------------------------------------------
# 降级提示
# ---------------------------------------------------------------------------
def test_fallback_message_when_online_failed(qapp):
    svc = FakeService(_record(source=models.SOURCE_OFFLINE))
    svc.last_fallback = True
    w = MainWindow(service=svc, runner=SyncQueryRunner())
    w.online_checkbox.setChecked(True)
    w._on_query()
    assert "降级" in w.message_label.text()
    assert w.source_value.text() == "离线示例数据"
    w.close()


def test_offline_only_message_when_online_disabled(qapp):
    svc = FakeService(_record(source=models.SOURCE_OFFLINE))
    svc.last_fallback = False
    w = MainWindow(service=svc, runner=SyncQueryRunner())
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
    w = MainWindow(service=svc, runner=SyncQueryRunner())
    svc.window = w

    w._on_query()

    assert svc.enabled_during_query is False, (
        "查询进行中「查询天气」按钮仍可用，用户可重复点击导致重复请求"
    )
    w.close()


# ===========================================================================
# 第 2 轮 H1 修复验证
# ===========================================================================
def test_default_runner_is_thread_query_runner(qapp):
    """H1：默认执行器必须是后台线程执行器（真实应用不阻塞主线程）。"""
    w = MainWindow(service=FakeService(_record()))
    try:
        assert isinstance(w.runner, ThreadQueryRunner), (
            "MainWindow 默认 runner 不是 ThreadQueryRunner，网络请求仍会阻塞 GUI 主线程"
        )
    finally:
        w.close()


def test_query_does_not_block_main_thread(qapp):
    """H1：耗时的 service 在后台线程执行，_on_query() 立即返回、界面不冻结。

    假 service 睡眠约 250ms 模拟阻塞式网络请求：
    * `_on_query()` 必须在远早于睡眠结束前返回（主线程未被阻塞）；
    * 返回瞬间界面已进入忙碌态（按钮禁用 + 「查询中…」）、结果尚未到达；
    * 随后经事件循环等待后台结果投递回主线程，断言渲染完成、按钮恢复。
    """
    sleep_seconds = 0.25

    class SlowService(FakeService):
        def get_weather(self, day, use_online=True):
            self.calls += 1
            time.sleep(sleep_seconds)  # 模拟阻塞式网络请求
            return self.record

    svc = SlowService(_record())
    w = MainWindow(service=svc)  # 使用默认 ThreadQueryRunner（真实异步路径）
    try:
        assert isinstance(w.runner, ThreadQueryRunner)

        start = time.monotonic()
        w._on_query()
        elapsed = time.monotonic() - start

        # 主线程未被阻塞：立即返回，耗时远小于后台睡眠时长
        assert elapsed < sleep_seconds * 0.8, (
            f"_on_query 阻塞了主线程 {elapsed:.3f}s（假 service 睡眠 {sleep_seconds}s）"
        )
        # 返回瞬间即处于忙碌态，且结果尚未渲染
        assert w.query_button.isEnabled() is False
        assert w.query_button.text() == "查询中…"
        assert w.temp_value.text() == "—"

        # 事件循环等待后台结果回到主线程（线程收尾后 _thread 置空）
        arrived = _wait_until(
            qapp, lambda: w.runner._thread is None and w.temp_value.text() != "—"
        )
        assert arrived, "后台查询结果未在超时前投递回主线程"

        assert w.temp_value.text() == "25.0 °C"
        assert w.humidity_value.text() == "62%"
        assert w.query_button.isEnabled() is True
        assert w.query_button.text() == "查询天气"
        assert svc.calls == 1
    finally:
        _wait_until(qapp, lambda: w.runner._thread is None)
        w.close()


def test_second_query_ignored_while_busy(qapp):
    """H1：查询在途时再次触发 _on_query() 不得发起第二次查询（忙碌防抖）。

    用计数执行器包装 ThreadQueryRunner，直接断言 `runner.run` 只被调用一次，
    从而验证是 MainWindow 的忙碌守卫（而非仅执行器内部兜底）拦下了重复请求。
    """
    class SlowService(FakeService):
        def get_weather(self, day, use_online=True):
            self.calls += 1
            time.sleep(0.25)
            return self.record

    class CountingRunner(ThreadQueryRunner):
        def __init__(self):
            super().__init__()
            self.run_calls = 0

        def run(self, *args, **kwargs):
            self.run_calls += 1
            return super().run(*args, **kwargs)

    svc = SlowService(_record())
    runner = CountingRunner()
    w = MainWindow(service=svc, runner=runner)
    try:
        w._on_query()  # 首次查询（后台睡眠 0.25s，仍在途）
        # 在途期间连续再次触发：应被忙碌守卫直接忽略
        w._on_query()
        w._on_query()

        # 忙碌守卫在 `_on_query` 内同步生效：三次触发只应进入执行器一次
        # （run_calls 在调用栈内同步自增，与后台线程调度无关，判定确定）
        assert runner.run_calls == 1, "忙碌期间发起了第二次查询执行"
        assert w.query_button.isEnabled() is False

        arrived = _wait_until(
            qapp, lambda: w.runner._thread is None and w.temp_value.text() != "—"
        )
        assert arrived, "首次查询结果未在超时前投递回主线程"
        assert w.temp_value.text() == "25.0 °C"
        assert w.query_button.isEnabled() is True
        # 首次查询完成后核对：执行器与 service 全程均只被调用一次
        assert runner.run_calls == 1
        assert svc.calls == 1, "被忽略的重复触发仍到达了 service"
    finally:
        _wait_until(qapp, lambda: w.runner._thread is None)
        w.close()
