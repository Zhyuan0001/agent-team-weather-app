"""ui.query_runner —— 把天气查询移出 GUI 主线程的执行器（评审报告 H1 修复）。

背景：
    ``WeatherService.get_weather`` 内部是阻塞式网络请求（超时最长约 8 秒），
    此前由 ``MainWindow._on_query`` 在 GUI 主线程直接调用，无网/弱网时点击
    查询会冻结界面至多 8 秒。本模块把「同步的 service 调用」与「界面回调」
    解耦，提供两种可选执行方式：

    * :class:`SyncQueryRunner`   —— 当前线程同步执行并立即回调；供测试注入，
      结果完全确定（不引入不确定的异步等待）；
    * :class:`ThreadQueryRunner` —— 在后台 ``QThread`` 中执行，完成后经 Qt
      信号把结果/异常投递回主线程再回调；真实应用使用，界面不阻塞。

统一接口::

    runner.run(service, day, use_online, on_success, on_error) -> None

    * ``on_success(record, last_fallback: bool)`` —— 成功；``last_fallback``
      为该次查询在 service 上的降级标记快照（随结果一并回传，不在回调时
      再读共享状态）；
    * ``on_error(exc: Exception)`` —— 失败；任何异常都经此上报。

架构约束：本模块位于 ui 层（唯一允许依赖 PyQt5 的层）；services/providers/core
不感知执行器的存在，``WeatherService`` 保持同步、对外行为不变。
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from ..services.weather_service import WeatherService

#: 成功回调：on_success(record, last_fallback)
OnSuccess = Callable[[Any, bool], None]
#: 失败回调：on_error(exc)
OnError = Callable[[Exception], None]


class QueryRunner:
    """查询执行器抽象：只约定一次查询的调用方式与回调语义。

    子类实现 :meth:`run`；对调用方（MainWindow）而言两种实现行为一致，
    区别只在「何时、在哪个线程执行 service.get_weather」。
    """

    def run(
        self,
        service: WeatherService,
        day: date,
        use_online: bool,
        on_success: OnSuccess,
        on_error: OnError,
    ) -> None:
        """执行一次天气查询（子类必须覆写）。

        参数：
            service:    天气服务，需提供同步的 ``get_weather`` 与 ``last_fallback``。
            day:        目标日期。
            use_online: 是否优先使用在线数据。
            on_success: 成功回调 ``on_success(record, last_fallback)``。
            on_error:   失败回调 ``on_error(exc)``。
        """
        raise NotImplementedError("QueryRunner 为抽象执行器，请使用 SyncQueryRunner / ThreadQueryRunner")


class SyncQueryRunner(QueryRunner):
    """同步执行器：当场执行 ``service.get_weather`` 并立即回调。

    专供测试注入：回调与查询在同一调用栈内完成，断言无需等待事件循环，
    结果完全确定；成功/失败的回调口径与 :class:`ThreadQueryRunner` 一致。
    """

    def run(
        self,
        service: WeatherService,
        day: date,
        use_online: bool,
        on_success: OnSuccess,
        on_error: OnError,
    ) -> None:
        try:
            record = service.get_weather(day, use_online=use_online)
            # 与异步执行器对齐：立即读取降级标记快照并随结果一并回传
            last_fallback = bool(getattr(service, "last_fallback", False))
        except Exception as exc:  # 兜底：任何异常统一交给 on_error，绝不上抛打断界面
            on_error(exc)
            return
        on_success(record, last_fallback)


class _WeatherWorker(QThread):
    """后台工作线程：调用同步的 ``service.get_weather``，把结果/异常经信号发回。

    信号在后台线程中 emit；接收方（:class:`ThreadQueryRunner`）位于主线程，
    Qt 的自动连接（AutoConnection）会把投递转为队列连接，从而保证界面
    回调一定在主线程执行。
    """

    #: 查询成功：参数为 (WeatherRecord, last_fallback 快照)
    succeeded = pyqtSignal(object, bool)
    #: 查询失败：参数为捕获到的异常对象
    failed = pyqtSignal(object)

    def __init__(self, service: WeatherService, day: date, use_online: bool) -> None:
        super().__init__()
        self._service = service
        self._day = day
        self._use_online = use_online

    def run(self) -> None:
        """线程入口：执行查询并把结果/异常通过信号发回主线程。"""
        try:
            record = self._service.get_weather(self._day, use_online=self._use_online)
            # 在后台线程内立即快照降级标记，避免结果回调时再读 service 共享状态
            last_fallback = bool(getattr(self._service, "last_fallback", False))
        except Exception as exc:  # 兜底：异常转为信号上报，绝不让线程带异常退出
            self.failed.emit(exc)
            return
        self.succeeded.emit(record, last_fallback)


class ThreadQueryRunner(QObject, QueryRunner):
    """异步执行器：后台 QThread 执行查询，回调经 Qt 信号回到主线程。

    实现要点：
        * 每次查询创建一个一次性的 :class:`_WeatherWorker`；线程结束后在
          ``finished`` 槽中 ``wait()`` + ``deleteLater()``，确保线程完全退出
          后才释放（避免 QThread 运行中被析构）；
        * ``succeeded`` / ``failed`` 发射于后台线程、接收者位于主线程，自动
          连接判定为队列连接 —— 回调必然在主线程执行，界面操作安全；
        * 通过 ``self._thread.isRunning()`` 检查避免并发重复启动：同一时刻
          最多一个在途查询（界面忙碌态是第一道防线，这里是第二道兜底）；
        * 回调在触发前先取出并清空，避免结果重复投递或旧回调残留。
    """

    def __init__(self, parent: QObject | None = None) -> None:
        QObject.__init__(self, parent)
        self._thread: _WeatherWorker | None = None
        self._on_success: OnSuccess | None = None
        self._on_error: OnError | None = None

    # ------------------------------------------------------------------
    # QueryRunner 接口
    # ------------------------------------------------------------------
    def run(
        self,
        service: WeatherService,
        day: date,
        use_online: bool,
        on_success: OnSuccess,
        on_error: OnError,
    ) -> None:
        """在后台线程执行一次查询；已有查询在途时忽略本次请求。"""
        # 并发保护：上一轮线程尚未运行结束时直接忽略，避免回调错乱
        if self._thread is not None and self._thread.isRunning():
            return

        self._on_success = on_success
        self._on_error = on_error

        worker = _WeatherWorker(service, day, use_online)
        # 跨线程信号 -> 本对象（主线程）槽：自动连接会转为队列投递
        worker.succeeded.connect(self._handle_success)
        worker.failed.connect(self._handle_failure)
        worker.finished.connect(self._handle_thread_finished)
        self._thread = worker
        worker.start()

    # ------------------------------------------------------------------
    # 内部槽（均在主线程被调用）
    # ------------------------------------------------------------------
    def _handle_success(self, record: Any, last_fallback: bool) -> None:
        """成功槽：取出并清空回调后转交界面处理。"""
        on_success, self._on_success = self._on_success, None
        self._on_error = None
        if on_success is not None:
            on_success(record, last_fallback)

    def _handle_failure(self, exc: Exception) -> None:
        """失败槽：取出并清空回调后转交界面处理。"""
        on_error, self._on_error = self._on_error, None
        self._on_success = None
        if on_error is not None:
            on_error(exc)

    def _handle_thread_finished(self) -> None:
        """线程结束收尾：等待完全退出、延迟释放，并清理引用以便下次查询。"""
        worker = self.sender()
        if worker is None:  # 直接调用（无信号上下文）时回退到当前线程引用
            worker = self._thread
        if not isinstance(worker, _WeatherWorker):
            return
        worker.wait()          # finished 已发出，此处即刻返回，确保线程已完全退出
        worker.deleteLater()   # 线程结束后再交给事件循环安全析构
        if self._thread is worker:
            self._thread = None
