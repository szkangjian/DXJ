"""
对稳定条件格子做执行敏感性测试。

方法：
- IBS: 基准为收盘进出，保守版改为次日开盘进出
- Gap: 基准为开盘买入/收盘卖出，保守版改为 09:35 买入 / 15:55 卖出
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from analyze_condition_stability import analyze_cells, build_trades


DOC_FILE = Path("docs/12_stable_cell_execution.md")


def load_market_data(csv_file: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(csv_file, parse_dates=["timestamp"])
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
    df["date"] = pd.to_datetime(df.index.date)

    daily = (
        df.resample("D")
        .agg(
            Open=("Open", "first"),
            Close=("Close", "last"),
        )
        .dropna()
    )
    return df, daily


def next_day_open(daily: pd.DataFrame, date: pd.Timestamp) -> float | None:
    if date not in daily.index:
        return None
    loc = daily.index.get_loc(date)
    if isinstance(loc, slice):
        return None
    if loc + 1 >= len(daily):
        return None
    return float(daily.iloc[loc + 1]["Open"])


def intraday_close(minute_df: pd.DataFrame, date: pd.Timestamp, hhmm: str) -> float | None:
    day_rows = minute_df[minute_df["date"] == date].copy()
    if day_rows.empty:
        return None
    target = pd.Timestamp(f"{date.date()} {hhmm}")
    eligible = day_rows[day_rows.index <= target]
    if eligible.empty:
        return None
    return float(eligible.iloc[-1]["Close"])


def summarize_returns(returns: list[float]) -> dict[str, float]:
    if not returns:
        return {
            "n": 0,
            "wr": float("nan"),
            "total": float("nan"),
            "avg": float("nan"),
            "worst": float("nan"),
        }
    s = pd.Series(returns)
    return {
        "n": int(len(s)),
        "wr": float((s > 0).mean() * 100),
        "total": float(s.sum() * 100),
        "avg": float(s.mean() * 100),
        "worst": float(s.min() * 100),
    }


def execution_label(base_avg: float, cons_avg: float, cons_total: float) -> str:
    if pd.isna(cons_total) or cons_total <= 0:
        return "Fragile"
    if cons_avg < base_avg * 0.5:
        return "Degraded"
    return "Robust"


def evaluate_cell(trades: pd.DataFrame, minute_df: pd.DataFrame, daily: pd.DataFrame) -> dict[str, float | str]:
    base_returns = trades["ret"].tolist()
    cons_returns: list[float] = []

    for _, row in trades.iterrows():
        entry_date = pd.to_datetime(row["entry_date"])
        exit_date = pd.to_datetime(row["exit_date"])

        if row["strategy"] == "IBS":
            entry_price = next_day_open(daily, entry_date)
            exit_price = next_day_open(daily, exit_date)
        else:
            entry_price = intraday_close(minute_df, entry_date, "09:35")
            exit_price = intraday_close(minute_df, exit_date, "15:55")

        if entry_price is None or exit_price is None or entry_price <= 0:
            continue
        cons_returns.append(exit_price / entry_price - 1)

    base = summarize_returns(base_returns)
    cons = summarize_returns(cons_returns)

    return {
        "base_n": base["n"],
        "base_wr": base["wr"],
        "base_total": base["total"],
        "base_avg": base["avg"],
        "cons_n": cons["n"],
        "cons_wr": cons["wr"],
        "cons_total": cons["total"],
        "cons_avg": cons["avg"],
        "delta_total": cons["total"] - base["total"],
        "delta_avg": cons["avg"] - base["avg"],
        "label": execution_label(base["avg"], cons["avg"], cons["total"]),
    }


def build_report(results: pd.DataFrame) -> str:
    observations = []

    robust = results[results["label"] == "Robust"]
    fragile = results[results["label"] == "Fragile"]
    degraded = results[results["label"] == "Degraded"]

    if not robust.empty:
        top = robust.iloc[0]
        observations.append(
            f"`{top['asset']} | {top['strategy']} | {top['cell']}` 在更保守的执行假设下仍保持正收益，属于优先保留的候选。"
        )
    if not degraded.empty:
        top = degraded.iloc[0]
        observations.append(
            f"`{top['asset']} | {top['strategy']} | {top['cell']}` 在执行上仍为正，但收益折损明显，后续需要更精细的下单时点测试。"
        )
    if not fragile.empty:
        top = fragile.iloc[0]
        observations.append(
            f"`{top['asset']} | {top['strategy']} | {top['cell']}` 一旦换成更保守执行就明显变弱，不能直接实盘化。"
        )

    lines = [
        "# 稳定格子的执行敏感性测试",
        "",
        f"> 生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "> 执行假设:",
        "> - IBS: 基准为收盘进出，保守版为次日开盘进出",
        "> - Gap: 基准为开盘买入/收盘卖出，保守版为 09:35 买入 / 15:55 卖出",
        "",
        "## 一、执行敏感性总表",
        "",
        "| 标记 | 标的 | 策略 | 联合条件 | 基准笔数 | 基准均收益 | 基准总收益 | 保守笔数 | 保守均收益 | 保守总收益 | 总收益变化 | 均收益变化 |",
        "| ---- | ---- | ---- | -------- | -------- | ---------- | ---------- | -------- | ---------- | ---------- | ---------- | ---------- |",
    ]

    for _, row in results.iterrows():
        lines.append(
            f"| {row['label']} | {row['asset']} | {row['strategy']} | {row['cell']} | {int(row['base_n'])} | "
            f"{row['base_avg']:+.2f}% | {row['base_total']:+.1f}% | {int(row['cons_n'])} | "
            f"{row['cons_avg']:+.2f}% | {row['cons_total']:+.1f}% | {row['delta_total']:+.1f}% | {row['delta_avg']:+.2f}% |"
        )

    lines.extend(
        [
            "",
            "## 二、第一轮观察",
            "",
        ]
    )
    lines.extend([f"- {line}" for line in observations] or ["- 当前稳定格子在保守执行下仍需逐个检查，不能只看研究层面的均值表现。"])
    lines.extend(
        [
            "",
            "下一步建议：",
            "- 只对 `Robust` 标签的格子继续做分钟级或下单时点优化",
            "- `Degraded` 标签保留为观察对象，但先不要进信号引擎",
            "- `Fragile` 标签若无额外证据，不应继续实盘优先级推进",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    trades = build_trades()
    stability_df, _ = analyze_cells(trades)
    stable_cells = stability_df[stability_df["label"] == "Stable"].copy()

    dxj_minute, dxj_daily = load_market_data("dxj_minute_data.csv")
    ewj_minute, ewj_daily = load_market_data("ewj_minute_data.csv")

    rows = []
    for _, stable in stable_cells.iterrows():
        subset = trades[
            (trades["asset"] == stable["asset"])
            & (trades["strategy"] == stable["strategy"])
            & (trades["cell"] == stable["cell"])
        ].copy()

        minute_df, daily = (dxj_minute, dxj_daily) if stable["asset"] == "DXJ" else (ewj_minute, ewj_daily)
        summary = evaluate_cell(subset, minute_df, daily)
        rows.append(
            {
                "asset": stable["asset"],
                "strategy": stable["strategy"],
                "cell": stable["cell"],
                **summary,
            }
        )

    result_df = pd.DataFrame(rows).sort_values(
        ["label", "cons_total", "cons_avg"],
        ascending=[True, False, False],
    )
    report = build_report(result_df)
    DOC_FILE.write_text(report, encoding="utf-8")

    print(f"Wrote execution report to {DOC_FILE}")
    print(f"Stable cells tested: {len(result_df)}")


if __name__ == "__main__":
    main()
