# 天气查询桌面应用 — Bug 清单（TestEngineer / P4）

> 来源：`tests/` 自动化测试暴露的真实缺陷（**无源码修改**）。
> 提交对象：主控 Agent → 转交 CodeWriter 修复。
> 编号规则：`B**`；严重级别：高 / 中 / 低。
> 对应测试运行：`QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -v`
> 生成日期：2026-10-10

---

## 汇总

| 编号 | 严重级别 | 标题 | 关联失败用例数 |
|---|---|---|---|
| B01 | 高 | 在线解析遇畸形响应抛非业务异常穿透，破坏「失败必降级」 | 5 |
| B02 | 高 | 湿度/风速关键字段缺失时静默回填 0，并标注为「在线数据」 | 3 |
| B03 | 中 | 目标日期不在返回数组时静默取首项并改写 date，造成数据错配 | 1 |
| B04 | 中 | 在线失败后无负缓存，离线演示场景反复重试（叠加超时反复卡顿） | 1 |
| B05 | 中 | 查询进行中「查询天气」按钮不禁用、无忙碌态，可重复点击 | 1 |
| B06 | 低 | `format_temperature` 取整为 0 位小数时出现负零显示 `-0 °C` | 1 |
| B07 | 低 | WMO 天气码 `1`（Mainly clear）被映射为「多云」 | 1 |

合计：**7 个 bug**（高 2 / 中 3 / 低 2），对应 13 个失败用例。

---

## B01 · 高 · 在线解析遇畸形响应抛非业务异常穿透，破坏「失败必降级」

- **涉及文件:行**：`weather_app/providers/open_meteo.py:154`（`payload.get`）、
  `:182`（`float(t_max)`）、`:192`（`float(humidity)`）；
  `weather_app/services/weather_service.py:70-81`（只捕获两类业务异常）
- **关联用例**：`test_parse_non_dict_payload_raises_unavailable`、
  `test_parse_none_payload_raises_unavailable`、`test_parse_string_temperature_raises_unavailable`、
  `test_parse_string_humidity_raises_unavailable`、`test_parse_style_exception_should_degrade`
- **复现步骤**：
  1. 构造 `OpenMeteoProvider`（注入伪造 session）；
  2. 分别调用 `provider._parse(payload, date(2023,7,15))`，payload 依次为
     `["x"]`、`None`、温度字段 `["abc"]`、湿度字段 `["abc"]`；
     （或在 service 层让 online provider 抛 `AttributeError`）
  3. 观察抛出的异常类型。
- **期望 vs 实际**：
  - 期望：统一抛 `WeatherUnavailableError`（SPEC F4：失败时自动降级），
    service 捕获后降级为离线并提示「离线示例数据」；
  - 实际：抛 `AttributeError` / `ValueError`，**穿透 service 的 except 分支**，不降级，
    只能靠 UI 兜底 `except Exception` 显示「查询失败…」，离线兜底能力失效。
- **影响**：一旦 open-meteo 返回结构变化（非 JSON 对象、字段变字符串），
  「失败必降级」的保证被破坏，直接违反 SPEC F4。

---

## B02 · 高 · 湿度/风速关键字段缺失时静默回填 0，并标注为「在线数据」

- **涉及文件:行**：`weather_app/providers/open_meteo.py:185-186`
  （`value("relative_humidity_2m_mean", 0) or 0`、`value("wind_speed_10m_max", 0) or 0`）
- **关联用例**：`test_parse_missing_humidity_raises_unavailable`、
  `test_parse_missing_wind_raises_unavailable`、`test_parse_null_humidity_raises_unavailable`
- **复现步骤**：
  1. 构造 payload，`daily` 中省略 `relative_humidity_2m_mean`（或置为 `null`），
     其余字段正常；另一例省略 `wind_speed_10m_max`；
  2. 调用 `provider._parse(payload, day)`；
  3. 打印返回的 `WeatherRecord`。
- **期望 vs 实际**：
  - 期望：关键字段缺失视为数据不可用 → 抛 `WeatherUnavailableError` 以降级；
    （温度字段缺失已按此策略处理，湿度/风速应对齐）
  - 实际：静默回填 `humidity=0.0 / wind_kph=0.0`，且 `source="open-meteo"`，
    界面会显示「湿度 0% / 风速 0.0 km/h」并标注为「在线数据」。
- **影响**：**静默错误数据**（比报错更难发现），违反 SPEC F3 展示准确性。

---

## B03 · 中 · 目标日期不在返回数组时静默取首项并改写 date，造成数据错配

- **涉及文件:行**：`weather_app/providers/open_meteo.py:160-163`
  （`except ValueError: index = 0`）
