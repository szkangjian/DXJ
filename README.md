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

## 研究文档

### 方法总纲

| 文件 | 内容 |
| ---- | ---- |
| [docs/00_general_research_framework.md](docs/00_general_research_framework.md) | 脱离具体标的的通用研究框架 |
| [docs/00_dxj_research_framework.md](docs/00_dxj_research_framework.md) | 日本 ETF 这条线的落地研究框架 |

### 单标的研究

| 文件 | 内容 |
| ---- | ---- |
| [docs/01_dxj_research.md](docs/01_dxj_research.md) | DXJ 资产画像 |
| [docs/01_ewj_research.md](docs/01_ewj_research.md) | EWJ 资产画像 |
| [docs/02_dxj_event_drivers.md](docs/02_dxj_event_drivers.md) | DXJ 驱动归因 |
| [docs/02_ewj_event_drivers.md](docs/02_ewj_event_drivers.md) | EWJ 驱动归因 |
| [docs/03_dxj_strategy_research.md](docs/03_dxj_strategy_research.md) | DXJ 策略研究 |
| [docs/03_ewj_strategy_research.md](docs/03_ewj_strategy_research.md) | EWJ 策略研究 |

### 联合研究与执行

| 文件 | 内容 |
| ---- | ---- |
| [docs/04_dxj_ewj_tax_analysis.md](docs/04_dxj_ewj_tax_analysis.md) | IB 交易下的美国居民 vs 非居民税务说明 |
| [docs/05_dxj_strategy_playbook.md](docs/05_dxj_strategy_playbook.md) | DXJ/EWJ 当前策略操作手册 |
| [docs/06_dxj_execution_log.md](docs/06_dxj_execution_log.md) | 执行与复盘日志模板 |
| [docs/07_dxj_ewj_comparison.md](docs/07_dxj_ewj_comparison.md) | DXJ vs EWJ 核心差异 |
| [docs/08_dxj_ewj_event_alignment.md](docs/08_dxj_ewj_event_alignment.md) | 事件对齐与相对收益拆解 |
| [docs/09_dxj_ewj_ibs_fx_regime.md](docs/09_dxj_ewj_ibs_fx_regime.md) | IBS 与 FXY regime |
| [docs/10_fxy_conditioning_interactions.md](docs/10_fxy_conditioning_interactions.md) | FXY × 事件类型 × 策略交互 |
| [docs/11_condition_stability.md](docs/11_condition_stability.md) | 条件格子稳定性检查 |
| [docs/12_stable_cell_execution.md](docs/12_stable_cell_execution.md) | 执行敏感性验证 |
| [docs/13_condition_specific_params.md](docs/13_condition_specific_params.md) | 条件参数扫描 |
| [docs/14_parameter_walkforward.md](docs/14_parameter_walkforward.md) | 半样本样本外验证 |
| [docs/15_signal_shortlist.md](docs/15_signal_shortlist.md) | 候选清单与推进优先级 |
| [docs/16_japan_core_signal_engine.md](docs/16_japan_core_signal_engine.md) | 日频信号引擎说明 |
| [docs/risk_reports/japan_core_2026-03.md](docs/risk_reports/japan_core_2026-03.md) | 最新日本 Core 月度风控报告 |

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
