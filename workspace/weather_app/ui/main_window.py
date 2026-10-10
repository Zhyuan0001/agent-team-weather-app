"""ui.main_window —— PyQt5 主窗口。

界面元素：
    * 日期选择控件（默认今天）
    * 「今天」快捷按钮
    * 「优先使用在线数据」开关（关闭则强制走离线样例，便于断网演示）
    * 温度单位切换（摄氏度 / 华氏度，默认摄氏度）
    * 「查询天气」按钮
    * 结果区：天气状况（文字 + emoji）、温度、湿度、风速、数据来源
    * 状态栏 + 内联提示：错误与「离线示例数据」提示均为友好文案，绝不弹崩溃
"""
from __future__ import annotations

from datetime import date

from PyQt5.QtCore import QDate, Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core import date_utils
from ..core.errors import DateOutOfRangeError, WeatherUnavailableError
from ..core.formatting import render_record
from ..core.models import SOURCE_OFFLINE
from ..core.units import UNIT_CELSIUS, UNIT_FAHRENHEIT
from ..services.weather_service import WeatherService

# 日期控件允许的粗略范围（越界会被服务层/界面友好拦截）
_MIN_QDATE = QDate(1940, 1, 1)
_MAX_QDATE = QDate(2100, 12, 31)

# 未查询时的占位文案
_PLACEHOLDER = "—"