- **关联用例**：`test_parse_date_not_in_times_raises_unavailable`
- **复现步骤**：
  1. 构造 payload：`daily.time = ["2000-01-01"]`，温度/状况数组各 1 项；
  2. 调用 `provider._parse(payload, date(2023,7,15))`；
  3. 查看返回记录的 `date` 与数值。
- **期望 vs 实际**：
  - 期望：日期未命中返回数组 → 视为数据源异常，抛 `WeatherUnavailableError`；
  - 实际：`index` 退化为 `0`，返回一条 `date=2023-07-15` 但数值取自 `2000-01-01` 的记录。
- **影响**：会把**其它日期的天气**当成本日数据展示，且 `date` 被改写，
  用户无法察觉；当前因请求固定 `start_date=end_date` 命中率高，属潜在缺陷。

---

## B04 · 中 · 在线失败后无负缓存，离线演示场景反复重试（叠加超时反复卡顿）

- **涉及文件:行**：`weather_app/services/weather_service.py:65-93`（`get_weather` 降级分支只写离线缓存）
- **关联用例**：`test_repeated_offline_demo_should_not_retry_online_every_time`
- **复现步骤**：
  1. 构造 `WeatherService`，注入「持续抛 `WeatherUnavailableError`」的 online provider；
  2. 连续调用 `service.get_weather(day, use_online=True)` 两次；
  3. 断言 online provider 的调用次数。
- **期望 vs 实际**：
  - 期望：在线失败后应有短期失败记忆（负缓存/TTL），第二次直接走离线 → online 调用 **1 次**；
  - 实际：online 每次都被重新尝试 → 调用 **2 次**（并各等待一次完整超时）。
- **影响**：与评审 H1（同步阻塞主线程）叠加，无网环境下用户每点一次查询都要
  重新等待完整超时，无法满足 SPEC §2「完全离线可演示」。

---

## B05 · 中 · 查询进行中「查询天气」按钮不禁用、无忙碌态，可重复点击

- **涉及文件:行**：`weather_app/ui/main_window.py:115-118`（按钮创建）、
  `:172-190`（`_on_query` 未做状态管理）
- **关联用例**：`test_query_button_disabled_during_query`
- **复现步骤**：
  1. 构造主窗口，注入一个在 `get_weather` 内部读取 `query_button.isEnabled()` 的替身 service；
  2. 触发 `_on_query()`；
  3. 读取查询过程中记录的按钮可用状态。
- **期望 vs 实际**：
  - 期望：查询开始即 `query_button.setEnabled(False)`，结束恢复，并显示「查询中…」；
  - 实际：查询进行中按钮仍为 **可用**（`isEnabled() == True`）。
- **影响**：阻塞期间用户再次点击会被 Qt 事件队列缓存，首次返回后再次触发一次网络请求
  （重复查询/重复等待），且无反馈易被误判为「程序卡死」。属评审 H1/M5 的可自动化部分。

---

## B06 · 低 · `format_temperature` 取整为 0 位小数时出现负零显示 `-0 °C`

- **涉及文件:行**：`weather_app/core/units.py:43`
- **关联用例**：`test_format_temperature_zero_decimals_negative_value_should_not_be_negative_zero`
- **复现步骤**：调用 `format_temperature(-0.5, "C", 0)`。
- **期望 vs 实际**：
  - 期望：显示 `"0 °C"`；
  - 实际：显示 `"-0 °C"`（IEEE 负零经 f-string 舍入产生负号）。
- **影响**：极端取值下的显示瑕疵（用户可见的 `-0`）。

---

## B07 · 低 · WMO 天气码 `1`（Mainly clear）被映射为「多云」

- **涉及文件:行**：`weather_app/providers/open_meteo.py:64`（`if code in (1, 2): return CLOUDY`）
- **关联用例**：`test_map_wmo_code_1_mainly_clear_is_sunny`
- **复现步骤**：调用 `map_wmo_code(1)`。
- **期望 vs 实际**：
  - 期望：`"sunny"`（WMO 1 = Mainly clear ≈ 大部晴朗）；
  - 实际：`"cloudy"`（与 WMO 2 Partly cloudy 同归「多云」）。
- **影响**：偏晴天气被展示为「多云」，影响 SPEC F3 的展示准确度。

---

## 回归说明

修复后请重跑：
```bash
cd "/home/yuan/桌面/SofteareEnjineer/任务02-Agent团队开发/workspace"
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -v
```
目标：151 个用例全绿（13 个失败用例转为通过）。
若**有意保留**某些当前行为（如 B02 选择「容错」而非报错），请同步更新 SPEC 并调整对应用例的期望，而非删除用例。

*（本清单仅记录测试发现，未修改任何源码文件。）*
