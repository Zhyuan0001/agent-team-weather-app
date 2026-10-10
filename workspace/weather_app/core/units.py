"""core.units —— 温度单位换算与格式化。

内部统一以摄氏度存储，展示时再按用户选择的单位换算。
"""
from __future__ import annotations

# 单位标识
UNIT_CELSIUS = "C"      # 摄氏度
UNIT_FAHRENHEIT = "F"   # 华氏度

# 单位 -> 符号
_UNIT_SYMBOLS = {
    UNIT_CELSIUS: "°C",
    UNIT_FAHRENHEIT: "°F",
}


def c_to_f(celsius: float) -> float:
    """摄氏度 -> 华氏度。"""
    return float(celsius) * 9.0 / 5.0 + 32.0


def f_to_c(fahrenheit: float) -> float:
    """华氏度 -> 摄氏度。"""
    return (float(fahrenheit) - 32.0) * 5.0 / 9.0


def unit_symbol(unit: str) -> str:
    """返回单位符号（°C / °F），未知单位回退为摄氏度。"""
    return _UNIT_SYMBOLS.get(unit, "°C")


def convert(temp_c: float, unit: str = UNIT_CELSIUS) -> float:
    """把摄氏温度换算到目标单位（摄氏度则原样返回）。"""
    if unit == UNIT_FAHRENHEIT:
        return c_to_f(temp_c)
    return float(temp_c)


def format_temperature(temp_c: float, unit: str = UNIT_CELSIUS, decimals: int = 1) -> str:
    """把摄氏温度格式化为带单位符号的字符串，例如 ``"23.4 °C"``。"""
    value = convert(temp_c, unit)
    # 先按精度取整，再把 ±0.0 统一归零；否则 -0.5 在 0 位小数下会显示为「-0 °C」
    rounded = round(value, decimals)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.{decimals}f} {unit_symbol(unit)}"
