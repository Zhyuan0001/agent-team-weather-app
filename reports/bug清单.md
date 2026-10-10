# 天气查询桌面应用 — Bug 清单（TestEngineer / 第 2 轮回归复验版）

> 来源：`tests/` 自动化测试暴露的真实缺陷 + `reports/评审报告.md` 高风险项（**无源码修改**）。
> 编号规则：测试发现的缺陷记 `B**`；评审报告高风险/中风险项沿用其原编号（如 `H1`）。
> 严重级别：高 / 中 / 低。
> 对应测试运行：`QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -v`
> 生成日期：2026-10-10（第 2 轮复验更新于 H1 修复后）

---

## 汇总

| 编号 | 严重级别 | 标题 | 关联失败用例数 | 状态（第 2 轮复验） |
|---|---|---|---|---|
| B01 | 高 | 在线解析遇畸形响应抛非业务异常穿透，破坏「失败必降级」 | 5 | ✅ 已修复 |
| B02 | 高 | 湿度/风速关键字段缺失时静默回填 0，并标注为「在线数据」 | 3 | ✅ 已修复 |
| B03 | 中 | 目标日期不在返回数组时静默取首项并改写 date，造成数据错配 | 1 | ✅ 已修复 |
| B04 | 中 | 在线失败后无负缓存，离线演示场景反复重试（叠加超时反复卡顿） | 1 | ✅ 已修复 |
| B05 | 中 | 查询进行中「查询天气」按钮不禁用、无忙碌态，可重复点击 | 1 | ✅ 已修复 |
| B06 | 低 | `format_temperature` 取整为 0 位小数时出现负零显示 `-0 °C` | 1 | ✅ 已修复 |
| B07 | 低 | WMO 天气码 `1`（Mainly clear）被映射为「多云」 | 1 | ✅ 已修复 |
| **H1** | **高** | **「查询天气」在 GUI 主线程内同步发起阻塞式网络请求，无网/弱网时界面冻结至多 8s** | **9（第 2 轮 UI 用例因异步改动时序失败）** | ✅ **已修复** |

合计：**8 个 bug**（高 3 / 中 3 / 低 2）。
- 第 1 轮：B01–B07 共 7 个（高 2 / 中 3 / 低 2），13 个失败用例全部转绿；
- 第 2 轮：**H1 已修复**，并新增 3 个验证用例；既有 9 个 UI 查询类用例经注入同步执行器适配后保持通过。
- **未发现仍未修复的 bug，未发现新 bug（无回归）。**

---

## B01 · 高 · 在线解析遇畸形响应抛非业务异常穿透，破坏「失败必降级」

- **状态**：✅ **已修复**（验证：5 个关联用例全部 PASSED）
- **涉及文件:行**：`weather_app/providers/open_meteo.py`（`_parse`）、
  `weather_app/services/weather_service.py`（`get_weather` 在线分支 except）
- **修复要点**：`_parse` 对一切畸形数据统一抛 `WeatherUnavailableError`；service 在线分支
  捕获范围扩展为 `(WeatherUnavailableError, AttributeError, ValueError, TypeError, KeyError)`，
  确保失败必降级。
- **验证用例（均 PASSED）**：
  - `tests/test_open_meteo.py::test_parse_non_dict_payload_raises_unavailable`
  - `tests/test_open_meteo.py::test_parse_none_payload_raises_unavailable`
  - `tests/test_open_meteo.py::test_parse_string_temperature_raises_unavailable`
  - `tests/test_open_meteo.py::test_parse_string_humidity_raises_unavailable`
  - `tests/test_weather_service.py::test_parse_style_exception_should_degrade`

---

## B02 · 高 · 湿度/风速关键字段缺失时静默回填 0，并标注为「在线数据」

- **状态**：✅ **已修复**（验证：3 个关联用例全部 PASSED）
- **涉及文件:行**：`weather_app/providers/open_meteo.py`（`_parse` 湿度/风速取值）
- **修复要点**：删除 `value(...) or 0` 静默回填，改用 `to_float()`；缺失/`null`/不可解析一律抛
  `WeatherUnavailableError`，与温度字段策略对齐。
- **验证用例（均 PASSED）**：
  - `tests/test_open_meteo.py::test_parse_missing_humidity_raises_unavailable`
  - `tests/test_open_meteo.py::test_parse_missing_wind_raises_unavailable`
  - `tests/test_open_meteo.py::test_parse_null_humidity_raises_unavailable`

---

## B03 · 中 · 目标日期不在返回数组时静默取首项并改写 date，造成数据错配

- **状态**：✅ **已修复**（验证：1 个关联用例 PASSED）
- **涉及文件:行**：`weather_app/providers/open_meteo.py`（`_parse` 日期定位）
- **修复要点**：删除 `except ValueError: index = 0` 退化容错；日期未命中 `times` 时抛
  `WeatherUnavailableError`，杜绝把其它日期天气错配给目标日期。
- **验证用例（PASSED）**：
  - `tests/test_open_meteo.py::test_parse_date_not_in_times_raises_unavailable`

---

## B04 · 中 · 在线失败后无负缓存，离线演示场景反复重试（叠加超时反复卡顿）

- **状态**：✅ **已修复**（验证：1 个关联用例 PASSED）
- **涉及文件:行**：`weather_app/services/weather_service.py`（`__init__` / `clear_cache` / `get_weather`）
- **修复要点**：新增 `self._online_failed_days: set[date]` 负缓存；在线失败记入负缓存，后续同日期
  查询跳过在线直接走离线（`last_fallback=True`）；`clear_cache()` 一并清空负缓存。
