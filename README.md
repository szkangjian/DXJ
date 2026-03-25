# EWY 量化交易研究

iShares MSCI South Korea ETF (EWY) 的量化分析与交易策略研究项目。

基于 219,296 条分钟级数据（2024-03 → 2026-03），从因子分析、事件驱动研究到可执行策略的完整研究链。

## 核心发现

- **IBS 策略**：83% 胜率，均收益 +2.14%/笔，平均持有 2.3 天
- **跌幅触发策略**：73% 胜率，盘中跌 >3% 买入，反弹 +2.5% 卖出
- **与事件类型无关**：关税、AI 恐慌、伊朗战争 — 不管什么原因跌，短期都反弹
- **策略前提**：EWY 处于半导体/AI 上升通道中（需持续监控）

## 策略研究文档

文档按阅读顺序编号，位于 `docs/` 目录：

| # | 文件 | 内容概要 |
| - | ---- | -------- |
| 01 | [EWY 底层研究](docs/01_ewy_research.md) | 价格历史、Spread、波动率、极端事件、股息、相关性分析 |
| 02 | [外部事件驱动分析](docs/02_ewy_event_drivers.md) | 2025-2026 共 44 个异动日逐一溯源，分类为半导体/AI、地缘政治等 |
| 03 | [交易策略研究](docs/03_ewy_strategy_research.md) | IBS、跌幅触发、RSI、BB 四种策略回测，参数扫描，量价分析 |
| 04 | [税务分析](docs/04_ewy_tax_analysis.md) | NRA vs 美国居民税务影响，Wash Sale 处理 |
| 05 | [**策略操作手册 (Playbook)**](docs/05_ewy_strategy_playbook.md) | **核心纲要**。IBS + 跌幅触发双策略、仓位管理、风控铁律、执行清单 |
| 06 | [执行追踪日志模板](docs/06_ewy_execution_log.md) | 交易记录、月度汇总、风控指标追踪、策略衰减对比 |

## 数据管道

### 获取历史数据

```bash
# 从 Polygon.io 下载分钟级 K 线（2024-03 至今）
python download_ewy_polygon.py
```

### 每日更新

```bash
# 收盘后从 Yahoo Finance 补充当日数据
python update_ewy_today.py
```

### 盘中实时监控

```bash
# Finnhub WebSocket 实时监控 + 策略信号提醒
python realtime_ewy.py
```

## 策略工具

### 每日信号

```bash
# 收盘后检查 IBS 信号
python ewy_signal.py
```

### 月度风控报告

```bash
# 自动拉取 FRED/yfinance 数据，生成风控指标报告
python ewy_risk_monitor.py
```

## 配置

将 `config.py` 填入 API Key：
- **Polygon.io**：历史分钟数据下载
- **Finnhub.io**：实时 WebSocket 数据

## 安装依赖

```bash
uv pip install yfinance pandas requests websocket-client numpy python-dateutil
```

## 项目结构

```
EWY/
├── docs/                          # 研究文档
│   ├── 01_ewy_research.md        # 因子分析
│   ├── 02_ewy_event_drivers.md   # 事件驱动
│   ├── 03_ewy_strategy_research.md # 策略回测
│   ├── 04_ewy_tax_analysis.md    # 税务分析
│   ├── 05_ewy_strategy_playbook.md # 操作手册
│   ├── 06_ewy_execution_log.md   # 交易日志模板
│   └── risk_reports/             # 月度风控报告
├── download_ewy_polygon.py       # Polygon 历史数据下载
├── update_ewy_today.py           # Yahoo Finance 每日更新
├── realtime_ewy.py               # 盘中实时监控 + 策略提醒
├── ewy_signal.py                 # 每日 IBS 信号生成
├── ewy_risk_monitor.py           # 月度风控指标报告
├── ewy_backtest.py               # 因子分析回测
├── ewy_intraday_backtest.py      # 跌幅触发策略参数扫描
├── ewy_filter_backtest.py        # 过滤器对比测试
├── backtest_mean_reversion.py    # 均值回归日线回测
├── backtest_mean_reversion_intraday.py # 均值回归分钟级回测
├── analyze_ewy_*.py              # 各类专题分析脚本
├── config.py                     # API 密钥配置
└── ewy_minute_data.csv           # 分钟级 OHLCV 数据
```
