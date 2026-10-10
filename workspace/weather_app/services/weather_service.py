"""services.weather_service —— 天气业务服务。

职责：
    * 组合在线 provider（open-meteo）与离线 provider（样例数据）；
    * 在线查询失败/无网时自动降级到离线，并在结果中保留来源标记；
    * 提供简单的内存缓存，避免同一日期重复请求。

降级策略：
    * DateOutOfRangeError 属于「用户选了不可查询的日期」，直接向上抛出，由界面提示；
    * WeatherUnavailableError 属于「数据暂时取不到」，此时降级为离线样例数据。
"""
from __future__ import annotations

from datetime import date, datetime

from ..core.errors import DateOutOfRangeError, WeatherUnavailableError
from ..core.models import WeatherRecord
from ..providers.base import WeatherProvider
from ..providers.offline import OfflineProvider
from ..providers.open_meteo import OpenMeteoProvider


class WeatherService:
    """天气查询服务：在线优先 + 失败降级 + 内存缓存。"""

    def __init__(
        self,
        online_provider: WeatherProvider | None = None,
        offline_provider: WeatherProvider | None = None,
    ) -> None:
        # 允许注入 provider，便于测试替换为假实现
        self._online = online_provider if online_provider is not None else OpenMeteoProvider()
        self._offline = offline_provider if offline_provider is not None else OfflineProvider()
        # 缓存：键为 (来源类别, 日期)，值为 WeatherRecord
        self._cache: dict[tuple[str, date], WeatherRecord] = {}
        #: 记录最近一次查询是否发生了「降级」
        self.last_fallback: bool = False

    def clear_cache(self) -> None:
        """清空内存缓存。"""
        self._cache.clear()

    def get_weather(self, day: date, use_online: bool = True) -> WeatherRecord:
        """获取指定日期的天气记录。

        参数：
            day:        目标日期。
            use_online: 是否优先使用在线数据源；False 时直接使用离线样例。

        返回：
            WeatherRecord（其 source 标明实际来源）。

        异常：
            ValueError: day 不是日期类型。
            DateOutOfRangeError: 日期超出可查询范围（在线模式下）。
        """
        if isinstance(day, datetime):
            day = day.date()
        if not isinstance(day, date):
            raise ValueError("get_weather 需要一个 datetime.date 表示日期")

        # 每次查询先重置降级标记
        self.last_fallback = False

        if use_online:
            cached = self._cache.get(("online", day))
            if cached is not None:
                return cached

            try:
                record = self._online.fetch(day)
            except DateOutOfRangeError:
                # 日期本身不可查询，无需降级，直接上抛由界面友好提示
                raise
            except WeatherUnavailableError:
                # 网络/HTTP 失败 -> 走降级分支
                record = None

            if record is not None:
                self._cache[("online", day)] = record
                return record

            # 记录本次查询发生了降级
            self.last_fallback = True

        # 离线分支（未启用在线，或在线失败降级）
        cached = self._cache.get(("offline", day))
        if cached is not None:
            return cached

        record = self._offline.fetch(day)
        self._cache[("offline", day)] = record
        return record
