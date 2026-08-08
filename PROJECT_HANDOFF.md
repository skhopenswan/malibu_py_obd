# 🚗 雪佛兰迈锐宝 OBD-II 开发项目 — 交接 / 上下文记忆文档

> **给新 AI agent 的指令**：请先完整阅读本文件，再阅读 `test_case.md`、`体检报告.txt` 与本目录下的源码，之后再开始任何修改或开发。本文件记录了截至 2026-08-08 的全部开发历史、技术决策、已完成功能、文件清单与下一步待办。凡标注【约定】【坑】的内容请在后续开发中遵守。

---

## 0. 项目一句话定位

针对**雪佛兰迈锐宝 1.5T (LFV) 车系**，用 **ELM327 通用 OBD 适配器 + USB 线 + Windows 10 + `python-OBD` 库**，实现：
1. 实时读取关心的 OBD 数据并**实时刷屏显示**；
2. 同步把数据**毫秒级时间戳写入 CSV 文件**，便于事后分析；
3. **非原厂 ELM327 读数可信度校验**（防卡死/假数据/超界）；
4. **行车高容错**：OBD 断连自动循环重连，全程无需驾驶员操作电脑。

---

## 1. 运行环境与依赖

- **操作系统**：Windows 10（开发验证机为 win32，VS Code）
- **Python**：3.14.4（`C:\Program Files\Python314\python.exe`；另有 `3.14t` 自由线程版）
- **已安装依赖**（当前环境，安装于用户目录 `C:\Users\aster\AppData\Roaming\Python\Python314\site-packages`）：
  - `obd`（python-OBD）**0.7.3**
  - `pyserial` **3.5**
  - 传递依赖：`pint==0.24.4`、`platformdirs`、`typing-extensions`、`flexcache`、`flexparser`
- **硬件事项**：【约定】OBD 端口默认 **COM4**，波特率 **38400**。若改端口，只改各脚本顶部的 `PORT_NAME`。安装依赖命令：`pip install -r requirements.txt`

---

## 2. 项目文件清单与职责

### 2.1 项目根目录 `d:\MY_TEMP\malibu_pc\malibu_py_obd\`

| 文件 | 作用 |
|---|---|
| `test_case.md` | **需求来源**：车辆信息、关注的故障方向、重点读取数据项(第4章)、判读逻辑(第5章) |
| `体检报告.txt` | 首次体检运行 `malibu_health_check.py` 的真实输出 |
| `malibu_health_check.py` | 早期一次性体检脚本（读故障码、STFT/LTFT、节气门、电压、水温、GM TFT） |
| `malibu_obd_test.py` | 早期实时监控简化版（RPM/Speed/ECT/MAP/Boost/TFT 每秒刷新） |
| `ai_coach.py` | 早期 AI 驾驶教练面板（水温/TFT/负荷/节气门/增压 + 逻辑提示） |
| `shuiwen_test.py`、`test_obd.py`、`test_obd_pyserial.py`、`scan_for.py` | 早期测试/排错/扫描 Mode22 的脚本（scan_for 探测 0x1940-0x1960 TFT DID） |
| `malibu_live_monitor/` | **当前主力子项目**（见下） |

### 2.2 主力子项目 `malibu_live_monitor/`

| 文件 | 作用 | 运行命令 |
|---|---|---|
| `real_time_monitor.py` | **主程序**：实时面板 + 20 列 CSV 存盘 + 断线自动重连（当前 13.9KB） | `python real_time_monitor.py` |
| `verify_obd.py` | **ELM327 可信度校验**：采样 10 次，校验响应率/范围/卡死，导出 txt 报告 | `python verify_obd.py` |
| `test_connection.py` | 端口/适配器连通性快速检测 | `python test_connection.py` |
| `self_test.py` | **离线自测**：模拟数据 + 模拟掉线重连，验证 CSV 与事件日志（无需连车） | `python self_test.py` |
| `requirements.txt` | 依赖：`pyserial>=3.5`、`obd>=0.7.3` | — |
| `README.md` | 子项目使用文档 + 判读手册（6.9KB） | — |
| `data_logs/` | 运行时自动生成：CSV 数据、事件 .log、校验报告 .txt | — |

