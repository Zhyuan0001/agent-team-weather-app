"""core/units 单元测试：摄氏/华氏换算与温度格式化（含负温、取整）。"""
from __future__ import annotations

import pytest

from weather_app.core import units


# ---------------------------------------------------------------------------
# c_to_f / f_to_c
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "c, expected_f",
    [
        (0, 32.0),
        (100, 212.0),
        (-40, -40.0),
        (37, 98.6),
        (-10, 14.0),
    ],
)
def test_c_to_f(c, expected_f):
    assert units.c_to_f(c) == pytest.approx(expected_f)


@pytest.mark.parametrize(
    "f, expected_c",
    [
        (32, 0.0),
        (212, 100.0),
        (-40, -40.0),
        (98.6, 37.0),
    ],
)
def test_f_to_c(f, expected_c):
    assert units.f_to_c(f) == pytest.approx(expected_c)


def test_conversion_round_trip():
    for c in (-30, -1.5, 0, 12.3, 100):
        assert units.f_to_c(units.c_to_f(c)) == pytest.approx(c)


# ---------------------------------------------------------------------------
# unit_symbol / convert
# ---------------------------------------------------------------------------
def test_unit_symbol_known_and_unknown():
    assert units.unit_symbol(units.UNIT_CELSIUS) == "°C"
    assert units.unit_symbol(units.UNIT_FAHRENHEIT) == "°F"
    assert units.unit_symbol("K") == "°C"  # 未知单位回退摄氏度


def test_convert_defaults_to_celsius():
    assert units.convert(20.0) == 20.0
    assert units.convert(20.0, units.UNIT_CELSIUS) == 20.0
    assert units.convert(0.0, units.UNIT_FAHRENHEIT) == pytest.approx(32.0)
    assert units.convert(20.0, "K") == 20.0  # 未知单位按摄氏度


# ---------------------------------------------------------------------------
# format_temperature
# ---------------------------------------------------------------------------
def test_format_temperature_celsius_default_decimals():
    assert units.format_temperature(23.44) == "23.4 °C"


def test_format_temperature_negative():
    assert units.format_temperature(-5.04, "C") == "-5.0 °C"
    assert units.format_temperature(-40, "C") == "-40.0 °C"


def test_format_temperature_fahrenheit():
    assert units.format_temperature(100, "F") == "212.0 °F"
    assert units.format_temperature(-40, "F") == "-40.0 °F"


def test_format_temperature_zero_decimals_rounds():
    assert units.format_temperature(23.44, "C", 0) == "23 °C"
    assert units.format_temperature(23.6, "C", 0) == "24 °C"


def test_format_temperature_zero_decimals_negative_value_should_not_be_negative_zero():
    """取整到 0 位小数时，-0.5 不应显示为「-0 °C」这一负零瑕疵（对应用户可见的显示错误）。"""
    result = units.format_temperature(-0.5, "C", 0)
    assert result == "0 °C", f"负零显示瑕疵：得到 {result!r}"
