"""ui —— PyQt5 界面层。

main_window 负责：日期选择、查询触发、结果展示、单位切换与友好错误提示；
query_runner 负责：查询执行器（后台 QThread / 同步两种实现），把阻塞式
网络请求移出 GUI 主线程（评审报告 H1），并让测试可注入同步执行器保证确定性。

注意：本层是唯一依赖 PyQt5 的层；导入本包会加载 ``PyQt5.QtCore``
（QObject/QThread 无需 QApplication 即可导入），只有 import
``weather_app.ui.main_window``（进而 import PyQt5 控件类）才需要 Qt 可导入；
构造 QWidget 子类实例仍要求已有 QApplication。
"""
from .query_runner import QueryRunner, SyncQueryRunner, ThreadQueryRunner

__all__ = ["QueryRunner", "SyncQueryRunner", "ThreadQueryRunner"]
