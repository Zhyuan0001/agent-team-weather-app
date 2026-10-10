"""providers —— 数据源层。

统一接口 + 可替换实现：
    base        WeatherProvider 抽象基类（接口 fetch(day) -> WeatherRecord）
    offline     离线样例数据（确定性、完全无网络）
    open_meteo  在线数据（open-meteo，免 key）

providers 层可依赖 core，但不得依赖 ui。
"""
