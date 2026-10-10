"""weather_app —— 「根据选定日期显示天气」的 PyQt5 桌面应用。

分层架构（逻辑与界面解耦，逻辑层零 GUI 依赖以便单元测试）：

    core       纯逻辑：模型 / 日期校验 / 单位换算 / 展示格式化（无 GUI、无网络）
    providers  数据源：base(接口) / offline(离线样例) / open_meteo(在线)
    services   业务服务：组合 provider + 内存缓存 + 在线失败自动降级
    ui         PyQt5 界面：main_window

依赖方向：ui -> services -> providers -> core，core 不依赖任何上层。
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
