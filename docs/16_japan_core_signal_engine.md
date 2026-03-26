# 日本 ETF Core Signal Engine

> 生成目的: 把研究层已经筛出来的 `Core` 候选落成可执行的日频信号脚本。

## 当前执行范围

脚本入口: [japan_core_signal.py](/Users/patrick/Projects/DXJ/japan_core_signal.py)

操作手册: [docs/05_dxj_strategy_playbook.md](/Users/patrick/Projects/DXJ/docs/05_dxj_strategy_playbook.md)

执行日志模板: [docs/06_dxj_execution_log.md](/Users/patrick/Projects/DXJ/docs/06_dxj_execution_log.md)

当前只自动执行两个 `Core` 候选：

| 标的 | 策略 | 入场条件 | 出场条件 |
| ---- | ---- | -------- | -------- |
| DXJ | IBS | `event_fx_combo = Cross-Hedge Divergence \| Neutral` 且 `IBS <= 0.30` | `IBS >= 0.90` 或持有 `5` 天 |
| EWJ | IBS | `event_fx_combo = Cross-Hedge Divergence \| Neutral` 且 `IBS <= 0.25` | `IBS >= 0.60` 或持有 `2` 天 |

## Monitor Only

下列条件目前只做提示，不自动入场：

| 分类 | 条件 |
| ---- | ---- |
| Secondary | `EWJ \| IBS \| Shared Down Shock \| Neutral` |
| Watchlist | `DXJ \| Gap \| Non-event \| Neutral` |

## 用法

```bash
python japan_core_signal.py
python japan_core_signal.py --update
```

`--update` 会先运行：
- [update_dxj_today.py](/Users/patrick/Projects/DXJ/update_dxj_today.py)
- [update_ewj_today.py](/Users/patrick/Projects/DXJ/update_ewj_today.py)

## 状态文件

状态保存在 [japan_core_signal_state.json](/Users/patrick/Projects/DXJ/japan_core_signal_state.json)。

最近一次监控快照会写入 [japan_core_signal_status.json](/Users/patrick/Projects/DXJ/japan_core_signal_status.json)。

当前记录内容包括：
- `positions`
- `trade_log`
- `last_processed_date`

`last_processed_date` 用来避免同一交易日重复运行时把持仓天数和交易记录重复累加。

## 设计原则

- 研究层和执行层共用相同的 `FXY regime` 与 `event_type` 定义
- 当前不继续做条件化参数拆分，统一沿用样本外验证后保留下来的统一参数
- 先做收盘后日频执行，再决定是否扩展到更细的盘中监控

## 月度风控

月度风险报告脚本: [japan_core_risk_monitor.py](/Users/patrick/Projects/DXJ/japan_core_risk_monitor.py)

税务说明: [docs/04_dxj_ewj_tax_analysis.md](/Users/patrick/Projects/DXJ/docs/04_dxj_ewj_tax_analysis.md)

```bash
python japan_core_risk_monitor.py
```

报告会写入 `docs/risk_reports/japan_core_YYYY-MM.md`。