- **验证用例（PASSED）**：
  - `tests/test_weather_service.py::test_repeated_offline_demo_should_not_retry_online_every_time`
  - 旁证（仍 PASSED，语义未破坏）：`tests/test_weather_service.py::test_clear_cache_forces_refetch`

---

## B05 · 中 · 查询进行中「查询天气」按钮不禁用、无忙碌态，可重复点击

- **状态**：✅ **已修复**（第 2 轮接口适配后语义不变，验证：1 个关联用例 PASSED）
- **涉及文件:行**：`weather_app/ui/main_window.py`（`_on_query` + 新增 `_set_querying`）
- **修复要点**：查询开始即 `_set_querying(True)`（按钮禁用、文案「查询中…」），业务逻辑包在
  `try/finally` 中，`finally` 恢复可用与文案「查询天气」；第 2 轮 H1 修复后该忙碌态逻辑保留，
  改为在 `_on_query` 起点设置、在成功/失败回调的 `finally` 中恢复。
- **验证用例（PASSED）**：
  - `tests/test_main_window.py::test_query_button_disabled_during_query`
    （第 2 轮构造方式适配为 `MainWindow(service=svc, runner=SyncQueryRunner())`，断言逐字保留）

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
- **涉及文件:行**：`weather_app/providers/open_meteo.py`（`map_wmo_code`）
- **修复要点**：拆开原 `if code in (1, 2)`：`code == 1` → `SUNNY`，`code == 2` → `CLOUDY`。
- **验证用例（PASSED）**：
  - `tests/test_open_meteo.py::test_map_wmo_code_1_mainly_clear_is_sunny`
  - 旁证（仍 PASSED，未回归）：`test_map_wmo_code[2-cloudy]`

---

## H1 · 高 · 「查询天气」在 GUI 主线程内同步发起阻塞式网络请求（第 2 轮新增）

> 来源：`reports/评审报告.md` H1（与 M5 同源）；第 2 轮 CodeWriter 修复，TestEngineer 复验。

- **状态**：✅ **已修复**（验证：3 个专用用例全部 PASSED；连续 10 次重跑无抖动）
- **问题**：`ui/main_window.py` 的 `_on_query` 在 GUI 主线程内同步调用
  `service.get_weather()`，其内部为阻塞式 `requests.Session.get`（超时最长约 8s）。
  无网/弱网时点击查询后窗口直接冻结至多 8 秒，直接损害 SPEC A3「断网降级演示」的人工观感。
- **涉及文件:行**：
  - 新增 `weather_app/ui/query_runner.py`（`QueryRunner` 抽象 / `SyncQueryRunner` / `ThreadQueryRunner`）；
  - 修改 `weather_app/ui/main_window.py`（`__init__` 增加 `runner` 注入，默认 `ThreadQueryRunner`；
    `_on_query` 改为「忙碌态 → runner.run → 回调渲染/提示 → 恢复按钮」）；
  - 修改 `weather_app/ui/__init__.py`（再导出执行器）。
- **修复要点**：把阻塞式 `service.get_weather` 移出 GUI 主线程——`ThreadQueryRunner` 用一次性
  `QThread`（`_WeatherWorker`）在后台执行，结果/异常经 `succeeded(record, last_fallback)` /
  `failed(exc)` 信号（跨线程自动队列连接）投递回主线程再渲染；`SyncQueryRunner` 供测试注入，
  同步回调保证断言确定性。执行器与界面双层防抖（`isRunning()` 检查 + `_querying` 守卫）确保
  同一时刻最多一次在途查询。
- **验证用例（均 PASSED）**：
  - `tests/test_main_window.py::test_default_runner_is_thread_query_runner`
    —— 默认 `runner` 类型为 `ThreadQueryRunner`（回归证明真实应用不再走同步路径）；
  - `tests/test_main_window.py::test_query_does_not_block_main_thread`
    —— 假 service `time.sleep(0.25s)`：`_on_query()` 立即返回（耗时 < 0.2s），返回瞬间按钮已禁用、
    结果未渲染；随后 `processEvents()` 轮询等待结果回主线程，断言渲染完成、按钮恢复；
  - `tests/test_main_window.py::test_second_query_ignored_while_busy`
    —— 首查在途时两次重复 `_on_query()`：`runner.run` 仅调用 1 次、`service.calls == 1`，按钮保持禁用。
- **旁证（仍 PASSED，既有对外行为未回归）**：`test_query_renders_online_record`、
  `test_unit_switch_rerenders_without_refetch`、`test_query_button_disabled_during_query`、
  `test_fallback_message_when_online_failed`、`test_offline_only_message_when_online_disabled`
  等 UI 用例（构造方式适配为注入 `SyncQueryRunner`，断言逐字保留）。

---

## 回归说明

复验命令：
```bash
cd "/home/yuan/桌面/SofteareEnjineer/任务02-Agent团队开发/workspace"
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -v
```

复验结果：**154 passed in 0.84s**（全量重跑 5 次均稳定 154 passed）。

- 第 1 轮 151 用例中 13 个失败用例（对应 B01–B07）持续通过；
- 第 2 轮新增 3 个 H1 验证用例，覆盖「默认异步执行器 / 主线程不阻塞 / 忙碌防抖」；
- 既有 9 个 UI 查询类用例仅「构造方式」适配（注入 `SyncQueryRunner`），**断言未削弱、未删除**；
- **无新增失败 / 无回归 / 未发现新 bug**。

*（本清单仅记录测试发现与复验结论，未修改任何业务源码文件。）*
