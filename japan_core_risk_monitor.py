"""
DXJ / EWJ Core Signal 的月度风险监控报告。

重点不是宏观大全，而是检查：
1. 当前状态与已完成交易
2. 核心候选最近 60-120 天的机会频率与收益表现
3. 当前 event / FXY 环境是否偏离研究里最有利的格子
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from analyze_condition_specific_params import evaluate_gap
from analyze_fxy_interactions import load_context, prepare_daily
from analyze_ibs_fx_regime import load_daily, run_ibs


MONTH = datetime.now().strftime("%Y-%m")
SAVE_FILE = "--no-save" not in sys.argv
REPORT_DIR = Path("docs/risk_reports")
REPORT_FILE = REPORT_DIR / f"japan_core_{MONTH}.md"
STATE_FILE = Path("japan_core_signal_state.json")
STATUS_FILE = Path("japan_core_signal_status.json")

CORE_CANDIDATES = [
    {
        "label": "DXJ Core IBS",
        "asset": "DXJ",
        "strategy": "IBS",
        "combo": "Cross-Hedge Divergence | Neutral",
        "entry_ibs": 0.30,
        "exit_ibs": 0.90,
        "max_hold": 5,
    },
    {
        "label": "EWJ Core IBS",
        "asset": "EWJ",
        "strategy": "IBS",
        "combo": "Cross-Hedge Divergence | Neutral",
        "entry_ibs": 0.25,
        "exit_ibs": 0.60,
        "max_hold": 2,
    },
]

MONITOR_CANDIDATES = [
    {
        "label": "EWJ Secondary IBS",
        "asset": "EWJ",
        "strategy": "IBS",
        "combo": "Shared Down Shock | Neutral",
        "entry_ibs": 0.25,
        "exit_ibs": 0.60,
        "max_hold": 2,
    },
    {
        "label": "DXJ Gap Watchlist",
        "asset": "DXJ",
        "strategy": "Gap",
        "combo": "Non-event | Neutral",
        "gap_threshold": -0.01,
        "hold_days": 5,
    },
]

report_lines: list[str] = []
alerts: list[tuple[str, str, str]] = []


def out(text: str = "") -> None:
    print(text)
    report_lines.append(text)


def md_cell(value: str) -> str:
    return value.replace("|", "\\|")


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"positions": {}, "trade_log": [], "last_processed_date": None}
    return json.loads(STATE_FILE.read_text())


def load_status() -> dict | None:
    if not STATUS_FILE.exists():
        return None
    return json.loads(STATUS_FILE.read_text())


def load_asset_daily(asset: str) -> pd.DataFrame:
    return prepare_daily(load_daily(f"{asset.lower()}_minute_data.csv"))


def fmt_pct(value: float) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{value:+.1f}%"


def fmt_avg(value: float) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{value:+.2f}%"


def combo_counts(ctx: pd.DataFrame, lookback: int = 60) -> pd.Series:
    recent = ctx.tail(lookback)
    return recent["event_fx_combo"].value_counts()


def recent_fxy_distribution(ctx: pd.DataFrame, lookback: int = 60) -> pd.Series:
    recent = ctx.tail(lookback)
    return recent["fxy_regime"].value_counts()


def summarize_candidate(candidate: dict, daily: pd.DataFrame, ctx: pd.DataFrame, lookback: int = 120) -> dict:
    recent_daily = daily.tail(lookback).copy()
    entry_mask = (ctx["event_fx_combo"] == candidate["combo"]).reindex(recent_daily.index).fillna(False)
    combo_hits = int(entry_mask.sum())

    if candidate["strategy"] == "IBS":
        summary = run_ibs(
            recent_daily,
            candidate["entry_ibs"],
            candidate["exit_ibs"],
            candidate["max_hold"],
            entry_mask=entry_mask,
        )
    else:
        summary = evaluate_gap(recent_daily, entry_mask, candidate["gap_threshold"], candidate["hold_days"])

    result = {
        "combo_hits": combo_hits,
        "n": 0,
        "wr": float("nan"),
        "total": float("nan"),
        "avg": float("nan"),
        "worst": float("nan"),
    }
    if summary is not None:
        result.update(summary)
    return result


def maybe_alert_candidate(candidate: dict, summary_120: dict, summary_60: dict) -> None:
    label = candidate["label"]
    if summary_120["combo_hits"] == 0:
        alerts.append(("YELLOW", "机会频率", f"{label} 最近 120 天没有出现目标格子"))
        return

    if summary_120["n"] > 0 and pd.notna(summary_120["total"]) and summary_120["total"] < 0:
        alerts.append(("RED", "策略衰减", f"{label} 最近 120 天总收益为 {summary_120['total']:+.1f}%"))
    elif summary_60["n"] > 0 and pd.notna(summary_60["avg"]) and summary_60["avg"] < 0:
        alerts.append(("YELLOW", "短期走弱", f"{label} 最近 60 天平均收益为 {summary_60['avg']:+.2f}%"))
    elif summary_60["combo_hits"] == 0:
        alerts.append(("YELLOW", "机会频率", f"{label} 最近 60 天没有出现目标格子"))


def render_perf_section(state: dict) -> None:
    out("## 一、状态与绩效\n")
    trades = state.get("trade_log", [])
    positions = state.get("positions", {})

    if trades:
        all_rets = [trade["ret"] for trade in trades]
        month_trades = [trade for trade in trades if trade.get("sell_date", "").startswith(MONTH)]
        wins = sum(1 for ret in all_rets if ret > 0)
        out("| 指标 | 数值 |")
        out("|------|------|")
        out(f"| 累计交易笔数 | {len(trades)} |")
        out(f"| 累计胜率 | {wins / len(trades) * 100:.0f}% ({wins}/{len(trades)}) |")
        out(f"| 累计收益 | {sum(all_rets):+.1f}% |")
        out(f"| 平均收益/笔 | {pd.Series(all_rets).mean():+.2f}% |")
        out(f"| 最大单笔亏损 | {pd.Series(all_rets).min():+.2f}% |")
        out()
        if month_trades:
            out(f"### 本月已完成交易 ({MONTH})\n")
            out("| 标的 | 买入日 | 卖出日 | 天数 | 收益 | 原因 |")
            out("|------|--------|--------|------|------|------|")
            for trade in month_trades:
                out(
                    f"| {trade['asset']} | {trade['buy_date']} | {trade['sell_date']} | "
                    f"{trade['days']} | {trade['ret']:+.2f}% | {trade['reason']} |"
                )
            out()
        else:
            out("本月无已完成交易。\n")
    else:
        out("暂无已完成交易。\n")

    active_positions = {asset: pos for asset, pos in positions.items() if pos}
    if active_positions:
        out("### 当前持仓\n")
        for asset, pos in active_positions.items():
            out(
                f"- {asset}: {pos['buy_date']} @ ${pos['buy_price']:.2f}, "
                f"已持有 {pos['days_held']} 天, 入场格子 `{pos['entry_combo']}`"
            )
        out()
    else:
        out("当前无持仓。\n")


def render_market_section(status: dict | None, ctx: pd.DataFrame, daily_map: dict[str, pd.DataFrame]) -> None:
    out("## 二、当前市场状态\n")
    latest_date = min(ctx.index.max(), *(daily.index.max() for daily in daily_map.values()))
    ctx_row = ctx.loc[latest_date]
    dxj_row = daily_map["DXJ"].loc[latest_date]
    ewj_row = daily_map["EWJ"].loc[latest_date]

    out("| 指标 | 数值 |")
    out("|------|------|")
    out(f"| 最新交易日 | {latest_date.date()} |")
    out(f"| Event Type | {ctx_row['event_type']} |")
    out(f"| FXY Regime | {ctx_row['fxy_regime']} |")
    out(f"| Event Combo | {md_cell(str(ctx_row['event_fx_combo']))} |")
    out(f"| DXJ 收盘 / IBS | ${dxj_row['Close']:.2f} / {dxj_row['ibs']:.3f} |")
    out(f"| EWJ 收盘 / IBS | ${ewj_row['Close']:.2f} / {ewj_row['ibs']:.3f} |")
    out()

    if status is not None:
        out("### 最近一次日频监控快照\n")
        out(f"- 快照日期: {status['trade_date']}")
        out(f"- Core 信号数: {len(status.get('signals', []))}")
        out(f"- Monitor 提示数: {len(status.get('monitor_notes', []))}")
        if status.get("monitor_notes"):
            for note in status["monitor_notes"]:
                out(f"- {note}")
        out()

    out("### 最近 60 天格子分布\n")
    out("| 格子 | 次数 |")
    out("|------|------|")
    for combo, count in combo_counts(ctx, 60).head(8).items():
        out(f"| {md_cell(str(combo))} | {count} |")
    out()

    out("### 最近 60 天 FXY Regime 分布\n")
    out("| Regime | 次数 |")
    out("|--------|------|")
    for regime, count in recent_fxy_distribution(ctx, 60).items():
        out(f"| {regime} | {count} |")
    out()


def render_candidate_section(ctx: pd.DataFrame, daily_map: dict[str, pd.DataFrame]) -> None:
    out("## 三、候选健康度\n")
    out("| 候选 | 口径 | 最近 60 天格子次数 | 最近 60 天交易数 | 最近 60 天总收益 | 最近 60 天均收益 | 最近 120 天格子次数 | 最近 120 天交易数 | 最近 120 天总收益 | 最近 120 天均收益 |")
    out("|------|------|-------------------|------------------|------------------|------------------|--------------------|-------------------|-------------------|-------------------|")

    for candidate in CORE_CANDIDATES + MONITOR_CANDIDATES:
        daily = daily_map[candidate["asset"]]
        summary_60 = summarize_candidate(candidate, daily, ctx, 60)
        summary_120 = summarize_candidate(candidate, daily, ctx, 120)

        maybe_alert_candidate(candidate, summary_120, summary_60)

        out(
            f"| {candidate['label']} | {md_cell(candidate['combo'])} | {summary_60['combo_hits']} | {int(summary_60['n'])} | "
            f"{fmt_pct(summary_60['total'])} | {fmt_avg(summary_60['avg'])} | {summary_120['combo_hits']} | {int(summary_120['n'])} | "
            f"{fmt_pct(summary_120['total'])} | {fmt_avg(summary_120['avg'])} |"
        )
    out()


def render_alerts() -> None:
    out("## 四、风险汇总\n")
    red_alerts = [alert for alert in alerts if alert[0] == "RED"]
    yellow_alerts = [alert for alert in alerts if alert[0] == "YELLOW"]

    if red_alerts:
        out(f"### RED 红色警报 ({len(red_alerts)} 个)\n")
        for _, category, message in red_alerts:
            out(f"- **[{category}]** {message}")
        out()

    if yellow_alerts:
        out(f"### YELLOW 黄色预警 ({len(yellow_alerts)} 个)\n")
        for _, category, message in yellow_alerts:
            out(f"- [{category}] {message}")
        out()

    if not red_alerts and not yellow_alerts:
        out("当前没有自动化红黄警报。\n")

    out("### 建议\n")
    if red_alerts:
        out("建议暂停新增 Core 仓位，先复核最近 120 天的条件表现。")
    elif yellow_alerts:
        out("保持运行，但应重点跟踪格子频率和短期收益变化。")
    else:
        out("Core 候选可继续运行。")
    out()


def main() -> None:
    out(f"# Japan Core Risk Report — {MONTH}")
    out(f"\n> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out()

    state = load_state()
    status = load_status()
    ctx = load_context()
    daily_map = {
        "DXJ": load_asset_daily("DXJ"),
        "EWJ": load_asset_daily("EWJ"),
    }

    render_perf_section(state)
    render_market_section(status, ctx, daily_map)
    render_candidate_section(ctx, daily_map)
    render_alerts()

    if SAVE_FILE:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_FILE.write_text("\n".join(report_lines), encoding="utf-8")
        print(f"\n{'=' * 60}")
        print(f"  报告已保存至: {REPORT_FILE}")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