---

## 3. 车辆背景信息摘要（来源 test_case.md + 体检报告.txt）

### 3.1 车辆
- 2017 款雪佛兰迈锐宝 **1.5T + 6AT(6T45)**，非 XL，发动机 **LFV**，排量 1.49L，净功率 120kW，**怠速约 600rpm**。
- 92 号汽油、8 英寸屏、无 CarPlay/安吉星、**带自动启停**、二手车。
- 轮胎 225/55 R17 97V（2019 年第 41 周）；电瓶约 80Ah / CCA 800A，静置电压约 12.28-12.29V，充电约 13.5-13.8V。

### 3.2 关注的故障方向
1. **进气侧漏气/真空泄漏**（有油迹、怠速有嘶嘶声、开油盖纸被吸入）
2. **PCV 系统异常**（曲轴箱压力、怠速不稳/偏稀/渗油/异响）
3. **增压/进气系统问题**（管路/卡箍/软管老化，加速无力、建压慢）
4. **排气侧泄漏**（冷启动哒哒、氧传感器异常、燃油修正异常）
5. **发动机整体健康**

### 3.3 已测得数据（体检报告.txt，供对比参考）
```
故障码: 无
自清码后里程: 65535
短期燃油修正 STFT: -10.94%
长期燃油修正 LTFT: 2.34%
相对节气门开度: 23.92%  (⚠️ 偏大，疑积碳/补气)
电瓶电压: 13.3 V
冷却液温度: 85 °C
通用 6AT 变速箱油温 TFT: 41 °C
```
【判读提示】STFT -10.94%（偏浓方向异常大，值得后续重点核实是否 ELM 读数异常或真实），LTFT +2.34%（正常范围）。

---

## 4. 核心功能与技术决策

### 4.1 主程序 `real_time_monitor.py`
- **配置区顶部**（USER CONFIG）：`PORT_NAME="COM4"`、`BAUD_RATE=38400`、`REFRESH_INTERVAL=0.8`、`RETRY_DELAY=2.5`、`DISCONNECT_THRESHOLD=2`、`LOG_DIR=data_logs`。
- **GM TFT**（自定义 Mode22）：`OBDCommand("GM_TFT",..., b"221940", 0, raw_string, obd.ECU.ALL, fast=False)`；解析：返回串去空格找 `621940`，其后一字节 hex − 40 = 摄氏度。查询时须 `force=True`。
- **CSV 20 列表头**（顺序固定，勿乱改）：
  `Timestamp | RPM(rpm) | Speed(km/h) | CoolantTemp(C) | IntakeTemp(C) | MAP(kPa) | BaroPressure(kPa) | BoostPressure(bar) | ThrottlePos(%) | STFT(%) | LTFT(%) | MAF(g/s) | O2_B1S1(V) | O2_B1S2(V) | TimingAdvance(deg) | Voltage(V) | EngineLoad(%) | FuelStatus | AmbAirTemp(C) | TFT(C)`
- **Boost 计算**：【约定】`boost_bar = (MAP − BARO) / 100.0`；MAP 缺失时 BARO 默认 101.3。**怠速 Boost 为负数属正常真空**。
- **自动重连机制**：整轮读取被 try 包围；连续 `DISCONNECT_THRESHOLD` 次 RPM 与电压都读不到 → 判定掉线；进入无限重连循环（每次 `obd.OBD(PORT, baudrate=BAUD, fast=False)`），成功后**继续写同一 CSV 文件**；断连/重连时间写入 `malibu_connection_events_<时间戳>.log`。
- 退出：`Ctrl+C` → finally 中关 CSV、关连接、打印两个文件路径与采集行数。

