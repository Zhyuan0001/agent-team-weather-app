"""providers.base —— 数据源抽象接口。

所有数据源（在线/离线/未来的其它源）都实现 ``fetch``，返回统一的
``WeatherRecord``；失败时抛业务异常，由上层 service 决定是否降级。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from ..core.models import WeatherRecord


class WeatherProvider(ABC):
    """天气数据源抽象基类。"""

    #: 数据源名称（子类覆盖），用于日志/来源标记
    name: str = "base"

    @abstractmethod
    def fetch(self, day: date) -> WeatherRecord:
        """获取指定日期的天气记录。

        参数：
            day: 目标日期。

        返回：
            该日期的 ``WeatherRecord``。

        异常：
            DateOutOfRangeError: 日期超出本数据源支持范围。
            WeatherUnavailableError: 数据当前不可用（网络/HTTP/解析失败）。
        """
        raise NotImplementedError
