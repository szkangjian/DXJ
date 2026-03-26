"""
DXJ / EWJ 核心条件信号引擎。

当前只执行已经通过研究筛选的 Core 候选：
1. DXJ IBS @ Cross-Hedge Divergence | Neutral
2. EWJ IBS @ Cross-Hedge Divergence | Neutral

Secondary / Watchlist 只做提示，不自动入场。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import update_dxj_today
import update_ewj_today
from analyze_fxy_interactions import load_context
from analyze_ibs_fx_regime import load_daily


STATE_FILE = Path("japan_core_signal_state.json")
STATUS_FILE = Path("japan_core_signal_status.json")

CORE_STRATEGIES = [
    {
        "asset": "DXJ",
        "entry_combo": "Cross-Hedge Divergence | Neutral",
        "entry_ibs": 0.30,
        "exit_ibs": 0.90,
        "max_hold": 5,
    },
    {
        "asset": "EWJ",
        "entry_combo": "Cross-Hedge Divergence | Neutral",
        "entry_ibs": 0.25,
        "exit_ibs": 0.60,
        "max_hold": 2,
    },
]

MONITOR_ONLY = [
    {
        "label": "EWJ Secondary IBS",
        "asset": "EWJ",
        "combo": "Shared Down Shock | Neutral",
        "entry_ibs": 0.25,
        "message": "Secondary 候选激活，只监控不自动入场。",
    },
    {
        "label": "DXJ Gap Watchlist",
        "asset": "DXJ",
        "combo": "Non-event | Neutral",
        "gap_threshold": -0.01,
        "message": "Watchlist 激活，继续观察但不自动入场。",
    },
]


def default_state() -> dict:
    return {
        "positions": {strategy["asset"]: None for strategy in CORE_STRATEGIES},
        "trade_log": [],
        "last_processed_date": None,
    }


def load_state() -> dict:
    if not STATE_FILE.exists():
        return default_state()

    state = json.loads(STATE_FILE.read_text())
    template = default_state()
    state.setdefault("positions", template["positions"])
    state.setdefault("trade_log", [])
    state.setdefault("last_processed_date", None)
    for asset in template["positions"]:
        state["positions"].setdefault(asset, None)
    return state


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def save_status(payload: dict) -> None:
    STATUS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def build_status_payload(
    trade_date: str,
    ctx_row: pd.Series,
    dxj_row: pd.Series,
    ewj_row: pd.Series,
    signals: list[dict],
    monitor_notes: list[str],
    positions: dict,
    already_processed: bool = False,
) -> dict:
    return {
        "trade_date": trade_date,
        "event_type": str(ctx_row["event_type"]),
        "fxy_regime": str(ctx_row["fxy_regime"]),
        "event_fx_combo": str(ctx_row["event_fx_combo"]),
        "dxj": {
            "close": round(float(dxj_row["Close"]), 2),
            "ibs": round(float(dxj_row["ibs"]), 4),
            "ret": round(float(dxj_row["ret"]) * 100, 2),
        },
        "ewj": {
            "close": round(float(ewj_row["Close"]), 2),
            "ibs": round(float(ewj_row["ibs"]), 4),
            "ret": round(float(ewj_row["ret"]) * 100, 2),
        },
        "signals": signals,
        "monitor_notes": monitor_notes,
        "positions": positions,
        "already_processed": already_processed,
    }


def update_data() -> None:
    print("更新 DXJ / EWJ 当日分钟数据...")
    update_dxj_today.main()
    update_ewj_today.main()


def latest_daily_map() -> dict[str, pd.DataFrame]:
    return {
        "DXJ": load_daily("dxj_minute_data.csv"),
        "EWJ": load_daily("ewj_minute_data.csv"),
    }


def latest_common_date(daily_map: dict[str, pd.DataFrame], ctx: pd.DataFrame) -> pd.Timestamp:
    latest_dates = [daily.index.max() for daily in daily_map.values()]
    latest_dates.append(ctx.index.max())
    return min(latest_dates)


def format_price(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"${value:.2f}"


def format_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value * 100:+.2f}%"


def print_snapshot(date_str: str, state: dict) -> None:
    print(f"\n{'=' * 64}")
    print(f"  Japan Core Signal | {date_str}")
    print(f"{'=' * 64}")
    print("  该交易日已经处理过，状态未重复写入。")

    for asset, pos in state["positions"].items():
        if pos:
            print(
                f"  {asset}: 持仓中 @ {format_price(pos['buy_price'])}, "
                f"买入日 {pos['buy_date']}, 已持有 {pos['days_held']} 天"
            )
        else:
            print(f"  {asset}: 空仓")


def print_context(ctx_row: pd.Series, dxj_row: pd.Series, ewj_row: pd.Series) -> None:
    print(f"\n{'=' * 64}")
    print(f"  Japan Core Signal | {pd.Timestamp(dxj_row.name).date()}")
    print(f"{'=' * 64}")
    print(f"  Event Type: {ctx_row['event_type']}")
    print(f"  FXY Regime: {ctx_row['fxy_regime']}  |  FXY Ret: {format_pct(ctx_row['FXY'])}")
    print(f"  Entry Combo: {ctx_row['event_fx_combo']}")
    print(
        f"  DXJ Ret: {format_pct(dxj_row['ret'])}  |  DXJ Close: {format_price(dxj_row['Close'])}  |  DXJ IBS: {dxj_row['ibs']:.3f}"
    )
    print(
        f"  EWJ Ret: {format_pct(ewj_row['ret'])}  |  EWJ Close: {format_price(ewj_row['Close'])}  |  EWJ IBS: {ewj_row['ibs']:.3f}"
    )


def maybe_record_trade(state: dict, trade: dict) -> None:
    state["trade_log"].append(trade)


def process_core_strategy(
    strategy: dict,
    row: pd.Series,
    combo: str,
    trade_date: str,
    state: dict,
) -> list[dict]:
    asset = strategy["asset"]
    close = float(row["Close"])
    ibs = float(row["ibs"]) if pd.notna(row["ibs"]) else float("nan")
    signals: list[dict] = []

    print(f"\n  --- {asset} Core IBS ---")
    print(
        f"  条件: {strategy['entry_combo']} | 买入 IBS<={strategy['entry_ibs']:.2f} | "
        f"卖出 IBS>={strategy['exit_ibs']:.2f} | 最大持有 {strategy['max_hold']} 天"
    )

    position = state["positions"].get(asset)
    if position:
        position["days_held"] += 1
        hold_ret = close / position["buy_price"] - 1
        print(
            f"  持仓中: {position['buy_date']} @ {format_price(position['buy_price'])} | "
            f"{position['days_held']} 天 | 浮盈 {hold_ret * 100:+.2f}%"
        )

        if pd.notna(ibs) and ibs >= strategy["exit_ibs"]:
            maybe_record_trade(
                state,
                {
                    "asset": asset,
                    "strategy": "IBS",
                    "buy_date": position["buy_date"],
                    "sell_date": trade_date,
                    "buy_price": position["buy_price"],
                    "sell_price": round(close, 2),
                    "days": position["days_held"],
                    "ret": round(hold_ret * 100, 2),
                    "reason": f"IBS>={strategy['exit_ibs']:.2f}",
                    "entry_combo": position["entry_combo"],
                },
            )
            state["positions"][asset] = None
            signals.append(
                {
                    "asset": asset,
                    "action": "SELL",
                    "price": close,
                    "reason": f"IBS={ibs:.3f} >= {strategy['exit_ibs']:.2f}",
                }
            )
            print(f"  >> 卖出信号: IBS 退出 | 收益 {hold_ret * 100:+.2f}%")
        elif position["days_held"] >= strategy["max_hold"]:
            maybe_record_trade(
                state,
                {
                    "asset": asset,
                    "strategy": "IBS",
                    "buy_date": position["buy_date"],
                    "sell_date": trade_date,
                    "buy_price": position["buy_price"],
                    "sell_price": round(close, 2),
                    "days": position["days_held"],
                    "ret": round(hold_ret * 100, 2),
                    "reason": "MAX_HOLD",
                    "entry_combo": position["entry_combo"],
                },
            )
            state["positions"][asset] = None
            signals.append(
                {
                    "asset": asset,
                    "action": "SELL",
                    "price": close,
                    "reason": f"持有到期 ({strategy['max_hold']} 天)",
                }
            )
            print(f"  >> 卖出信号: 到期退出 | 收益 {hold_ret * 100:+.2f}%")
        else:
            print("  -- 继续持有")
        return signals

    combo_match = combo == strategy["entry_combo"]
    ibs_match = pd.notna(ibs) and ibs <= strategy["entry_ibs"]

    if combo_match and ibs_match:
        state["positions"][asset] = {
            "buy_date": trade_date,
            "buy_price": round(close, 2),
            "days_held": 0,
            "entry_combo": combo,
            "entry_ibs": round(float(ibs), 4),
        }
        signals.append(
            {
                "asset": asset,
                "action": "BUY",
                "price": close,
                "reason": f"Combo={combo}, IBS={ibs:.3f} <= {strategy['entry_ibs']:.2f}",
            }
        )
        print(f"  >> 买入信号: {combo} + IBS={ibs:.3f}")
        return signals

    reasons = []
    if not combo_match:
        reasons.append(f"Combo={combo}")
    if not ibs_match:
        reasons.append(f"IBS={ibs:.3f} > {strategy['entry_ibs']:.2f}" if pd.notna(ibs) else "IBS 不可用")
    print(f"  -- 无入场 ({', '.join(reasons)})")
    return signals


def process_monitors(
    dxj_daily: pd.DataFrame,
    ewj_daily: pd.DataFrame,
    combo: str,
) -> list[str]:
    notes: list[str] = []
    dxj_row = dxj_daily.iloc[-1]
    ewj_row = ewj_daily.iloc[-1]
    dxj_gap = dxj_row["Open"] / dxj_daily["Close"].shift(1).iloc[-1] - 1 if len(dxj_daily) > 1 else float("nan")

    print(f"\n  --- Monitor Only ---")
    for monitor in MONITOR_ONLY:
        if monitor["asset"] == "EWJ":
            row = ewj_row
            active = combo == monitor["combo"] and pd.notna(row["ibs"]) and row["ibs"] <= monitor["entry_ibs"]
            detail = f"Combo={combo}, IBS={row['ibs']:.3f}"
        else:
            active = combo == monitor["combo"] and pd.notna(dxj_gap) and dxj_gap <= monitor["gap_threshold"]
            detail = f"Combo={combo}, Gap={dxj_gap * 100:+.2f}%"

        if active:
            note = f"{monitor['label']}: {monitor['message']} ({detail})"
            notes.append(note)
            print(f"  >> {note}")
        else:
            print(f"  -- {monitor['label']}: 未激活 ({detail})")

    return notes


def print_recent_trades(state: dict) -> None:
    trades = state["trade_log"]
    if not trades:
        return

    recent = trades[-6:]
    print(f"\n  --- 最近交易 ---")
    print(f"  {'标的':>4} | {'买入日':>10} | {'卖出日':>10} | {'买入':>7} | {'卖出':>7} | {'天数':>2} | {'收益':>7} | 原因")
    print(f"  {'-' * 82}")
    for trade in recent:
        print(
            f"  {trade['asset']:>4} | {trade['buy_date']:>10} | {trade['sell_date']:>10} | "
            f"${trade['buy_price']:>6.2f} | ${trade['sell_price']:>6.2f} | {trade['days']:>2} | "
            f"{trade['ret']:>+6.2f}% | {trade['reason']}"
        )

    total_ret = sum(trade["ret"] for trade in trades)
    wins = sum(1 for trade in trades if trade["ret"] > 0)
    print(f"\n  累计: {len(trades)} 笔 | 胜率 {wins / len(trades) * 100:.0f}% | 总收益 {total_ret:+.1f}%")


def main() -> None:
    parser = argparse.ArgumentParser(description="DXJ / EWJ 核心条件信号引擎")
    parser.add_argument("--update", action="store_true", help="先更新 DXJ / EWJ 当日分钟数据")
    args = parser.parse_args()

    if args.update:
        update_data()

    state = load_state()
    ctx = load_context()
    daily_map = latest_daily_map()
    trade_date = latest_common_date(daily_map, ctx)
    trade_date_str = str(trade_date.date())

    dxj_daily = daily_map["DXJ"].loc[:trade_date]
    ewj_daily = daily_map["EWJ"].loc[:trade_date]
    dxj_row = dxj_daily.iloc[-1]
    ewj_row = ewj_daily.iloc[-1]
    ctx_row = ctx.loc[trade_date]
    combo = str(ctx_row["event_fx_combo"])

    if state.get("last_processed_date") == trade_date_str:
        save_status(
            build_status_payload(
                trade_date_str,
                ctx_row,
                dxj_row,
                ewj_row,
                [],
                process_monitors(dxj_daily, ewj_daily, combo),
                state["positions"],
                already_processed=True,
            )
        )
        print_snapshot(trade_date_str, state)
        return

    print_context(ctx_row, dxj_row, ewj_row)

    signals: list[dict] = []
    for strategy in CORE_STRATEGIES:
        asset_daily = dxj_daily if strategy["asset"] == "DXJ" else ewj_daily
        row = asset_daily.iloc[-1]
        signals.extend(process_core_strategy(strategy, row, combo, trade_date_str, state))

    monitor_notes = process_monitors(dxj_daily, ewj_daily, combo)
    print_recent_trades(state)

    if signals:
        print(f"\n  {'*' * 48}")
        for signal in signals:
            print(f"  * {signal['asset']} {signal['action']} @ {signal['price']:.2f} — {signal['reason']}")
        print(f"  {'*' * 48}")
    else:
        print("\n  今日无 Core 交易信号")

    if monitor_notes:
        print(f"\n  Monitor Notes:")
        for note in monitor_notes:
            print(f"  - {note}")

    state["last_processed_date"] = trade_date_str
    save_state(state)
    save_status(build_status_payload(trade_date_str, ctx_row, dxj_row, ewj_row, signals, monitor_notes, state["positions"]))
    print(f"\n状态已写入 {STATE_FILE}")
    print(f"监控快照已写入 {STATUS_FILE}")


if __name__ == "__main__":
    main()