### 4.2 校验程序 `verify_obd.py`
- `PID_SPECS` 字典定义 16 项 PID 的（指令、单位、min/max、is_dynamic）。TFT 单独用 `query_tft_value`。
- 校验 3 维度：①响应率（N 次多少为空）②物理范围（min/max）③动态卡死（is_dynamic 且采样≥5 且 max−min==0 → 提示“疑似 ELM327 缓存卡死”）。
- 输出报告表格 + 汇总，存 `data_logs/obd_verification_<时间戳>.txt`。
- 【坑】旧版本该脚本 `query_tft_value` 函数曾因分段写入被截断，已补全——若日后报错先检查该函数完整性。

### 4.3 自测 `self_test.py`
- 无需连车。`mock_get_obd_data()` 生成合理工况数据，`run_self_test()` 写 CSV、第 3 次采样模拟掉线再恢复、写事件日志、最后断言 CSV 20 列/行数与事件日志条数。
- 通过标志：`🎉 离线断线重连与数据存盘逻辑自测全部通过！`

---

## 5. 已完成的验证记录

- ✅ `python self_test.py` **多次运行通过**（CSV 20 列表头、行数正确；事件日志 3 条含“测试启动/掉线/重连成功”）。最近一次：2026-08-08 17:30:55。
- ✅ `real_time_monitor.py`、`verify_obd.py`、`test_connection.py` 均通过 `python -m py_compile`。
- ✅ 早期体检脚本曾在真实车辆成功读取（体检报告.txt 为证）。
- ⚠️ **真实车辆实测 `real_time_monitor.py` 与 `verify_obd.py` 仍待用户本人在车上验证**（本开发环境无 OBD 硬件，`test_connection.py` 在无车时正确报“连接失败”为预期行为）。

---

## 6. 已知 bug / 曾修复项（请勿重蹈）

1. **`safe_query_str` 曾不完整**（分段写入 `editor` 时被截断，FUEL_STATUS 始终返回 None）——已补全：正确处理 tuple/list → 用 `/` 连接，否则 `str(val)`，异常/空 → 返回 `"N/A"`。
2. **`verify_obd.py` 的 `query_tft_value` 曾被截断**——已补全。
3. **`editor` 工具单次 `new_text` 上限约 6000 字符**：大文件必须**分段写入**，并在每次插入后 `py_compile` 检查，且注意插入处可能残留上一版尾块，需仔细清尾。

---

## 7. 下一步待办（TODO）

1. **[用户操作] 真实车辆实测**：接 COM4，运行 `verify_obd.py` 确认各 PID 可信度，再运行 `real_time_monitor.py` 录制热车怠速/1500/2000/2500rpm/道路负载数据。
2. **数据分析**：把 `data_logs/*.csv` 用 Excel/Python(pandas) 分析 STFT/LTFT、MAP/Boost 趋势，对照 test_case.md 第 5-7 章判断是否漏气/PCV。
3. **可扩展项**（此前计划但未实现）：
   - Mode 06 / 增强 PID 读**失火计数**、**喷油脉宽**、原厂增压压力 DID。
   - `verify_obd.py` 增加“记录每次采样原始值”选项（当前只存结论）。
   - 将 PID 列表抽成**共享配置模块**（当前 `real_time` 与 `verify` 各自维护一份，易漂移）。
   - 给 CSV 增加“连接状态”列或把断连时段在分析时可对事件日志时间轴对齐。
4. **体验优化**：若想 GUI 化可用 tkinter/plot，但当前坚持纯 `print` 面板以保持“最简启动”。

---

## 8. 判读参考速查（摘自觉要）

- **STFT/LTFT**：±5% 健康；+5~+10% 关注；怠速>+10%且升转后下降 → 疑似漏气/PCV；全工况高正值 → 供油/MAF/氧传感。
- **MAP**：热车怠速应明显低于大气压（~30-40kPa）；怠速偏高+节气门开度偏大 → 疑漏气/积碳。
- **Boost**：怠速负（真空）正常；加速应能到 0.3~0.8 bar；建压慢伴嘶嘶声 → 查增压软管/卡箍/中冷。
- 判断原则：**声音 + OBD 数据 + 工况趋势 三者同时归一才可靠**，勿单看一个数。
