"""
把 FXY 当成条件分层变量，而不是方向过滤器。

输出：
1. IBS x FXY regime
2. Gap x FXY regime
3. IBS x Event Type
4. Gap x Event Type
5. Strategy x FXY regime x Event Type 的联合条件格子
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from analyze_ibs_fx_regime import find_best_ibs, load_daily, load_fxy_returns


DOC_FILE = Path("docs/10_fxy_conditioning_interactions.md")
FX_MOVE = 0.008
SPREAD_MOVE = 0.0075
MARKET_MOVE = 0.012
STRESS_MOVE = 0.015


def fxy_regime(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "Unknown"
    if value >= FX_MOVE:
        return "Yen Strength"
    if value <= -FX_MOVE:
        return "Yen Weakness"
    return "Neutral"


def event_type(dxj_ret: float | None, ewj_ret: float | None) -> str:
    if pd.isna(dxj_ret) or pd.isna(ewj_ret):
        return "Non-event"

    spread = dxj_ret - ewj_ret
    if abs(dxj_ret) >= STRESS_MOVE and abs(ewj_ret) < 0.01:
        return "DXJ-only Stress"
    if abs(ewj_ret) >= STRESS_MOVE and abs(dxj_ret) < 0.01:
        return "EWJ-only Stress"
    if abs(spread) >= SPREAD_MOVE:
        return "Cross-Hedge Divergence"
    if dxj_ret <= -MARKET_MOVE and ewj_ret <= -MARKET_MOVE:
        return "Shared Down Shock"
    if dxj_ret >= MARKET_MOVE and ewj_ret >= MARKET_MOVE:
        return "Shared Up Shock"
    return "Non-event"


def load_context() -> pd.DataFrame:
    dxj_daily = load_daily("dxj_minute_data.csv")[["ret"]].rename(columns={"ret": "DXJ"})
    ewj_daily = load_daily("ewj_minute_data.csv")[["ret"]].rename(columns={"ret": "EWJ"})
    fxy = load_fxy_returns().to_frame()

    ctx = dxj_daily.join(ewj_daily, how="inner").join(fxy, how="left")
    ctx["fxy_regime"] = ctx["FXY"].apply(fxy_regime)
    ctx["event_type"] = [event_type(dxj, ewj) for dxj, ewj in zip(ctx["DXJ"], ctx["EWJ"], strict=True)]
    ctx["event_fx_combo"] = ctx["event_type"] + " | " + ctx["fxy_regime"]
    return ctx


def prepare_daily(daily: pd.DataFrame) -> pd.DataFrame:
    prepared = daily.copy()
    prepared["gap_pct"] = prepared["Open"] / prepared["Close"].shift(1) - 1
    return prepared


def run_ibs_trades(asset: str, daily: pd.DataFrame, ibs_buy: float, ibs_sell: float, max_hold: int) -> pd.DataFrame:
    trades: list[dict] = []
    position: dict | None = None

    for idx, row in daily.iterrows():
        if position is not None:
            position["days"] += 1
            if row["ibs"] >= ibs_sell or position["days"] >= max_hold:
                trades.append(
                    {
                        "asset": asset,
                        "strategy": "IBS",
                        "entry_date": position["entry_date"],
                        "exit_date": idx,
                        "days": position["days"],
                        "ret": row["Close"] / position["buy_price"] - 1,
                    }
                )
                position = None
                continue

        if position is None and pd.notna(row["ibs"]) and row["ibs"] <= ibs_buy:
            position = {
                "entry_date": idx,
                "buy_price": row["Close"],
                "days": 0,
            }

    return pd.DataFrame(trades)


def find_best_gap(daily: pd.DataFrame) -> dict:
    rows = daily.reset_index()
    results = []

    for gap_threshold in [-0.01, -0.015, -0.02, -0.025, -0.03]:
        for hold_days in [0, 1, 2, 3, 5]:
            trades = []
            i = 1
            while i < len(rows):
                row = rows.iloc[i]
                if row["gap_pct"] <= gap_threshold:
                    exit_i = min(i + hold_days, len(rows) - 1)
                    exit_row = rows.iloc[exit_i]
                    trades.append(exit_row["Close"] / row["Open"] - 1)
                    i = exit_i + 1
                else:
                    i += 1
            if trades:
                s = pd.Series(trades)
                results.append(
                    {
                        "gap_threshold": gap_threshold,
                        "hold_days": hold_days,
                        "n": len(s),
                        "wr": float((s > 0).mean() * 100),
                        "total": float(s.sum() * 100),
                        "avg": float(s.mean() * 100),
                    }
                )

    return pd.DataFrame(results).sort_values(["total", "avg", "wr"], ascending=False).iloc[0].to_dict()


def run_gap_trades(asset: str, daily: pd.DataFrame, gap_threshold: float, hold_days: int) -> pd.DataFrame:
    rows = daily.reset_index()
    trades: list[dict] = []
    i = 1

    while i < len(rows):
        row = rows.iloc[i]
        if row["gap_pct"] <= gap_threshold:
            exit_i = min(i + hold_days, len(rows) - 1)
            exit_row = rows.iloc[exit_i]
            trades.append(
                {
                    "asset": asset,
                    "strategy": "Gap",
                    "entry_date": row["timestamp"],
                    "exit_date": exit_row["timestamp"],
                    "days": hold_days + 1,
                    "ret": exit_row["Close"] / row["Open"] - 1,
                }
            )
            i = exit_i + 1
        else:
            i += 1

    return pd.DataFrame(trades)


def attach_context(trades: pd.DataFrame, ctx: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades
    enriched = trades.copy()
    enriched["entry_date"] = pd.to_datetime(enriched["entry_date"])
    joined = enriched.merge(
        ctx[["FXY", "fxy_regime", "event_type"]],
        left_on="entry_date",
        right_index=True,
        how="left",
    )
    joined["fxy_regime"] = joined["fxy_regime"].fillna("Unknown")
    joined["event_type"] = joined["event_type"].fillna("Non-event")
    joined["event_fx_combo"] = joined["event_type"] + " | " + joined["fxy_regime"]
    return joined


def summarize(trades: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()

    summary = (
        trades.groupby(group_cols)
        .agg(
            n=("ret", "size"),
            wr=("ret", lambda s: (s > 0).mean() * 100),
            total=("ret", lambda s: s.sum() * 100),
            avg=("ret", lambda s: s.mean() * 100),
            worst=("ret", lambda s: s.min() * 100),
            avg_hold=("days", "mean"),
        )
        .reset_index()
    )
    return summary.sort_values(["total", "avg", "wr"], ascending=False)


def add_strategy_params_row(params: dict, label: str) -> str:
    if label == "IBS":
        return f"IBS<={params['ibs_buy']:.2f} / IBS>={params['ibs_sell']:.2f} / {int(params['max_hold'])}d"
    return f"Gap<={params['gap_threshold']*100:.1f}% / Hold {int(params['hold_days'])}d"


def build_report(
    dxj_ibs_params: dict,
    ewj_ibs_params: dict,
    dxj_gap_params: dict,
    ewj_gap_params: dict,
    trades: pd.DataFrame,
) -> str:
    by_fxy = summarize(trades, ["asset", "strategy", "fxy_regime"])
    by_event = summarize(trades, ["asset", "strategy", "event_type"])
    by_combo = summarize(trades, ["asset", "strategy", "event_fx_combo"])
    combo_filtered = by_combo[by_combo["n"] >= 3].copy()

    observations = []

    dxj_ibs_strength = by_fxy[(by_fxy["asset"] == "DXJ") & (by_fxy["strategy"] == "IBS") & (by_fxy["fxy_regime"] == "Yen Strength")]
    dxj_ibs_neutral = by_fxy[(by_fxy["asset"] == "DXJ") & (by_fxy["strategy"] == "IBS") & (by_fxy["fxy_regime"] == "Neutral")]
    if not dxj_ibs_strength.empty and not dxj_ibs_neutral.empty and dxj_ibs_strength.iloc[0]["avg"] > dxj_ibs_neutral.iloc[0]["avg"]:
        observations.append("DXJ 的 IBS 在日元走强环境下平均单笔收益高于中性环境，说明 FXY 更适合做条件分层，而不是简单屏蔽。")

    ewj_gap_div = by_event[(by_event["asset"] == "EWJ") & (by_event["strategy"] == "Gap") & (by_event["event_type"] == "Cross-Hedge Divergence")]
    if not ewj_gap_div.empty and ewj_gap_div.iloc[0]["avg"] > 0:
        observations.append("EWJ 的 Gap 信号在“Cross-Hedge Divergence”类事件里仍为正收益，但强度低于 IBS，说明缺口修复不是其核心模式。")

    dxj_gap_div_strength = combo_filtered[
        (combo_filtered["asset"] == "DXJ")
        & (combo_filtered["strategy"] == "Gap")
        & (combo_filtered["event_fx_combo"] == "Cross-Hedge Divergence | Yen Strength")
    ]
    if not dxj_gap_div_strength.empty:
        observations.append("DXJ 的 Gap 在“Cross-Hedge Divergence | Yen Strength”格子里有独立表现，后续值得做成专门子样本。")

    ewj_ibs_shared_down = combo_filtered[
        (combo_filtered["asset"] == "EWJ")
        & (combo_filtered["strategy"] == "IBS")
        & (combo_filtered["event_fx_combo"] == "Shared Down Shock | Neutral")
    ]
    if not ewj_ibs_shared_down.empty:
        observations.append("EWJ 的 IBS 在“Shared Down Shock | Neutral”格子里值得重点观察，这更接近纯日本 beta 冲击后的修复。")

    lines = [
        "# FXY 作为条件分层变量的交互研究",
        "",
        f"> 生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> FXY Regime: `FXY >= {FX_MOVE*100:.2f}%` 为 Yen Strength, `FXY <= -{FX_MOVE*100:.2f}%` 为 Yen Weakness",
        f"> Event Type 独立于 FXY 方向，避免把汇率直接塞回事件分类。",
        "",
        "## 一、使用的基础信号参数",
        "",
        "| 标的 | IBS 参数 | Gap 参数 |",
        "| ---- | -------- | -------- |",
        f"| DXJ | {add_strategy_params_row(dxj_ibs_params, 'IBS')} | {add_strategy_params_row(dxj_gap_params, 'Gap')} |",
        f"| EWJ | {add_strategy_params_row(ewj_ibs_params, 'IBS')} | {add_strategy_params_row(ewj_gap_params, 'Gap')} |",
        "",
        "## 二、策略 x FXY Regime",
        "",
        "| 标的 | 策略 | FXY Regime | 笔数 | 胜率 | 总收益 | 均收益 | 最大亏损 | 平均持有 |",
        "| ---- | ---- | ---------- | ---- | ---- | ------ | ------ | -------- | -------- |",
    ]

    for _, row in by_fxy.iterrows():
        lines.append(
            f"| {row['asset']} | {row['strategy']} | {row['fxy_regime']} | {int(row['n'])} | {row['wr']:.0f}% | "
            f"{row['total']:+.1f}% | {row['avg']:+.2f}% | {row['worst']:+.2f}% | {row['avg_hold']:.1f}d |"
        )

    lines.extend(
        [
            "",
            "## 三、策略 x Event Type",
            "",
            "| 标的 | 策略 | Event Type | 笔数 | 胜率 | 总收益 | 均收益 | 最大亏损 | 平均持有 |",
            "| ---- | ---- | ---------- | ---- | ---- | ------ | ------ | -------- | -------- |",
        ]
    )

    for _, row in by_event.iterrows():
        lines.append(
            f"| {row['asset']} | {row['strategy']} | {row['event_type']} | {int(row['n'])} | {row['wr']:.0f}% | "
            f"{row['total']:+.1f}% | {row['avg']:+.2f}% | {row['worst']:+.2f}% | {row['avg_hold']:.1f}d |"
        )

    lines.extend(
        [
            "",
            "## 四、策略 x Event Type x FXY Regime",
            "",
            "只保留样本数 >= 3 的格子，避免极小样本误导。",
            "",
            "| 标的 | 策略 | 联合条件 | 笔数 | 胜率 | 总收益 | 均收益 | 最大亏损 | 平均持有 |",
            "| ---- | ---- | -------- | ---- | ---- | ------ | ------ | -------- | -------- |",
        ]
    )

    if combo_filtered.empty:
        lines.append("| 无足够样本 | - | - | - | - | - | - | - | - |")
    else:
        for _, row in combo_filtered.iterrows():
            lines.append(
                f"| {row['asset']} | {row['strategy']} | {row['event_fx_combo']} | {int(row['n'])} | {row['wr']:.0f}% | "
                f"{row['total']:+.1f}% | {row['avg']:+.2f}% | {row['worst']:+.2f}% | {row['avg_hold']:.1f}d |"
            )

    lines.extend(
        [
            "",
            "## 五、第一轮观察",
            "",
        ]
    )
    lines.extend([f"- {line}" for line in observations] or ["- 当前结果说明 FXY 更适合作为分层变量而不是单一开关，但还需要进一步压缩样本格子。"])
    lines.extend(
        [
            "",
            "下一步建议：",
            "- 在 `IBS x FXY Regime` 里，只保留样本数足够的格子，做滚动样本外稳定性检查",
            "- 把 `Cross-Hedge Divergence` 和 `Shared Down Shock` 两类事件抽出来，做单独分钟级回测",
            "- 如果联合格子稳定，再考虑把 FXY 变量写进信号引擎，而不是继续停留在研究文档里",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    dxj_daily = prepare_daily(load_daily("dxj_minute_data.csv"))
    ewj_daily = prepare_daily(load_daily("ewj_minute_data.csv"))
    ctx = load_context()

    dxj_ibs_params = find_best_ibs(dxj_daily)
    ewj_ibs_params = find_best_ibs(ewj_daily)
    dxj_gap_params = find_best_gap(dxj_daily)
    ewj_gap_params = find_best_gap(ewj_daily)

    trades = []
    trades.append(attach_context(run_ibs_trades("DXJ", dxj_daily, dxj_ibs_params["ibs_buy"], dxj_ibs_params["ibs_sell"], int(dxj_ibs_params["max_hold"])), ctx))
    trades.append(attach_context(run_ibs_trades("EWJ", ewj_daily, ewj_ibs_params["ibs_buy"], ewj_ibs_params["ibs_sell"], int(ewj_ibs_params["max_hold"])), ctx))
    trades.append(attach_context(run_gap_trades("DXJ", dxj_daily, dxj_gap_params["gap_threshold"], int(dxj_gap_params["hold_days"])), ctx))
    trades.append(attach_context(run_gap_trades("EWJ", ewj_daily, ewj_gap_params["gap_threshold"], int(ewj_gap_params["hold_days"])), ctx))

    all_trades = pd.concat(trades, ignore_index=True)
    report = build_report(dxj_ibs_params, ewj_ibs_params, dxj_gap_params, ewj_gap_params, all_trades)
    DOC_FILE.write_text(report, encoding="utf-8")

    print(f"Wrote interaction report to {DOC_FILE}")
    print(f"Trades analyzed: {len(all_trades)}")


if __name__ == "__main__":
    main()
