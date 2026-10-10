"""core.errors —— 自定义异常类型。

对外只暴露「日期超范围」与「天气数据不可用」两类业务异常，
使界面层可以用统一方式做友好提示，而不必区分底层具体错误（网络/HTTP/解析等）。
"""


class WeatherError(Exception):
    """本应用所有业务异常的基类，便于上层统一捕获。"""


class DateOutOfRangeError(WeatherError):
    """所选日期超出了数据源可提供的范围。

    例如：早于历史归档起点，或超出未来预报窗口。
    """


class WeatherUnavailableError(WeatherError):
    """天气数据当前不可用。

    覆盖网络异常、HTTP 非 200、响应无法解析等一切「取不到数据」的情况。
    """
