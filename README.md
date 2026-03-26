# DXJ / EWJ 日本 ETF 研究与执行

仓库当前主线已经切到日本 ETF：
- `DXJ`：WisdomTree Japan Hedged Equity Fund
- `EWJ`：iShares MSCI Japan ETF

项目目标不是单一回测，而是完整跑通：
- 数据获取
- 资产画像
- 驱动归因
- 条件分层
- 稳定性与执行验证
- 日频信号与月度风控

## 当前结论

- `DXJ` 和 `EWJ` 的差异，本质上主要来自汇率对冲；`DXJ-EWJ` 的相对收益与 `FXY` 高度相关
- 两个标的里，`IBS` 明显强于简单 `Gap` 修复
- 条件分层里真正值得推进的 `Core` 候选只有两个：
  - `DXJ | IBS | Cross-Hedge Divergence | Neutral`
  - `EWJ | IBS | Cross-Hedge Divergence | Neutral`
- 条件化参数在全样本里有时更好看，但半样本样本外验证不支持把它们拆成独立参数策略

## 策略研究文档

文档按阅读顺序编号，位于 `docs/` 目录。为避免目录过长，分成三个清晰区块：方法总纲、单标的研究、联合研究与执行。

### 方法总纲

先看研究方法，再看具体标的和执行层。

| # | 文件 | 内容概要 |
| - | ---- | -------- |
| 00A | [通用研究框架](docs/00_general_research_framework.md) | 脱离具体标的的通用研究方法，从资产画像到执行工具化的完整流程 |
| 00B | [日本 ETF 研究框架](docs/00_dxj_research_framework.md) | 把通用框架落到 `DXJ / EWJ` 这条线，定义研究顺序与脚本规划 |

### 单标的研究

这一组对应 `DXJ` 和 `EWJ` 的底层画像、驱动归因和单标的策略扫描。

| # | 文件 | 内容概要 |
| - | ---- | -------- |
| 01A | [DXJ 底层研究](docs/01_dxj_research.md) | DXJ 的流动性、波动、极端日、分布特征与资产画像 |
| 01B | [EWJ 底层研究](docs/01_ewj_research.md) | EWJ 的流动性、波动、极端日、分布特征与资产画像 |
| 02A | [DXJ 驱动归因](docs/02_dxj_event_drivers.md) | DXJ 与日本 beta、汇率和外部事件的驱动关系 |
| 02B | [EWJ 驱动归因](docs/02_ewj_event_drivers.md) | EWJ 与日本 beta、汇率和外部事件的驱动关系 |
| 03A | [DXJ 策略研究](docs/03_dxj_strategy_research.md) | DXJ 的日线规律、IBS 与 Gap 策略扫描 |
| 03B | [EWJ 策略研究](docs/03_ewj_strategy_research.md) | EWJ 的日线规律、IBS 与 Gap 策略扫描 |

### 联合研究与执行

这一组把两个标的一起研究，并把结果收口到税务、手册、信号和风控。

| # | 文件 | 内容概要 |
| - | ---- | -------- |
| 04 | [税务分析](docs/04_dxj_ewj_tax_analysis.md) | IB 交易 `DXJ / EWJ` 时，美国税务居民与非居民的关键税务差异 |
| 05 | [策略操作手册](docs/05_dxj_strategy_playbook.md) | 当前日本 ETF 执行框架、Core 候选、仓位与风控纪律 |
| 06 | [执行追踪日志模板](docs/06_dxj_execution_log.md) | 交易记录、月度汇总、税务检查和风险复盘模板 |
| 07 | [DXJ / EWJ 对比](docs/07_dxj_ewj_comparison.md) | 两个日本 ETF 的结构差异、恢复能力和策略侧重点 |
| 08 | [事件对齐分析](docs/08_dxj_ewj_event_alignment.md) | 对齐同日事件，拆解日本 beta 与汇率对冲效应 |
| 09 | [IBS 与 FXY Regime](docs/09_dxj_ewj_ibs_fx_regime.md) | 测试 `FXY regime` 对 IBS 信号质量的影响 |
| 10 | [FXY 条件交互](docs/10_fxy_conditioning_interactions.md) | 测试 `FXY × 事件类型 × 策略` 的联合条件格子 |
| 11 | [条件格子稳定性](docs/11_condition_stability.md) | 检查有效格子是否在时间维度上保持稳定 |
| 12 | [执行敏感性验证](docs/12_stable_cell_execution.md) | 测试更保守执行假设下，哪些格子仍然成立 |
| 13 | [条件参数扫描](docs/13_condition_specific_params.md) | 比较统一参数与条件参数是否值得拆分 |
| 14 | [半样本样本外验证](docs/14_parameter_walkforward.md) | 用 walk-forward 检查条件参数是否真的优于统一参数 |
| 15 | [信号候选清单](docs/15_signal_shortlist.md) | 把 Core、Secondary、Watchlist 候选按优先级收口 |
| 16 | [Japan Core Signal Engine](docs/16_japan_core_signal_engine.md) | 当前日频信号脚本、状态文件和月度风控入口说明 |
| R1 | [Japan Core 月度风控报告](docs/risk_reports/japan_core_2026-03.md) | 最新一次风险监控输出，检查 Core 候选是否出现衰减迹象 |

## 数据与研究脚本

### 历史数据

```bash
python download_dxj_polygon.py
python download_ewj_polygon.py
```

### 每日更新

```bash
python update_dxj_today.py
python update_ewj_today.py
```

### 研究与回测

```bash
python dxj_backtest.py
python ewj_backtest.py
python analyze_dxj_correlation.py
python analyze_ewj_correlation.py
python compare_japan_etfs.py
python analyze_japan_event_alignment.py
python analyze_ibs_fx_regime.py
python analyze_fxy_interactions.py
python analyze_condition_stability.py
python analyze_stable_cell_execution.py
python analyze_condition_specific_params.py
python analyze_parameter_walkforward.py
python build_signal_shortlist.py
```

## 执行层

### 每日信号

```bash
python japan_core_signal.py
python japan_core_signal.py --update
```

### 月度风控

```bash
python japan_core_risk_monitor.py
```

## 安装依赖

```bash
uv pip install yfinance pandas requests websocket-client numpy python-dateutil
```
