"""providers.open_meteo —— 在线数据源（open-meteo，免 key）。

数据源说明：
    * 历史日期 -> archive-api.open-meteo.com（归档数据）
    * 今天 ~ 未来 16 天 -> api.open-meteo.com（预报数据）
    * 超出范围 -> 抛 DateOutOfRangeError
    * 网络/HTTP/解析失败 -> 抛 WeatherUnavailableError

默认城市为上海（lat 31.23, lon 121.47）。
"""
from __future__ import annotations

from datetime import date, datetime

import requests

from ..core import date_utils
from ..core.errors import DateOutOfRangeError, WeatherUnavailableError
from ..core.models import (
    CLOUDY,
    DRIZZLE,
    FOG,
    OVERCAST,
    RAIN,
    SNOW,
    SOURCE_OPEN_METEO,
    SUNNY,
    THUNDER,
    WeatherRecord,
)
from .base import WeatherProvider

# open-meteo 接口地址
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# 默认位置：上海
DEFAULT_LATITUDE = 31.23
DEFAULT_LONGITUDE = 121.47
DEFAULT_CITY = "上海"

# 默认网络超时（秒）
DEFAULT_TIMEOUT = 8

# 需要的每日变量：天气码、最高/最低温、平均湿度、最大风速
_DAILY_VARIABLES = (
    "weather_code,"
    "temperature_2m_max,"
    "temperature_2m_min,"
    "relative_humidity_2m_mean,"
    "wind_speed_10m_max"
)


def map_wmo_code(code) -> str:
    """把 WMO 天气码映射为内部天气状况常量，未知码回退为多云。"""
    try:
        code = int(code)
    except (TypeError, ValueError):
        return CLOUDY

    if code == 0:
        return SUNNY
    if code in (1, 2):
        return CLOUDY
    if code == 3:
        return OVERCAST
    if code in (45, 48):
        return FOG
    if code in (51, 53, 55, 56, 57):
        return DRIZZLE
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return RAIN
    if code in (71, 73, 75, 77, 85, 86):
        return SNOW
    if code in (95, 96, 99):
        return THUNDER
    return CLOUDY


class OpenMeteoProvider(WeatherProvider):
    """open-meteo 在线数据源。"""

    name = "open-meteo"

    def __init__(
        self,
        latitude: float = DEFAULT_LATITUDE,
        longitude: float = DEFAULT_LONGITUDE,
        city: str = DEFAULT_CITY,
        timeout: float = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        self.latitude = latitude
        self.longitude = longitude
        self.city = city
        self.timeout = timeout
        # 允许注入 session，便于复用连接或测试替换
        self._session = session or requests.Session()

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def fetch(self, day: date) -> WeatherRecord:
        """获取指定日期的天气记录。"""
        if isinstance(day, datetime):
            day = day.date()
        if not isinstance(day, date):
            raise DateOutOfRangeError("日期类型非法，需要一个 datetime.date")

        if not date_utils.is_supported_range(day):
            raise DateOutOfRangeError(
                f"日期 {day.isoformat()} 超出可查询范围"
                f"（支持 {date_utils.MIN_SUPPORTED_DATE.isoformat()}"
                f" 至 {date_utils.max_supported_date().isoformat()}）"
            )

        # 历史日期走归档接口，今天及未来走预报接口
        if day >= date_utils.today():
            payload = self._request(FORECAST_URL, day)
        else:
            payload = self._request(ARCHIVE_URL, day)

        return self._parse(payload, day)

    # ------------------------------------------------------------------
    # 内部：请求与解析
    # ------------------------------------------------------------------
    def _request(self, url: str, day: date) -> dict:
        """发起 HTTP 请求并返回解析后的 JSON，失败统一抛 WeatherUnavailableError。"""
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "daily": _DAILY_VARIABLES,
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
            "timezone": "auto",
        }
        try:
            response = self._session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise WeatherUnavailableError(f"网络请求失败：{exc}") from exc

        if response.status_code != 200:
            raise WeatherUnavailableError(f"数据源返回 HTTP {response.status_code}")

        try:
            return response.json()
        except ValueError as exc:
            raise WeatherUnavailableError("数据源返回内容无法解析为 JSON") from exc

    def _parse(self, payload: dict, day: date) -> WeatherRecord:
        """把 open-meteo 的 JSON 响应解析为 WeatherRecord。"""
        daily = payload.get("daily") or {}
        times = daily.get("time") or []
        if not times:
            raise WeatherUnavailableError("数据源未返回每日数据")

        # 定位目标日期在返回数组中的下标（正常应命中，否则退化为第一项）
        try:
            index = times.index(day.isoformat())
        except ValueError:
            index = 0

        def value(key: str, default=None):
            """安全取值：数组越界或为 null 时返回默认值。"""
            seq = daily.get(key) or []
            if index < len(seq) and seq[index] is not None:
                return seq[index]
            return default

        t_max = value("temperature_2m_max")
        t_min = value("temperature_2m_min")
        if t_max is None and t_min is None:
            raise WeatherUnavailableError("数据源缺少温度数据")
        if t_max is None:
            t_max = t_min
        if t_min is None:
            t_min = t_max

        # 以当日最高/最低温的平均值作为展示温度
        temp_c = (float(t_max) + float(t_min)) / 2.0

        code = value("weather_code")
        humidity = value("relative_humidity_2m_mean", 0) or 0
        wind_kph = value("wind_speed_10m_max", 0) or 0

        return WeatherRecord(
            date=day,
            condition=map_wmo_code(code),
            temp_c=round(temp_c, 1),
            humidity=float(humidity),
            wind_kph=float(wind_kph),
            source=SOURCE_OPEN_METEO,
        )
