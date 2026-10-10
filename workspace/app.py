"""app.py —— 桌面应用入口。

职责：创建 QApplication 与主窗口、显示界面并进入事件循环。
运行方式（在 workspace/ 目录下）：

    python3 app.py

逻辑层（core/providers/services）均不依赖 PyQt5，本文件是唯一负责启动 GUI 的入口。
"""
import sys

from PyQt5.QtWidgets import QApplication

from weather_app.ui.main_window import MainWindow


def main() -> int:
    """创建应用、显示主窗口并进入事件循环。"""
    app = QApplication(sys.argv)
    app.setApplicationName("天气查询")
    app.setApplicationDisplayName("天气查询")

    window = MainWindow()
    window.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
