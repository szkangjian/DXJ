"""
对稳健格子的统一参数 vs 条件参数做半样本样本外验证。

方法：
1. 用前半段样本选出资产级统一参数
2. 用同一前半段样本选出条件格子的局部最优参数
3. 在后半段样本中，只对该条件格子的入场机会做对照评估
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from analyze_condition_specific_params import evaluate_gap, scan_gap, scan_ibs
from analyze_fxy_interactions import find_best_gap, load_context, prepare_daily
from analyze_ibs_fx_regime import find_best_ibs, load_daily, run_ibs


DOC_FILE = Path("docs/14_parameter_walkforward.md")

TARGETS = [
    {"asset": "DXJ", "strategy": "Gap", "cell": "Non-event | Neutral"},
    {"asset": "DXJ", "strategy": "IBS", "cell": "Cross-Hedge Divergence | Neutral"},
    {"asset": "EWJ", "strategy": "IBS", "cell": "Cross-Hedge Divergence | Neutral"},
    {"asset": "EWJ", "strategy": "IBS", "cell": "Shared Down Shock | Neutral"},
]


def load_asset_daily(asset: str) -> pd.DataFrame:
    csv_file = f"{asset.lower()}_minute_data.csv"
    return prepare_daily(load_daily(csv_file))


def parse_ibs_row(row: pd.Series) -> tuple[float, float, int]:
    ibs_buy = float(str(row["entry"]).split("<=")[1])
    ibs_sell = float(str(row["exit"]).split(">=")[1])
    hold = int(row["hold"])
    return ibs_buy, ibs_sell, hold


def parse_gap_row(row: pd.Series) -> tuple[float, int]:
    gap_threshold = float(str(row["entry"]).split("<=")[1].rstrip("%")) / 100
    hold_days = int(str(row["exit"]).replace("Hold ", "").replace("d", ""))
    return gap_threshold, hold_days


def split_daily(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    split_idx = len(daily) // 2
    train = daily.iloc[:split_idx].copy()
    test = daily.iloc[split_idx:].copy()
    return train, test


def summarize_test(
    strategy: str,
    baseline_params: dict,
    conditional_row: pd.Series,
    test_daily: pd.DataFrame,
    test_mask: pd.Series,
) -> tuple[dict | None, dict | None]:
    if strategy == "IBS":
        baseline = run_ibs(
            test_daily,
            float(baseline_params["ibs_buy"]),
            float(baseline_params["ibs_sell"]),
            int(baseline_params["max_hold"]),
            entry_mask=test_mask,
        )
        if baseline is not None:
            baseline = {
                "entry": f"IBS<={baseline_params['ibs_buy']:.2f}",
                "exit": f"IBS>={baseline_params['ibs_sell']:.2f}",
                "hold": int(baseline_params["max_hold"]),
                **baseline,
            }

        ibs_buy, ibs_sell, hold = parse_ibs_row(conditional_row)
        conditional = run_ibs(test_daily, ibs_buy, ibs_sell, hold, entry_mask=test_mask)
        if conditional is not None:
            conditional = {
                "entry": f"IBS<={ibs_buy:.2f}",
                "exit": f"IBS>={ibs_sell:.2f}",
                "hold": hold,
                **conditional,
            }
        return baseline, conditional

    baseline = evaluate_gap(
        test_daily,
        test_mask,
        float(baseline_params["gap_threshold"]),
        int(baseline_params["hold_days"]),
    )
    gap_threshold, hold_days = parse_gap_row(conditional_row)
    conditional = evaluate_gap(test_daily, test_mask, gap_threshold, hold_days)
    return baseline, conditional


def verdict(baseline: dict | None, conditional: dict | None) -> str:
    if baseline is None or conditional is None:
        return "Inconclusive"
    if conditional["total"] > baseline["total"] and conditional["avg"] > baseline["avg"]:
        return "Support Child"
    if baseline["total"] > 0 and baseline["avg"] >= conditional["avg"]:
        return "Keep Unified"
    return "Mixed"


def build_report(results: list[dict]) -> str:
    observations = []
    for result in results:
        if result["verdict"] == "Support Child":
            observations.append(
                f"`{result['asset']} | {result['strategy']} | {result['cell']}` 在测试半段里条件参数仍跑赢统一参数，"
                f"子策略有初步样本外支持。"
            )
        elif result["verdict"] == "Keep Unified":
            observations.append(
                f"`{result['asset']} | {result['strategy']} | {result['cell']}` 在测试半段没有证明条件参数更好，"
                f"先保留统一参数。"
            )
        else:
            observations.append(
                f"`{result['asset']} | {result['strategy']} | {result['cell']}` 的测试半段样本不足或结果混合，"
                f"暂时不升格为独立子策略。"
            )

    lines = [
        "# 参数选择的半样本样本外验证",
        "",
        f"> 生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "> 方法: 前半段选参数，后半段只在对应条件格子上做统一参数 vs 条件参数的对照。",
        "",
        "## 一、测试结果总表",
        "",
        "| 结论 | 标的 | 策略 | 条件格子 | 测试区间 | Baseline | 条件参数 | Baseline 总收益 | 条件总收益 | Baseline 均收益 | 条件均收益 |",
        "| ---- | ---- | ---- | -------- | -------- | -------- | -------- | --------------- | ---------- | --------------- | ---------- |",
    ]

    for result in results:
        baseline = result["baseline_test"]
        conditional = result["conditional_test"]
        baseline_label = "N/A"
        conditional_label = "N/A"
        baseline_total = "N/A"
        conditional_total = "N/A"
        baseline_avg = "N/A"
        conditional_avg = "N/A"

        if baseline is not None:
            baseline_label = f"{baseline['entry']} / {baseline['exit']} / {int(baseline['hold'])}d"
            baseline_total = f"{baseline['total']:+.1f}%"
            baseline_avg = f"{baseline['avg']:+.2f}%"
        if conditional is not None:
            conditional_label = f"{conditional['entry']} / {conditional['exit']} / {int(conditional['hold'])}d"
            conditional_total = f"{conditional['total']:+.1f}%"
            conditional_avg = f"{conditional['avg']:+.2f}%"

        lines.append(
            f"| {result['verdict']} | {result['asset']} | {result['strategy']} | {result['cell']} | "
            f"{result['test_start']} to {result['test_end']} | {baseline_label} | {conditional_label} | "
            f"{baseline_total} | {conditional_total} | {baseline_avg} | {conditional_avg} |"
        )

    for result in results:
        lines.extend(
            [
                "",
                f"## {result['asset']} | {result['strategy']} | {result['cell']}",
                "",
                f"训练区间: `{result['train_start']} to {result['train_end']}`",
                f"测试区间: `{result['test_start']} to {result['test_end']}`",
                "",
                f"- 资产级统一参数: `{result['baseline_train_label']}`",
                f"- 条件格子训练最优: `{result['conditional_train_label']}`",
                f"- 测试结论: `{result['verdict']}`",
            ]
        )

        baseline = result["baseline_test"]
        conditional = result["conditional_test"]
        if baseline is not None:
            lines.append(
                f"- Baseline 测试表现: {int(baseline['n'])} 笔, 总收益 {baseline['total']:+.1f}%, 均收益 {baseline['avg']:+.2f}%, 胜率 {baseline['wr']:.0f}%"
            )
        else:
            lines.append("- Baseline 测试表现: 无有效交易")

        if conditional is not None:
            lines.append(
                f"- 条件参数测试表现: {int(conditional['n'])} 笔, 总收益 {conditional['total']:+.1f}%, 均收益 {conditional['avg']:+.2f}%, 胜率 {conditional['wr']:.0f}%"
            )
        else:
            lines.append("- 条件参数测试表现: 无有效交易")

    lines.extend(
        [
            "",
            "## 二、第一轮观察",
            "",
        ]
    )
    lines.extend([f"- {line}" for line in observations])
    lines.extend(
        [
            "",
            "下一步建议：",
            "- 只有得到 `Support Child` 的格子，才值得继续做独立信号原型",
            "- `Keep Unified` 和 `Mixed` 先保留在统一参数框架内，避免参数碎片化",
            "- 若后续继续扩展样本，应优先重复这套半样本验证，而不是直接追求更高的全样本最优点",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    ctx = load_context()
    asset_daily = {asset: load_asset_daily(asset) for asset in {target["asset"] for target in TARGETS}}
    results: list[dict] = []

    for target in TARGETS:
        daily = asset_daily[target["asset"]]
        train_daily, test_daily = split_daily(daily)

        train_mask = (ctx["event_fx_combo"] == target["cell"]).reindex(train_daily.index).fillna(False)
        test_mask = (ctx["event_fx_combo"] == target["cell"]).reindex(test_daily.index).fillna(False)

        if target["strategy"] == "IBS":
            baseline_params = find_best_ibs(train_daily)
            conditional_scan = scan_ibs(train_daily, train_mask)
            conditional_best = conditional_scan.iloc[0]
            baseline_train_label = (
                f"IBS<={baseline_params['ibs_buy']:.2f} / IBS>={baseline_params['ibs_sell']:.2f} / {int(baseline_params['max_hold'])}d"
            )
        else:
            baseline_params = find_best_gap(train_daily)
            conditional_scan = scan_gap(train_daily, train_mask)
            conditional_best = conditional_scan.iloc[0]
            baseline_train_label = (
                f"Gap<={baseline_params['gap_threshold']*100:.1f}% / Hold {int(baseline_params['hold_days'])}d"
            )

        baseline_test, conditional_test = summarize_test(
            target["strategy"],
            baseline_params,
            conditional_best,
            test_daily,
            test_mask,
        )

        results.append(
            {
                "asset": target["asset"],
                "strategy": target["strategy"],
                "cell": target["cell"],
                "train_start": train_daily.index.min().date().isoformat(),
                "train_end": train_daily.index.max().date().isoformat(),
                "test_start": test_daily.index.min().date().isoformat(),
                "test_end": test_daily.index.max().date().isoformat(),
                "baseline_train_label": baseline_train_label,
                "conditional_train_label": f"{conditional_best['entry']} / {conditional_best['exit']} / {int(conditional_best['hold'])}d",
                "baseline_test": baseline_test,
                "conditional_test": conditional_test,
                "verdict": verdict(baseline_test, conditional_test),
            }
        )

    report = build_report(results)
    DOC_FILE.write_text(report, encoding="utf-8")

    print(f"Wrote walk-forward report to {DOC_FILE}")
    print(f"Targets tested: {len(results)}")


if __name__ == "__main__":
    main()
