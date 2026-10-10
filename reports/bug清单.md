# 天气查询桌面应用 — Bug 清单（TestEngineer / P5 回归复验版）

> 来源：`tests/` 自动化测试暴露的真实缺陷（**无源码修改**）。
> 提交对象：主控 Agent → CodeWriter 已修复 → 本轮 TestEngineer 复验。
> 编号规则：`B**`；严重级别：高 / 中 / 低。
> 对应测试运行：`QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -v`
> 生成日期：2026-10-10（复验更新于第 1 轮修复后）

---

## 汇总

| 编号 | 严重级别 | 标题 | 关联失败用例数 | 状态（v1.0 复验） |
|---|---|---|---|---|
| B01 | 高 | 在线解析遇畸形响应抛非业务异常穿透，破坏「失败必降级」 | 5 | ✅ 已修复 |
| B02 | 高 | 湿度/风速关键字段缺失时静默回填 0，并标注为「在线数据」 | 3 | ✅ 已修复 |
| B03 | 中 | 目标日期不在返回数组时静默取首项并改写 date，造成数据错配 | 1 | ✅ 已修复 |
| B04 | 中 | 在线失败后无负缓存，离线演示场景反复重试（叠加超时反复卡顿） | 1 | ✅ 已修复 |
| B05 | 中 | 查询进行中「查询天气」按钮不禁用、无忙碌态，可重复点击 | 1 | ✅ 已修复 |
| B06 | 低 | `format_temperature` 取整为 0 位小数时出现负零显示 `-0 °C` | 1 | ✅ 已修复 |
| B07 | 低 | WMO 天气码 `1`（Mainly clear）被映射为「多云」 | 1 | ✅ 已修复 |

合计：**7 个 bug**（高 2 / 中 3 / 低 2），对应 13 个失败用例 —— **全部已修复，13 用例全部转绿。
未发现仍未修复的 bug，未发现新 bug（无回归）。**

---

## B01 · 高 · 在线解析遇畸形响应抛非业务异常穿透，破坏「失败必降级」

- **状态**：✅ **已修复**（验证：13 个关联用例全部 PASSED）
- **涉及文件:行**：`weather_app/providers/open_meteo.py`（`_parse`，原 :154/:182/:192）、
  `weather_app/services/weather_service.py`（`get_weather` 在线分支 except）
- **修复要点**：`_parse` 对一切畸形数据统一抛 `WeatherUnavailableError`
  （顶层非 dict / daily 缺失 / 字段类型非法均归一化）；service 在线分支捕获范围扩展为
  `(WeatherUnavailableError, AttributeError, ValueError, TypeError, KeyError)`，确保失败必降级。
- **验证用例（均 PASSED）**：
  - `tests/test_open_meteo.py::test_parse_non_dict_payload_raises_unavailable`
  - `tests/test_open_meteo.py::test_parse_none_payload_raises_unavailable`
  - `tests/test_open_meteo.py::test_parse_string_temperature_raises_unavailable`
  - `tests/test_open_meteo.py::test_parse_string_humidity_raises_unavailable`
  - `tests/test_weather_service.py::test_parse_style_exception_should_degrade`

---

## B02 · 高 · 湿度/风速关键字段缺失时静默回填 0，并标注为「在线数据」

- **状态**：✅ **已修复**（验证：3 个关联用例全部 PASSED）
- **涉及文件:行**：`weather_app/providers/open_meteo.py`（`_parse` 湿度/风速取值，原 :185-186）
- **修复要点**：删除 `value(...) or 0` 静默回填，改用 `to_float()`；
  湿度/风速缺失、为 `null` 或不可解析时一律抛 `WeatherUnavailableError`，与温度字段策略对齐。
- **验证用例（均 PASSED）**：
  - `tests/test_open_meteo.py::test_parse_missing_humidity_raises_unavailable`
  - `tests/test_open_meteo.py::test_parse_missing_wind_raises_unavailable`
  - `tests/test_open_meteo.py::test_parse_null_humidity_raises_unavailable`

---

