"""ui —— PyQt5 界面层。

main_window 负责：日期选择、查询触发、结果展示、单位切换与友好错误提示。

注意：本层是唯一依赖 PyQt5 的层；导入本包不要求已创建 QApplication，
只有 import ``weather_app.ui.main_window``（进而 import PyQt5 控件类）才需要 Qt 可导入。
"""
