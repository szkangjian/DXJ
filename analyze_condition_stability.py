"""
对 FXY x Event Type x Strategy 的联合条件格子做时间稳定性检查。

目标：
1. 只保留样本数足够的格子
2. 检查这些格子在前后半段是否仍为正收益
3. 用四个连续时间桶判断它们是稳定、后期改善、前期透支还是混合
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from analyze_fxy_interactions import (
    DOC_FILE as _,
    attach_context,
    find_best_gap,
    load_context,
    prepare_daily,
    run_gap_trades,
    run_ibs_trades,
    summarize,
)
from analyze_ibs_fx_regime import find_best_ibs, load_daily


DOC_FILE = Path("docs/11_condition_stability.md")
MIN_TRADES = 6


def build_trades() -> pd.DataFrame:
    dxj_daily = prepare_daily(load_daily("dxj_minute_data.csv"))
    ewj_daily = prepare_daily(load_daily("ewj_minute_data.csv"))
    ctx = load_context()

    dxj_ibs = find_best_ibs(dxj_daily)
    ewj_ibs = find_best_ibs(ewj_daily)
    dxj_gap = find_best_gap(dxj_daily)
    ewj_gap = find_best_gap(ewj_daily)

    trades = []
    trades.append(
        attach_context(
            run_ibs_trades("DXJ", dxj_daily, dxj_ibs["ibs_buy"], dxj_ibs["ibs_sell"], int(dxj_ibs["max_hold"])),
            ctx,
        )
    )
    trades.append(
        attach_context(
            run_ibs_trades("EWJ", ewj_daily, ewj_ibs["ibs_buy"], ewj_ibs["ibs_sell"], int(ewj_ibs["max_hold"])),
            ctx,
        )
    )
    trades.append(
        attach_context(
            run_gap_trades("DXJ", dxj_daily, dxj_gap["gap_threshold"], int(dxj_gap["hold_days"])),
            ctx,
        )
    )
    trades.append(
        attach_context(
            run_gap_trades("EWJ", ewj_daily, ewj_gap["gap_threshold"], int(ewj_gap["hold_days"])),
            ctx,
        )
    )

    all_trades = pd.concat(trades, ignore_index=True)
    all_trades["entry_date"] = pd.to_datetime(all_trades["entry_date"])
    all_trades["cell"] = all_trades["event_fx_combo"]
    return all_trades


def summarize_simple(trades: pd.DataFrame) -> dict[str, float]:
    if trades.empty:
        return {
            "n": 0,
            "wr": float("nan"),
            "total": float("nan"),
            "avg": float("nan"),
            "worst": float("nan"),
            "avg_hold": float("nan"),
        }
    return {
        "n": int(len(trades)),
        "wr": float((trades["ret"] > 0).mean() * 100),
        "total": float(trades["ret"].sum() * 100),
        "avg": float(trades["ret"].mean() * 100),
        "worst": float(trades["ret"].min() * 100),
        "avg_hold": float(trades["days"].mean()),
    }


def classify_stability(first_avg: float, second_avg: float, positive_buckets: int, active_buckets: int) -> str:
    if pd.notna(first_avg) and pd.notna(second_avg):
        if first_avg > 0 and second_avg > 0 and active_buckets >= 2 and positive_buckets / active_buckets >= 0.75:
            return "Stable"
        if first_avg <= 0 < second_avg:
            return "Late Improve"
        if first_avg > 0 >= second_avg:
            return "Early Decay"
    return "Mixed"


def analyze_cells(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    combo_summary = summarize(trades, ["asset", "strategy", "event_fx_combo"])
    candidates = combo_summary[combo_summary["n"] >= MIN_TRADES].copy()

    start = trades["entry_date"].min()
    end = trades["entry_date"].max()
    mid = start + (end - start) / 2
    bucket_edges = pd.date_range(start=start.normalize(), end=end.normalize(), periods=5)

    trades = trades.copy()
    trades["half"] = trades["entry_date"].apply(lambda d: "H1" if d <= mid else "H2")
    bucket_labels = [f"B{i}" for i in range(1, 5)]
    trades["bucket"] = pd.cut(
        trades["entry_date"],
        bins=bucket_edges,
        labels=bucket_labels,
        include_lowest=True,
        right=True,
    )

    rows = []
    bucket_rows = []

    for _, candidate in candidates.iterrows():
        asset = candidate["asset"]
        strategy = candidate["strategy"]
        cell = candidate["event_fx_combo"]

        subset = trades[
            (trades["asset"] == asset)
            & (trades["strategy"] == strategy)
            & (trades["cell"] == cell)
        ].copy()

        first = summarize_simple(subset[subset["half"] == "H1"])
        second = summarize_simple(subset[subset["half"] == "H2"])

        bucket_summaries = {}
        active_buckets = 0
        positive_buckets = 0
        for label in bucket_labels:
            b = summarize_simple(subset[subset["bucket"] == label])
            bucket_summaries[label] = b
            if b["n"] > 0:
                active_buckets += 1
                if pd.notna(b["avg"]) and b["avg"] > 0:
                    positive_buckets += 1
                bucket_rows.append(
                    {
                        "asset": asset,
                        "strategy": strategy,
                        "cell": cell,
                        "bucket": label,
                        **b,
                    }
                )

        label = classify_stability(first["avg"], second["avg"], positive_buckets, active_buckets)
        rows.append(
            {
                "asset": asset,
                "strategy": strategy,
                "cell": cell,
                "label": label,
                "total_n": int(candidate["n"]),
                "overall_avg": float(candidate["avg"]),
                "overall_total": float(candidate["total"]),
                "first_n": first["n"],
                "first_avg": first["avg"],
                "second_n": second["n"],
                "second_avg": second["avg"],
                "positive_buckets": positive_buckets,
                "active_buckets": active_buckets,
            }
        )

    stability_df = pd.DataFrame(rows).sort_values(
        ["label", "overall_total", "overall_avg"],
        ascending=[True, False, False],
    )
    buckets_df = pd.DataFrame(bucket_rows)
    return stability_df, buckets_df


def build_report(stability_df: pd.DataFrame, buckets_df: pd.DataFrame) -> str:
    stable = stability_df[stability_df["label"] == "Stable"]
    decay = stability_df[stability_df["label"] == "Early Decay"]
    improve = stability_df[stability_df["label"] == "Late Improve"]

    observations = []
    if not stable.empty:
        top = stable.iloc[0]
        observations.append(
            f"当前最稳定的联合格子是 `{top['asset']} | {top['strategy']} | {top['cell']}`，前后半段都保持正平均收益。"
        )
    if not decay.empty:
        top = decay.iloc[0]
        observations.append(
            f"`{top['asset']} | {top['strategy']} | {top['cell']}` 属于前期有效、后期衰减，不能直接写进执行逻辑。"
        )
    if not improve.empty:
        top = improve.iloc[0]
        observations.append(
            f"`{top['asset']} | {top['strategy']} | {top['cell']}` 更像后期才变得有效，后续应检查是否与近期 regime 切换相关。"
        )

    lines = [
        "# 条件格子稳定性检查",
        "",
        f"> 生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 只分析样本数 >= {MIN_TRADES} 的联合条件格子。",
        f"> 说明: 这里测试的是“条件格子”的时间稳定性，不是参数搜索的严格样本外优化。",
        "",
        "## 一、稳定性总表",
        "",
        "| 标记 | 标的 | 策略 | 联合条件 | 总笔数 | 全样本均收益 | 前半段笔数 | 前半段均收益 | 后半段笔数 | 后半段均收益 | 正收益桶数 | 活跃桶数 |",
        "| ---- | ---- | ---- | -------- | ------ | ------------ | ---------- | ------------ | ---------- | ------------ | ---------- | -------- |",
    ]

    for _, row in stability_df.iterrows():
        lines.append(
            f"| {row['label']} | {row['asset']} | {row['strategy']} | {row['cell']} | {int(row['total_n'])} | "
            f"{row['overall_avg']:+.2f}% | {int(row['first_n'])} | {row['first_avg']:+.2f}% | "
            f"{int(row['second_n'])} | {row['second_avg']:+.2f}% | {int(row['positive_buckets'])} | {int(row['active_buckets'])} |"
        )

    lines.extend(
        [
            "",
            "## 二、四个连续时间桶明细",
            "",
            "| 标的 | 策略 | 联合条件 | 时间桶 | 笔数 | 胜率 | 均收益 | 总收益 | 最大亏损 |",
            "| ---- | ---- | -------- | ------ | ---- | ---- | ------ | ------ | -------- |",
        ]
    )

    for _, row in buckets_df.sort_values(["asset", "strategy", "cell", "bucket"]).iterrows():
        lines.append(
            f"| {row['asset']} | {row['strategy']} | {row['cell']} | {row['bucket']} | {int(row['n'])} | "
            f"{row['wr']:.0f}% | {row['avg']:+.2f}% | {row['total']:+.1f}% | {row['worst']:+.2f}% |"
        )

    lines.extend(
        [
            "",
            "## 三、第一轮观察",
            "",
        ]
    )
    lines.extend([f"- {line}" for line in observations] or ["- 当前样本长度仍不长，稳定性结论只能作为条件筛选，不足以直接实盘化。"])
    lines.extend(
        [
            "",
            "下一步建议：",
            "- 只对 `Stable` 标签的格子继续做分钟级执行回测",
            "- 对 `Early Decay` 标签的格子检查是否由单一时期或单一事件贡献",
            "- 若后续要做信号引擎，应优先把“稳定格子”写成条件分层，而不是把所有格子一视同仁",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    trades = build_trades()
    stability_df, buckets_df = analyze_cells(trades)
    report = build_report(stability_df, buckets_df)
    DOC_FILE.write_text(report, encoding="utf-8")

    print(f"Wrote stability report to {DOC_FILE}")
    print(f"Cells analyzed: {len(stability_df)}")


if __name__ == "__main__":
    main()