## B03 · 中 · 目标日期不在返回数组时静默取首项并改写 date，造成数据错配

- **状态**：✅ **已修复**（验证：1 个关联用例 PASSED）
- **涉及文件:行**：`weather_app/providers/open_meteo.py`（`_parse` 日期定位，原 :160-163）
- **修复要点**：删除 `except ValueError: index = 0` 退化容错；
  日期未命中 `times` 时抛 `WeatherUnavailableError`，杜绝把其它日期天气错配给目标日期。
- **验证用例（PASSED）**：
  - `tests/test_open_meteo.py::test_parse_date_not_in_times_raises_unavailable`

---

## B04 · 中 · 在线失败后无负缓存，离线演示场景反复重试（叠加超时反复卡顿）

- **状态**：✅ **已修复**（验证：1 个关联用例 PASSED）
- **涉及文件:行**：`weather_app/services/weather_service.py`（`__init__` / `clear_cache` / `get_weather`）
- **修复要点**：新增 `self._online_failed_days: set[date]` 负缓存；在线失败记入负缓存，
  后续同日期查询跳过在线直接走离线（`last_fallback=True`）；`clear_cache()` 一并清空负缓存。
- **验证用例（PASSED）**：
  - `tests/test_weather_service.py::test_repeated_offline_demo_should_not_retry_online_every_time`
  - 旁证（仍 PASSED，语义未破坏）：`tests/test_weather_service.py::test_clear_cache_forces_refetch`

---

## B05 · 中 · 查询进行中「查询天气」按钮不禁用、无忙碌态，可重复点击

- **状态**：✅ **已修复**（验证：1 个关联用例 PASSED）
- **涉及文件:行**：`weather_app/ui/main_window.py`（`_on_query` + 新增 `_set_querying`）
- **修复要点**：查询开始即 `_set_querying(True)`（按钮禁用、文案「查询中…」），
  业务逻辑包在 `try/finally` 中，`finally` 恢复可用与文案「查询天气」。
- **验证用例（PASSED）**：
  - `tests/test_main_window.py::test_query_button_disabled_during_query`

---

## B06 · 低 · `format_temperature` 取整为 0 位小数时出现负零显示 `-0 °C`

- **状态**：✅ **已修复**（验证：1 个关联用例 PASSED）
- **涉及文件:行**：`weather_app/core/units.py`（`format_temperature`）
- **修复要点**：先 `round(value, decimals)`，再 `if rounded == 0: rounded = 0.0` 消除 IEEE 负零，
  使 `format_temperature(-0.5, "C", 0)` 输出 `"0 °C"`；其余取值结果不变。
- **验证用例（PASSED）**：
  - `tests/test_units.py::test_format_temperature_zero_decimals_negative_value_should_not_be_negative_zero`
  - 旁证（仍 PASSED，未回归）：`test_format_temperature_zero_decimals_rounds`、`test_format_temperature_negative`

---

## B07 · 低 · WMO 天气码 `1`（Mainly clear）被映射为「多云」

- **状态**：✅ **已修复**（验证：1 个关联用例 PASSED）
- **涉及文件:行**：`weather_app/providers/open_meteo.py`（`map_wmo_code`，原 :64）
- **修复要点**：拆开原 `if code in (1, 2)`：`code == 1` → `SUNNY`，`code == 2` → `CLOUDY`。
- **验证用例（PASSED）**：
  - `tests/test_open_meteo.py::test_map_wmo_code_1_mainly_clear_is_sunny`
  - 旁证（仍 PASSED，未回归）：`test_map_wmo_code[2-cloudy]`

---

## 回归说明

复验命令：
```bash
cd "/home/yuan/桌面/SofteareEnjineer/任务02-Agent团队开发/workspace"
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -v
```

复验结果：**151 passed in 0.29s**。

- 上一轮 151 用例中 13 个失败用例（对应 B01–B07）**全部转为通过**。
- 用例集合**未增删**（仍 151 个），确认是源码修复生效而非测试被改动。
- **无新增失败 / 无回归**。

*（本清单仅记录测试发现与复验结论，未修改任何源码文件。）*
