"""
DXJ 日线规律扫描。

当前先测试两类候选模式：
1. IBS 均值回归
2. 隔夜跳空后的修复/延续

脚本会输出控制台摘要，并生成 docs/03_dxj_strategy_research.md。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


TICKER = "DXJ"
CSV_FILE = Path("dxj_minute_data.csv")
DOC_FILE = Path("docs/03_dxj_strategy_research.md")


def load_daily() -> pd.DataFrame:
    df = pd.read_csv(CSV_FILE, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    if df["timestamp"].dt.hour.max() > 21:
        df["timestamp"] = (
            df["timestamp"]
            .dt.tz_localize("UTC")
            .dt.tz_convert("US/Eastern")
            .dt.tz_localize(None)
        )

    df = df.sort_values("timestamp").reset_index(drop=True)
    df.set_index("timestamp", inplace=True)
    df = df.between_time("09:30", "16:00").copy()

    daily = (
        df.resample("D")
        .agg(
            Open=("Open", "first"),
            High=("High", "max"),
            Low=("Low", "min"),
            Close=("Close", "last"),
            Volume=("Volume", "sum"),
        )
        .dropna()
    )
    daily["ret"] = daily["Close"].pct_change()
    daily["gap_pct"] = daily["Open"] / daily["Close"].shift(1) - 1
    daily["ibs"] = (daily["Close"] - daily["Low"]) / (daily["High"] - daily["Low"])
    daily["ma200"] = daily["Close"].rolling(200).mean()
    daily["above_ma200"] = daily["Close"] > daily["ma200"]
    return daily


def summarize_trades(trades: list[dict]) -> dict | None:
    if not trades:
        return None
    tdf = pd.DataFrame(trades)
    wins = int((tdf["ret"] > 0).sum())
    return {
        "n": len(tdf),
        "wr": wins / len(tdf) * 100,
        "total": tdf["ret"].sum() * 100,
        "avg": tdf["ret"].mean() * 100,
        "worst": tdf["ret"].min() * 100,
        "best": tdf["ret"].max() * 100,
        "avg_hold": tdf["days"].mean(),
        "_trades": trades,
    }


def run_ibs_strategy(
    daily: pd.DataFrame,
    ibs_buy: float,
    ibs_sell: float,
    max_hold: int,
    require_ma200: bool,
) -> dict | None:
    trades: list[dict] = []
    position: dict | None = None

    for idx, row in daily.iterrows():
        if position is not None:
            position["days"] += 1
            should_sell = row["ibs"] >= ibs_sell or position["days"] >= max_hold
            if should_sell:
                ret = row["Close"] / position["buy_price"] - 1
                trades.append(
                    {
                        "buy_date": position["buy_date"],
                        "sell_date": idx.strftime("%Y-%m-%d"),
                        "buy_price": position["buy_price"],
                        "sell_price": row["Close"],
                        "days": position["days"],
                        "ret": ret,
                        "reason": "IBS" if row["ibs"] >= ibs_sell else "EXP",
                    }
                )
                position = None
                continue

        if position is None:
            if pd.isna(row["ibs"]):
                continue
            if require_ma200 and (pd.isna(row["ma200"]) or not row["above_ma200"]):
                continue
            if row["ibs"] <= ibs_buy:
                position = {
                    "buy_date": idx.strftime("%Y-%m-%d"),
                    "buy_price": row["Close"],
                    "days": 0,
                }

    summary = summarize_trades(trades)
    if summary is None:
        return None
    summary.update(
        {
            "family": "IBS",
            "entry": f"IBS<={ibs_buy:.2f}",
            "exit": f"IBS>={ibs_sell:.2f}",
            "hold": max_hold,
            "filter": "MA200" if require_ma200 else "None",
        }
    )
    return summary


def run_gap_strategy(
    daily: pd.DataFrame,
    gap_threshold: float,
    hold_days: int,
    require_ma200: bool,
) -> dict | None:
    trades: list[dict] = []
    i = 1
    rows = daily.reset_index()

    while i < len(rows):
        row = rows.iloc[i]
        if require_ma200 and (pd.isna(row["ma200"]) or not row["above_ma200"]):
            i += 1
            continue

        if row["gap_pct"] <= gap_threshold:
            exit_i = min(i + hold_days, len(rows) - 1)
            exit_row = rows.iloc[exit_i]
            buy_price = row["Open"]
            sell_price = exit_row["Close"]
            trades.append(
                {
                    "buy_date": row["timestamp"].strftime("%Y-%m-%d"),
                    "sell_date": exit_row["timestamp"].strftime("%Y-%m-%d"),
                    "buy_price": buy_price,
                    "sell_price": sell_price,
                    "days": hold_days + 1,
                    "ret": sell_price / buy_price - 1,
                    "reason": "gap",
                }
            )
            i = exit_i + 1
        else:
            i += 1

    summary = summarize_trades(trades)
    if summary is None:
        return None
    summary.update(
        {
            "family": "Gap",
            "entry": f"Gap<={gap_threshold * 100:.1f}%",
            "exit": f"Hold {hold_days}d",
            "hold": hold_days + 1,
            "filter": "MA200" if require_ma200 else "None",
        }
    )
    return summary


def build_report(daily: pd.DataFrame, ibs_results: pd.DataFrame, gap_results: pd.DataFrame) -> str:
    best_ibs = ibs_results.iloc[0] if not ibs_results.empty else None
    best_gap = gap_results.iloc[0] if not gap_results.empty else None

    observations = []
    if best_ibs is not None and best_gap is not None:
        if best_ibs["total"] > best_gap["total"]:
            observations.append(f"在当前样本里，{TICKER} 的 IBS 家族总收益优于简单跳空策略，说明日内收盘位置可能比单纯的隔夜缺口更有信息量。")
        else:
            observations.append(f"在当前样本里，{TICKER} 的隔夜跳空策略优于 IBS 家族，说明它更值得从跨时区定价与缺口修复角度继续研究。")

    if best_gap is not None and best_gap["avg"] > 0:
        observations.append("跳空后的持有窗口值得继续细分，下一步应区分同日修复、1-3 日修复和事件驱动型继续下跌。")

    if best_ibs is not None and best_ibs["filter"] == "MA200":
        observations.append(f"趋势过滤进入 {TICKER} 的最优组合，说明它可能更适合趋势中的回撤，而不是纯逆势均值回归。")

    lines = [
        f"# {TICKER} 策略规律研究（第一轮）",
        "",
        f"> 生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 样本区间: {daily.index.min().date()} -> {daily.index.max().date()}",
        f"> 日线样本: {len(daily)} 天",
        "",
        "## 一、本轮测试范围",
        "",
        "- IBS 均值回归：收盘接近当日低点时买入，收盘重新走强时卖出",
        "- 隔夜跳空策略：开盘相对前收大幅低开后买入，观察后续修复",
        "- 这些只是第一轮候选模式，不代表最终策略",
        "",
        "## 二、IBS 扫描 Top 10",
        "",
        "| 入场 | 出场 | 最大持有 | 过滤器 | 笔数 | 胜率 | 总收益 | 均收益 | 最大亏损 | 平均持有 |",
        "| ---- | ---- | -------- | ------ | ---- | ---- | ------ | ------ | -------- | -------- |",
    ]

    if ibs_results.empty:
        lines.append("| 无结果 | - | - | - | - | - | - | - | - | - |")
    else:
        for _, row in ibs_results.head(10).iterrows():
            lines.append(
                f"| {row['entry']} | {row['exit']} | {int(row['hold'])}d | {row['filter']} | {int(row['n'])} | "
                f"{row['wr']:.0f}% | {row['total']:+.1f}% | {row['avg']:+.2f}% | {row['worst']:+.2f}% | {row['avg_hold']:.1f}d |"
            )

    lines.extend(
        [
            "",
            "## 三、隔夜跳空策略 Top 10",
            "",
            "| 入场 | 出场 | 持有窗口 | 过滤器 | 笔数 | 胜率 | 总收益 | 均收益 | 最大亏损 | 平均持有 |",
            "| ---- | ---- | -------- | ------ | ---- | ---- | ------ | ------ | -------- | -------- |",
        ]
    )

    if gap_results.empty:
        lines.append("| 无结果 | - | - | - | - | - | - | - | - | - |")
    else:
        for _, row in gap_results.head(10).iterrows():
            lines.append(
                f"| {row['entry']} | {row['exit']} | {int(row['hold'])}d | {row['filter']} | {int(row['n'])} | "
                f"{row['wr']:.0f}% | {row['total']:+.1f}% | {row['avg']:+.2f}% | {row['worst']:+.2f}% | {row['avg_hold']:.1f}d |"
            )

    lines.extend(
        [
            "",
            "## 四、第一轮观察",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in observations] or ["- 当前结果只足够做方向筛选，还不足以下最终策略结论。"])
    lines.extend(
        [
            "",
            "下一步建议：",
            "- 把跳空样本按事件类型分类，区分汇率窗口和日本 beta 冲击",
            "- 在 IBS 和跳空之外，继续测“趋势中的回撤买入”而不是纯逆势抄底",
            "- 把最优组合转成分钟级执行逻辑，确认实际可成交性",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    daily = load_daily()

    ibs_results = []
    for ibs_buy in [0.10, 0.15, 0.20, 0.25, 0.30]:
        for ibs_sell in [0.60, 0.70, 0.80, 0.90]:
            if ibs_sell <= ibs_buy:
                continue
            for max_hold in [1, 2, 3, 5, 10]:
                for require_ma200 in [False, True]:
                    summary = run_ibs_strategy(daily, ibs_buy, ibs_sell, max_hold, require_ma200)
                    if summary is not None:
                        ibs_results.append(summary)

    gap_results = []
    for gap_threshold in [-0.01, -0.015, -0.02, -0.025, -0.03]:
        for hold_days in [0, 1, 2, 3, 5]:
            for require_ma200 in [False, True]:
                summary = run_gap_strategy(daily, gap_threshold, hold_days, require_ma200)
                if summary is not None:
                    gap_results.append(summary)

    ibs_df = pd.DataFrame(ibs_results).sort_values(["total", "avg", "wr"], ascending=False).reset_index(drop=True)
    gap_df = pd.DataFrame(gap_results).sort_values(["total", "avg", "wr"], ascending=False).reset_index(drop=True)

    report = build_report(daily, ibs_df, gap_df)
    DOC_FILE.write_text(report, encoding="utf-8")

    print(f"Wrote strategy scan to {DOC_FILE}")
    if not ibs_df.empty:
        top_ibs = ibs_df.iloc[0]
        print(
            f"Best IBS: {top_ibs['entry']} / {top_ibs['exit']} / {int(top_ibs['hold'])}d / "
            f"{top_ibs['filter']} -> total {top_ibs['total']:+.1f}%"
        )
    if not gap_df.empty:
        top_gap = gap_df.iloc[0]
        print(
            f"Best Gap: {top_gap['entry']} / {top_gap['exit']} / {int(top_gap['hold'])}d / "
            f"{top_gap['filter']} -> total {top_gap['total']:+.1f}%"
        )


if __name__ == "__main__":
    main()
