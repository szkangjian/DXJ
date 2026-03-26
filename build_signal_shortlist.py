"""
基于稳定性、执行敏感性和半样本验证，整理当前可继续推进的信号候选清单。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from analyze_condition_specific_params import scan_gap, scan_ibs
from analyze_condition_stability import build_trades
from analyze_fxy_interactions import find_best_gap, load_context, prepare_daily
from analyze_ibs_fx_regime import find_best_ibs, load_daily
from analyze_parameter_walkforward import TARGETS, split_daily, summarize_test, verdict
from analyze_stable_cell_execution import evaluate_cell, load_market_data


DOC_FILE = Path("docs/15_signal_shortlist.md")


def load_asset_daily(asset: str) -> pd.DataFrame:
    return prepare_daily(load_daily(f"{asset.lower()}_minute_data.csv"))


def unified_label(asset: str, strategy: str, daily: pd.DataFrame) -> str:
    if strategy == "IBS":
        params = find_best_ibs(daily)
        return f"IBS<={params['ibs_buy']:.2f} / IBS>={params['ibs_sell']:.2f} / {int(params['max_hold'])}d"
    params = find_best_gap(daily)
    return f"Gap<={params['gap_threshold']*100:.1f}% / Hold {int(params['hold_days'])}d"


def shortlist_status(execution_label: str, wf_verdict: str, baseline_test: dict | None) -> str:
    if execution_label != "Robust" or wf_verdict not in {"Keep Unified", "Support Child"} or baseline_test is None:
        return "Drop"
    if baseline_test["total"] <= 0:
        return "Drop"
    if baseline_test["n"] >= 5 and baseline_test["avg"] >= 0.75:
        return "Core"
    if baseline_test["total"] >= 5 or baseline_test["avg"] >= 0.75:
        return "Secondary"
    return "Watchlist"


def note_for_status(status: str, strategy: str) -> str:
    if status == "Core":
        return "优先进入统一参数信号原型。"
    if status == "Secondary":
        return "保留为第二梯队，先做轻量信号实现。"
    if status == "Watchlist":
        return "继续观察，不要单独提高实盘优先级。"
    return f"{strategy} 当前不应继续推进到执行层。"


def build_report(rows: list[dict]) -> str:
    ordered = pd.DataFrame(rows).sort_values(
        ["status", "oos_total", "oos_avg"],
        ascending=[True, False, False],
    )

    observations = []
    core = ordered[ordered["status"] == "Core"]
    secondary = ordered[ordered["status"] == "Secondary"]
    watchlist = ordered[ordered["status"] == "Watchlist"]

    if not core.empty:
        top = core.iloc[0]
        observations.append(
            f"`{top['asset']} | {top['strategy']} | {top['cell']}` 是当前优先级最高的统一参数候选。"
        )
    if not secondary.empty:
        top = secondary.iloc[0]
        observations.append(
            f"`{top['asset']} | {top['strategy']} | {top['cell']}` 样本外为正，但样本仍偏薄，放在第二梯队。"
        )
    if not watchlist.empty:
        top = watchlist.iloc[0]
        observations.append(
            f"`{top['asset']} | {top['strategy']} | {top['cell']}` 目前更适合作为观察名单，而不是核心信号。"
        )

    lines = [
        "# 日本 ETF 条件信号候选清单",
        "",
        f"> 生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "> 口径: 同时参考稳定性、执行敏感性、半样本样本外验证。",
        "> 这里的结论只决定推进优先级，不重新发明参数；当前参数仍以各资产最新统一参数研究页为准。",
        "",
        "## 一、候选总表",
        "",
        "| 状态 | 标的 | 策略 | 条件格子 | 当前统一参数 | 执行标签 | 样本外结论 | 样本外笔数 | 样本外总收益 | 样本外均收益 |",
        "| ---- | ---- | ---- | -------- | ------------ | -------- | ---------- | ---------- | ------------ | ------------ |",
    ]

    for _, row in ordered.iterrows():
        lines.append(
            f"| {row['status']} | {row['asset']} | {row['strategy']} | {row['cell']} | {row['current_params']} | "
            f"{row['execution_label']} | {row['wf_verdict']} | {int(row['oos_n'])} | {row['oos_total']:+.1f}% | {row['oos_avg']:+.2f}% |"
        )

    for _, row in ordered.iterrows():
        lines.extend(
            [
                "",
                f"## {row['asset']} | {row['strategy']} | {row['cell']}",
                "",
                f"- 当前状态: `{row['status']}`",
                f"- 当前统一参数: `{row['current_params']}`",
                f"- 执行敏感性: `{row['execution_label']}`",
                f"- 半样本验证: `{row['wf_verdict']}`",
                f"- 样本外表现: {int(row['oos_n'])} 笔, 总收益 {row['oos_total']:+.1f}%, 均收益 {row['oos_avg']:+.2f}%",
                f"- 推进建议: {row['note']}",
            ]
        )

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
            "- 先对 `Core` 候选写统一参数信号脚本",
            "- `Secondary` 先做轻量监控，不急着实盘化",
            "- `Watchlist` 保留在研究层，等样本继续扩展后再复查",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    ctx = load_context()
    trades = build_trades()
    asset_daily = {asset: load_asset_daily(asset) for asset in {target["asset"] for target in TARGETS}}

    dxj_minute, dxj_daily_exec = load_market_data("dxj_minute_data.csv")
    ewj_minute, ewj_daily_exec = load_market_data("ewj_minute_data.csv")

    rows: list[dict] = []
    for target in TARGETS:
        asset = target["asset"]
        strategy = target["strategy"]
        cell = target["cell"]

        trade_subset = trades[
            (trades["asset"] == asset)
            & (trades["strategy"] == strategy)
            & (trades["cell"] == cell)
        ].copy()
        minute_df, exec_daily = (dxj_minute, dxj_daily_exec) if asset == "DXJ" else (ewj_minute, ewj_daily_exec)
        execution = evaluate_cell(trade_subset, minute_df, exec_daily)

        daily = asset_daily[asset]
        train_daily, test_daily = split_daily(daily)
        train_mask = (ctx["event_fx_combo"] == cell).reindex(train_daily.index).fillna(False)
        test_mask = (ctx["event_fx_combo"] == cell).reindex(test_daily.index).fillna(False)

        if strategy == "IBS":
            baseline_params = find_best_ibs(train_daily)
            conditional_best = scan_ibs(train_daily, train_mask).iloc[0]
        else:
            baseline_params = find_best_gap(train_daily)
            conditional_best = scan_gap(train_daily, train_mask).iloc[0]

        baseline_test, conditional_test = summarize_test(
            strategy,
            baseline_params,
            conditional_best,
            test_daily,
            test_mask,
        )
        wf_verdict = verdict(baseline_test, conditional_test)

        oos_n = int(baseline_test["n"]) if baseline_test is not None else 0
        oos_total = float(baseline_test["total"]) if baseline_test is not None else 0.0
        oos_avg = float(baseline_test["avg"]) if baseline_test is not None else 0.0

        status = shortlist_status(execution["label"], wf_verdict, baseline_test)
        rows.append(
            {
                "asset": asset,
                "strategy": strategy,
                "cell": cell,
                "current_params": unified_label(asset, strategy, daily),
                "execution_label": execution["label"],
                "wf_verdict": wf_verdict,
                "oos_n": oos_n,
                "oos_total": oos_total,
                "oos_avg": oos_avg,
                "status": status,
                "note": note_for_status(status, strategy),
            }
        )

    report = build_report(rows)
    DOC_FILE.write_text(report, encoding="utf-8")

    print(f"Wrote signal shortlist to {DOC_FILE}")
    print(f"Candidates scored: {len(rows)}")


if __name__ == "__main__":
    main()
