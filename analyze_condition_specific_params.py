"""
对已经筛出来的稳健条件格子，单独做参数扫描。

目的：
1. 看这些格子是否应该使用条件化参数
2. 对比“全样本最优参数”与“条件格子最优参数”的差异
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from analyze_fxy_interactions import find_best_gap, load_context, prepare_daily
from analyze_ibs_fx_regime import find_best_ibs, load_daily, run_ibs


DOC_FILE = Path("docs/13_condition_specific_params.md")

TARGET_CELLS = [
    {"asset": "DXJ", "strategy": "Gap", "cell": "Non-event | Neutral"},
    {"asset": "DXJ", "strategy": "IBS", "cell": "Cross-Hedge Divergence | Neutral"},
    {"asset": "EWJ", "strategy": "IBS", "cell": "Cross-Hedge Divergence | Neutral"},
    {"asset": "EWJ", "strategy": "IBS", "cell": "Shared Down Shock | Neutral"},
]


def load_asset_daily(asset: str) -> pd.DataFrame:
    file_name = f"{asset.lower()}_minute_data.csv"
    daily = prepare_daily(load_daily(file_name))
    return daily


def summarize(trades: list[float]) -> dict | None:
    if not trades:
        return None
    s = pd.Series(trades)
    return {
        "n": len(s),
        "wr": float((s > 0).mean() * 100),
        "total": float(s.sum() * 100),
        "avg": float(s.mean() * 100),
        "worst": float(s.min() * 100),
    }


def scan_ibs(daily: pd.DataFrame, entry_mask: pd.Series) -> pd.DataFrame:
    rows = []
    for ibs_buy in [0.10, 0.15, 0.20, 0.25, 0.30]:
        for ibs_sell in [0.60, 0.70, 0.80, 0.90]:
            if ibs_sell <= ibs_buy:
                continue
            for hold in [1, 2, 3, 5, 10]:
                summary = run_ibs(daily, ibs_buy, ibs_sell, hold, entry_mask=entry_mask)
                if summary is None:
                    continue
                rows.append(
                    {
                        "entry": f"IBS<={ibs_buy:.2f}",
                        "exit": f"IBS>={ibs_sell:.2f}",
                        "hold": hold,
                        **summary,
                    }
                )

    return pd.DataFrame(rows).sort_values(["total", "avg", "wr"], ascending=False).reset_index(drop=True)


def evaluate_gap(daily: pd.DataFrame, entry_mask: pd.Series, gap_threshold: float, hold_days: int) -> dict | None:
    trades: list[float] = []
    reset = daily.reset_index()
    i = 1
    while i < len(reset):
        row = reset.iloc[i]
        idx = row["timestamp"]
        if bool(entry_mask.get(idx, False)) and row["gap_pct"] <= gap_threshold:
            exit_i = min(i + hold_days, len(reset) - 1)
            exit_row = reset.iloc[exit_i]
            trades.append(exit_row["Close"] / row["Open"] - 1)
            i = exit_i + 1
        else:
            i += 1

    summary = summarize(trades)
    if summary is None:
        return None
    return {
        "entry": f"Gap<={gap_threshold * 100:.1f}%",
        "exit": f"Hold {hold_days}d",
        "hold": hold_days + 1,
        **summary,
    }


def scan_gap(daily: pd.DataFrame, entry_mask: pd.Series) -> pd.DataFrame:
    rows = []

    for gap_threshold in [-0.01, -0.015, -0.02, -0.025, -0.03]:
        for hold_days in [0, 1, 2, 3, 5]:
            summary = evaluate_gap(daily, entry_mask, gap_threshold, hold_days)
            if summary is None:
                continue
            rows.append(summary)

    return pd.DataFrame(rows).sort_values(["total", "avg", "wr"], ascending=False).reset_index(drop=True)


def compare_label(result: dict) -> str:
    if result["baseline"] is None or result["best"].empty:
        return "No Signal"

    best = result["best"].iloc[0]
    base = result["baseline"]
    same_params = (
        best["entry"] == base["entry"]
        and best["exit"] == base["exit"]
        and int(best["hold"]) == int(base["hold"])
    )
    total_lift = float(best["total"] - base["total"])

    if same_params or total_lift <= 3:
        return "Keep Unified"
    return "Candidate Child Strategy"


def build_report(results: list[dict]) -> str:
    observations = []
    for result in results:
        if result["best"].empty or result["baseline"] is None:
            observations.append(
                f"`{result['asset']} | {result['cell']}` 当前没有形成可比较的条件样本，先不要单独参数化。"
            )
            continue

        best = result["best"].iloc[0]
        base = result["baseline"]
        lift = best["total"] - base["total"]
        if compare_label(result) == "Candidate Child Strategy":
            observations.append(
                f"`{result['asset']} | {result['cell']}` 的条件最优参数明显偏离统一参数，"
                f"总收益改善 {lift:+.1f}% ，值得视为独立子策略候选。"
            )
        else:
            observations.append(
                f"`{result['asset']} | {result['cell']}` 的条件最优与统一参数差异有限，"
                f"总收益改善 {lift:+.1f}% ，优先保留统一参数。"
            )

    lines = [
        "# 稳健格子的条件化参数扫描",
        "",
        f"> 生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "> 这里只对已经过稳定性和执行敏感性筛选的格子继续做细化扫描。",
        "",
    ]

    for result in results:
        lines.extend(
            [
                f"## {result['asset']} | {result['strategy']} | {result['cell']}",
                "",
                f"初步判断: `{compare_label(result)}`",
                "",
            ]
        )

        if result["baseline"] is None:
            lines.extend(
                [
                    "该条件格子在统一参数下没有形成有效交易样本，暂不继续细化。",
                    "",
                ]
            )
            continue

        baseline = result["baseline"]
        lines.extend(
            [
                "### 统一参数在该格子中的表现",
                "",
                "| 口径 | 入场 | 出场 | 持有 | 笔数 | 胜率 | 总收益 | 均收益 | 最大亏损 |",
                "| ---- | ---- | ---- | ---- | ---- | ---- | ------ | ------ | -------- |",
                f"| Baseline | {baseline['entry']} | {baseline['exit']} | {int(baseline['hold'])}d | {int(baseline['n'])} | "
                f"{baseline['wr']:.0f}% | {baseline['total']:+.1f}% | {baseline['avg']:+.2f}% | {baseline['worst']:+.2f}% |",
                "",
                "### 条件化参数候选",
                "",
                "| 入场 | 出场 | 持有 | 笔数 | 胜率 | 总收益 | 均收益 | 最大亏损 |",
                "| ---- | ---- | ---- | ---- | ---- | ------ | ------ | -------- |",
            ]
        )

        for _, row in result["best"].head(8).iterrows():
            lines.append(
                f"| {row['entry']} | {row['exit']} | {int(row['hold'])}d | {int(row['n'])} | {row['wr']:.0f}% | "
                f"{row['total']:+.1f}% | {row['avg']:+.2f}% | {row['worst']:+.2f}% |"
            )
        lines.append("")

    lines.extend(
        [
            "## 第一轮观察",
            "",
        ]
    )
    lines.extend([f"- {line}" for line in observations])
    lines.extend(
        [
            "",
            "下一步建议：",
            "- 若条件最优参数明显偏离全样本参数，应把它们视为独立子策略",
            "- 若条件最优与全样本参数接近，则优先保留统一参数，避免过拟合",
            "- 对样本数较少但收益高的格子，先做样本外滚动验证，再考虑进入执行层",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    ctx = load_context()
    results: list[dict] = []
    asset_daily = {asset: load_asset_daily(asset) for asset in {target["asset"] for target in TARGET_CELLS}}

    for target in TARGET_CELLS:
        daily = asset_daily[target["asset"]]
        entry_mask = (ctx["event_fx_combo"] == target["cell"]).reindex(daily.index).fillna(False)

        if target["strategy"] == "IBS":
            global_best = find_best_ibs(daily)
            baseline = run_ibs(
                daily,
                float(global_best["ibs_buy"]),
                float(global_best["ibs_sell"]),
                int(global_best["max_hold"]),
                entry_mask=entry_mask,
            )
            if baseline is not None:
                baseline = {
                    "entry": f"IBS<={global_best['ibs_buy']:.2f}",
                    "exit": f"IBS>={global_best['ibs_sell']:.2f}",
                    "hold": int(global_best["max_hold"]),
                    **baseline,
                }
            best = scan_ibs(daily, entry_mask)
        else:
            global_best = find_best_gap(daily)
            baseline = evaluate_gap(
                daily,
                entry_mask,
                float(global_best["gap_threshold"]),
                int(global_best["hold_days"]),
            )
            best = scan_gap(daily, entry_mask)

        results.append(
            {
                "asset": target["asset"],
                "strategy": target["strategy"],
                "cell": target["cell"],
                "baseline": baseline,
                "best": best,
            }
        )

    report = build_report(results)
    DOC_FILE.write_text(report, encoding="utf-8")

    print(f"Wrote conditional-parameter report to {DOC_FILE}")
    print(f"Cells scanned: {len(results)}")


if __name__ == "__main__":
    main()