class MainWindow(QMainWindow):
    """天气查询主窗口。"""

    def __init__(self, service: WeatherService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # 允许注入 service，便于替换数据源或测试
        self.service = service if service is not None else WeatherService()
        # 保存最近一次查询结果，供单位切换时重渲染
        self._current_record = None
        self._build_ui()
        self.statusBar().showMessage("请选择日期后点击「查询天气」。")

    # ------------------------------------------------------------------
    # 构建界面
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle("天气查询 - 按日期查看天气")
        self.resize(460, 520)

        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        # 标题
        title = QLabel("天气查询")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        root.addWidget(title)

        # ---- 控制区 ----------------------------------------------------
        controls = QGroupBox("查询条件")
        controls_layout = QGridLayout(controls)
        controls_layout.setHorizontalSpacing(10)
        controls_layout.setVerticalSpacing(10)

        # 日期选择（默认今天）
        controls_layout.addWidget(QLabel("选择日期："), 0, 0)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setMinimumDate(_MIN_QDATE)
        self.date_edit.setMaximumDate(_MAX_QDATE)
        self.date_edit.setDate(self._today_qdate())
        controls_layout.addWidget(self.date_edit, 0, 1)

        # 「今天」快捷按钮
        self.today_button = QPushButton("今天")
        self.today_button.clicked.connect(self._on_today_clicked)
        controls_layout.addWidget(self.today_button, 0, 2)

        # 温度单位切换（默认摄氏度）
        controls_layout.addWidget(QLabel("温度单位："), 1, 0)
        self.unit_combo = QComboBox()
        self.unit_combo.addItem("摄氏度 (°C)", UNIT_CELSIUS)
        self.unit_combo.addItem("华氏度 (°F)", UNIT_FAHRENHEIT)
        self.unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        controls_layout.addWidget(self.unit_combo, 1, 1)

        # 在线数据开关（默认开启）
        self.online_checkbox = QCheckBox("优先使用在线数据 (open-meteo)")
        self.online_checkbox.setChecked(True)
        controls_layout.addWidget(self.online_checkbox, 2, 0, 1, 3)

        root.addWidget(controls)

        # 查询按钮
        self.query_button = QPushButton("查询天气")
        self.query_button.setStyleSheet("font-size: 15px; padding: 8px;")
        self.query_button.clicked.connect(self._on_query)
        root.addWidget(self.query_button)

        # ---- 结果区 ----------------------------------------------------
        result_box = QGroupBox("查询结果")
        result_layout = QVBoxLayout(result_box)

        # 大号 emoji 与状况文字
        self.emoji_label = QLabel(_PLACEHOLDER)
        self.emoji_label.setAlignment(Qt.AlignCenter)
        self.emoji_label.setStyleSheet("font-size: 48px;")
        result_layout.addWidget(self.emoji_label)

        self.condition_label = QLabel("尚未查询")
        self.condition_label.setAlignment(Qt.AlignCenter)
        self.condition_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        result_layout.addWidget(self.condition_label)

        # 明细字段
        form = QFormLayout()
        self.date_value = QLabel(_PLACEHOLDER)
        self.temp_value = QLabel(_PLACEHOLDER)
        self.humidity_value = QLabel(_PLACEHOLDER)
        self.wind_value = QLabel(_PLACEHOLDER)
        self.source_value = QLabel(_PLACEHOLDER)
        form.addRow("日期：", self.date_value)
        form.addRow("温度：", self.temp_value)
        form.addRow("湿度：", self.humidity_value)
        form.addRow("风速：", self.wind_value)
        form.addRow("数据来源：", self.source_value)
        result_layout.addLayout(form)

        root.addWidget(result_box)

        # 内联提示（错误 / 离线提示），始终存在但不弹窗，避免阻塞
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet("color: #b00020;")
        root.addWidget(self.message_label)

        root.addStretch(1)

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------
    def _on_today_clicked(self) -> None:
        """把日期控件重置为今天。"""
        self.date_edit.setDate(self._today_qdate())

    def _on_unit_changed(self) -> None:
        """单位切换：若有已查询结果，直接用新单位重渲染，无需重新请求。"""
        if self._current_record is not None:
            self._render(self._current_record)

    def _on_query(self) -> None:
        """查询按钮：读取界面输入并调用服务层。"""
        qdate = self.date_edit.date()
        day = date(qdate.year(), qdate.month(), qdate.day())
        use_online = self.online_checkbox.isChecked()

        # 进入忙碌态：禁用查询按钮并给出提示，避免阻塞期间被重复点击/误判卡死
        self._set_querying(True)
        try:
            try:
                record = self.service.get_weather(day, use_online=use_online)
            except DateOutOfRangeError:
                self._show_message(
                    "所选日期超出可查询范围（支持 1940-01-01 至未来 16 天），请重新选择。"
                )
                return
            except WeatherUnavailableError as exc:
                self._show_message(f"天气数据暂时不可用：{exc}")
                return
            except Exception as exc:  # 兜底：任何异常都转为友好提示，绝不让程序崩溃
                self._show_message(f"查询失败：{exc}")
                return

            # 记录并渲染
            self._current_record = record
            self._render(record)

            # 依据实际来源与降级情况给出状态提示
            if record.source == SOURCE_OFFLINE and use_online and self.service.last_fallback:
                self.message_label.setText("已自动降级：当前展示「离线示例数据」。")
                self.statusBar().showMessage("在线查询失败，已降级为离线示例数据。", 8000)
            elif record.source == SOURCE_OFFLINE:
                self.message_label.setText("当前展示「离线示例数据」（未启用在线数据）。")
                self.statusBar().showMessage("已获取离线示例数据。", 5000)
            else:
                self.message_label.setText("")
                self.statusBar().showMessage("已获取在线天气数据。", 5000)
        finally:
            # 无论成功、降级还是异常，都恢复按钮可用状态
            self._set_querying(False)

    def _set_querying(self, busy: bool) -> None:
        """切换查询忙碌态：禁用/恢复查询按钮并更新按钮文案与状态提示。"""
        self.query_button.setEnabled(not busy)
        self.query_button.setText("查询中…" if busy else "查询天气")

    # ------------------------------------------------------------------
    # 渲染与提示
    # ------------------------------------------------------------------
    def _render(self, record) -> None:
        """把天气记录渲染到结果区（按当前选择的单位）。"""
        unit = self.unit_combo.currentData()
        view = render_record(record, unit)

        self.emoji_label.setText(view["condition_emoji"])
        self.condition_label.setText(f"{view['condition_label']} {view['condition_emoji']}")
        self.date_value.setText(view["date"])
        self.temp_value.setText(view["temperature"])
        self.humidity_value.setText(view["humidity"])
        self.wind_value.setText(view["wind"])
        self.source_value.setText(view["source_label"])

    def _show_message(self, text: str) -> None:
        """显示错误提示（内联 + 状态栏），不弹出模态框，避免阻塞/崩溃。"""
        self.message_label.setText(text)
        self.statusBar().showMessage(text, 8000)

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    @staticmethod
    def _today_qdate() -> QDate:
        """返回表示「今天」的 QDate。"""
        t = date_utils.today()
        return QDate(t.year, t.month, t.day)
