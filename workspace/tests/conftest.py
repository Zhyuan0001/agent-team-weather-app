"""tests.conftest —— 全局测试夹具。

要点：
* 把 workspace 根目录加入 sys.path，使 ``import weather_app`` 可用；
* 在导入 PyQt5 之前设置 ``QT_QPA_PLATFORM=offscreen``，保证无显示环境也能构造窗口；
* 提供会话级 QApplication 夹具（系统未安装 pytest-qt，手工构造）。
"""
from __future__ import annotations

import os
import sys

# 必须在任何 PyQt5 导入之前设置（无 X11/wayland 也能运行）
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# workspace 根目录（本文件的上一级）加入 sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """会话级 QApplication（offscreen）。"""
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
