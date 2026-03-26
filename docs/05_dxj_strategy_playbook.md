# DXJ / EWJ 策略操作手册

> 版本: v1.0 | 最后更新: 2026-03-25
>
> 当前手册只覆盖已经进入执行层的日本 ETF 框架，不再继承旧 `EWY` 的参数或结论。

## 一、当前执行范围

当前自动执行的只有两个 `Core` 候选：

| 标的 | 类型 | 入场条件 | 出场条件 |
| ---- | ---- | -------- | -------- |
| DXJ | Core IBS | `Cross-Hedge Divergence \| Neutral` 且 `IBS <= 0.30` | `IBS >= 0.90` 或持有 `5` 天 |
| EWJ | Core IBS | `Cross-Hedge Divergence \| Neutral` 且 `IBS <= 0.25` | `IBS >= 0.60` 或持有 `2` 天 |

仅做监控、不自动入场的条件：

| 类型 | 条件 |
| ---- | ---- |
| Secondary | `EWJ \| IBS \| Shared Down Shock \| Neutral` |
| Watchlist | `DXJ \| Gap \| Non-event \| Neutral` |

## 二、核心原则

### 2.1 不继续做条件化参数拆分

研究已经完成：
- 条件参数扫描
- 稳定性检查
- 执行敏感性测试
- 半样本样本外验证

当前结论是：
- 不把格子继续拆成独立参数策略
- 统一沿用样本外验证后保留下来的统一参数

参考：
- [docs/13_condition_specific_params.md](/Users/patrick/Projects/DXJ/docs/13_condition_specific_params.md)
- [docs/14_parameter_walkforward.md](/Users/patrick/Projects/DXJ/docs/14_parameter_walkforward.md)

### 2.2 只在“格子 + 指标”同时满足时入场

当前执行框架不是单纯做 IBS，而是：
- 先看 `event_fx_combo`
- 再看 `IBS`

如果只有 `IBS` 满足，但格子不对：
- 不入场

如果格子满足，但 `IBS` 没到：
- 也不入场

### 2.3 统一以收盘后日频执行

当前执行层默认：
- 收盘后运行
- 用 [japan_core_signal.py](/Users/patrick/Projects/DXJ/japan_core_signal.py) 生成信号
- 先不扩到实时盘中自动化

## 三、策略定义

### 3.1 DXJ Core IBS

| 项目 | 规则 |
| ---- | ---- |
| 标的 | `DXJ` |
| 条件格子 | `Cross-Hedge Divergence \| Neutral` |
| 买入 | `IBS <= 0.30` |
| 卖出 | `IBS >= 0.90` |
| 最长持有 | `5` 天 |

### 3.2 EWJ Core IBS

| 项目 | 规则 |
| ---- | ---- |
| 标的 | `EWJ` |
| 条件格子 | `Cross-Hedge Divergence \| Neutral` |
| 买入 | `IBS <= 0.25` |
| 卖出 | `IBS >= 0.60` |
| 最长持有 | `2` 天 |

### 3.3 Monitor Only

以下条件只做观察：
- `EWJ | IBS | Shared Down Shock | Neutral`
- `DXJ | Gap | Non-event | Neutral`

它们的作用是：
- 继续积累样本
- 帮助判断市场 regime 是否变化
- 但当前不提高到自动执行优先级

## 四、仓位与执行规则

### 4.1 仓位

- `DXJ` 与 `EWJ` 分开管理
- 每个标的最多 `1` 笔 Core 持仓
- 不同标的可以同时有仓
- 不加杠杆
- 不做同标的加仓或金字塔

### 4.2 执行纪律

- 同一交易日只处理一次
- 如果脚本重复运行，不应重复累加持仓天数或重复写交易记录
- 当前状态文件：
  - [japan_core_signal_state.json](/Users/patrick/Projects/DXJ/japan_core_signal_state.json)
  - [japan_core_signal_status.json](/Users/patrick/Projects/DXJ/japan_core_signal_status.json)

## 五、风险控制

### 5.1 当前硬规则

- 只有 `Core` 候选允许自动入场
- `Secondary` 与 `Watchlist` 只允许监控
- 如果月度风控出现 `RED`，暂停新增 Core 仓位，先做人工复核

### 5.2 当前软规则

以下情况需要提高警惕，但不自动停机：
- 某个 Core 候选最近 `60` 天平均收益转负
- 目标格子最近 `60-120` 天出现频率明显下降
- 市场长期偏离 `Neutral` regime

参考：
- [docs/15_signal_shortlist.md](/Users/patrick/Projects/DXJ/docs/15_signal_shortlist.md)
- [docs/16_japan_core_signal_engine.md](/Users/patrick/Projects/DXJ/docs/16_japan_core_signal_engine.md)
- [docs/risk_reports/japan_core_2026-03.md](/Users/patrick/Projects/DXJ/docs/risk_reports/japan_core_2026-03.md)

## 六、工具链

### 6.1 每日更新

```bash
python update_dxj_today.py
python update_ewj_today.py
```

### 6.2 每日信号

```bash
python japan_core_signal.py
python japan_core_signal.py --update
```

### 6.3 月度风控

```bash
python japan_core_risk_monitor.py
```

## 七、税务速览

简版结论：

- 美国税务居民：主问题是 `short-term capital gains + wash sale`
- 非美国税务居民：主问题通常是 `W-8BEN + dividend withholding + 183-day rule + estate tax`

完整说明见：
- [docs/04_dxj_ewj_tax_analysis.md](/Users/patrick/Projects/DXJ/docs/04_dxj_ewj_tax_analysis.md)

## 八、执行检查清单

### 每日

- [ ] 如有需要，先更新 `DXJ / EWJ` 当日分钟数据
- [ ] 运行 `python japan_core_signal.py`
- [ ] 检查当天 `event_fx_combo`
- [ ] 检查是否触发 `Core` 入场/出场
- [ ] 如有交易，记录到 [docs/06_dxj_execution_log.md](/Users/patrick/Projects/DXJ/docs/06_dxj_execution_log.md)

### 每周

- [ ] 复查 `Monitor Only` 条件是否频繁激活
- [ ] 复查 `japan_core_signal_status.json`

### 每月

- [ ] 运行 `python japan_core_risk_monitor.py`
- [ ] 复查最近 `60-120` 天候选健康度
- [ ] 若有 `RED`，暂停新增 Core 仓位并做人工复盘
