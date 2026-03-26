"""
DXJ / EWJ IBS 均值回归策略 — qbot Strategy 实现。

复用 japan_core_signal.py 的信号逻辑:
  - DXJ IBS: Buy ≤ 0.30, Sell ≥ 0.90, Max Hold 5 days (Cross-Hedge Divergence | Neutral)
  - EWJ IBS: Buy ≤ 0.25, Sell ≥ 0.60, Max Hold 2 days (Cross-Hedge Divergence | Neutral)

数据更新: update_dxj_today / update_ewj_today → load_daily → load_context
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保 qbot 和 DXJ 本地模块可导入
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from japan_core_signal import (
    CORE_STRATEGIES,
    MONITOR_ONLY,
    load_state,
    save_state,
    latest_daily_map,
    latest_common_date,
    update_data,
)
from analyze_fxy_interactions import load_context
from analyze_ibs_fx_regime import load_daily

from qbot.strategy_base import Strategy
from qbot.models import Signal, OrderSuggestion, CheckResult
from qbot import config, db
from qbot.log_util import get_logger

log = get_logger("dxj_strategy", "DXJ")


class DXJIBSStrategy(Strategy):
    """DXJ / EWJ IBS 均值回归策略。"""

    name = "DXJ_IBS"
    symbols = ["DXJ", "EWJ"]

    def __init__(self, do_update: bool = True):
        self.do_update = do_update

        # 用配置文件参数覆盖 CORE_STRATEGIES 默认值
        self.core_strategies = []
        for strat in CORE_STRATEGIES:
            asset = strat["asset"]
            cfg = config.strategy_params(f"{asset}_IBS")
            merged = {**strat}
            if cfg:
                if "quantity" in cfg:
                    merged["quantity"] = cfg["quantity"]
                if "entry_ibs" in cfg:
                    merged["entry_ibs"] = cfg["entry_ibs"]
                if "exit_ibs" in cfg:
                    merged["exit_ibs"] = cfg["exit_ibs"]
                if "max_hold" in cfg:
                    merged["max_hold"] = cfg["max_hold"]
            else:
                merged.setdefault("quantity", 100)
            self.core_strategies.append(merged)

        for s in self.core_strategies:
            log.info(f"{s['asset']}: qty={s.get('quantity', 100)}, "
                     f"entry_ibs≤{s['entry_ibs']}, exit_ibs≥{s['exit_ibs']}, "
                     f"max_hold={s['max_hold']}")

        self._state = None
        self._daily_map = None
        self._ctx = None
        self._trade_date = None
        self._combo = None

    def _load_data(self):
        """加载并缓存数据（避免重复加载）。"""
        if self._daily_map is not None:
            return

        if self.do_update:
            log.info("Updating DXJ / EWJ daily data...")
            update_data()

        self._state = load_state()
        self._ctx = load_context()
        self._daily_map = latest_daily_map()
        self._trade_date = latest_common_date(self._daily_map, self._ctx)
        trade_date_str = str(self._trade_date.date())

        ctx_row = self._ctx.loc[self._trade_date]
        self._combo = str(ctx_row["event_fx_combo"])

        log.info(f"Trade date: {trade_date_str}, Combo: {self._combo}")

    # ── 信号检查 ──────────────────────────────────────────

    def check_signals(self, market_data: dict) -> list[Signal]:
        self._load_data()

        trade_date_str = str(self._trade_date.date())

        # 检查是否已处理
        if self._state.get("last_processed_date") == trade_date_str:
            log.info(f"Date {trade_date_str} already processed, checking positions only")
            return self._check_exit_signals(trade_date_str)

        signals = []

        for strat in self.core_strategies:
            asset = strat["asset"]
            asset_daily = self._daily_map[asset].loc[:self._trade_date]
            row = asset_daily.iloc[-1]
            ibs = float(row["ibs"]) if pd.notna(row["ibs"]) else float("nan")
            close = float(row["Close"])

            position = self._state["positions"].get(asset)

            if position:
                # 检查退出条件
                position["days_held"] += 1
                hold_ret = close / position["buy_price"] - 1

                if pd.notna(ibs) and ibs >= strat["exit_ibs"]:
                    signals.append(Signal(
                        strategy=f"{asset}_IBS",
                        symbol=asset,
                        direction="SELL",
                        data={
                            "ibs": round(ibs, 4),
                            "exit_threshold": strat["exit_ibs"],
                            "close": close,
                            "entry_price": position["buy_price"],
                            "entry_date": position["buy_date"],
                            "days_held": position["days_held"],
                            "hold_return": round(hold_ret * 100, 2),
                            "reason": f"IBS={ibs:.3f} >= {strat['exit_ibs']:.2f}",
                            "combo": self._combo,
                        },
                    ))
                    self._state["positions"][asset] = None
                    self._close_db_position(f"{asset}_IBS", asset)

                elif position["days_held"] >= strat["max_hold"]:
                    signals.append(Signal(
                        strategy=f"{asset}_IBS",
                        symbol=asset,
                        direction="SELL",
                        data={
                            "ibs": round(ibs, 4) if pd.notna(ibs) else None,
                            "close": close,
                            "entry_price": position["buy_price"],
                            "entry_date": position["buy_date"],
                            "days_held": position["days_held"],
                            "hold_return": round(hold_ret * 100, 2),
                            "reason": f"Max hold {strat['max_hold']} days",
                            "combo": self._combo,
                        },
                    ))
                    self._state["positions"][asset] = None
                    self._close_db_position(f"{asset}_IBS", asset)
                else:
                    log.info(f"{asset}: holding (day {position['days_held']}/{strat['max_hold']}, "
                             f"IBS={ibs:.3f}, return={hold_ret*100:+.2f}%)")
            else:
                # 检查入场条件
                combo_match = self._combo == strat["entry_combo"]
                ibs_match = pd.notna(ibs) and ibs <= strat["entry_ibs"]

                if combo_match and ibs_match:
                    signals.append(Signal(
                        strategy=f"{asset}_IBS",
                        symbol=asset,
                        direction="BUY",
                        data={
                            "ibs": round(ibs, 4),
                            "entry_threshold": strat["entry_ibs"],
                            "close": close,
                            "combo": self._combo,
                            "max_hold": strat["max_hold"],
                            "exit_ibs": strat["exit_ibs"],
                            "reason": f"Combo={self._combo}, IBS={ibs:.3f} <= {strat['entry_ibs']:.2f}",
                        },
                    ))
                    # 记录持仓到 state
                    self._state["positions"][asset] = {
                        "buy_date": trade_date_str,
                        "buy_price": round(close, 2),
                        "days_held": 0,
                        "entry_combo": self._combo,
                        "entry_ibs": round(ibs, 4),
                    }
                    from qbot import db
                    db.open_position(f"{asset}_IBS", asset, strat.get("quantity", 100),
                                     round(close, 2), trade_date_str)
                else:
                    reasons = []
                    if not combo_match:
                        reasons.append(f"Combo={self._combo}")
                    if not ibs_match:
                        reasons.append(f"IBS={ibs:.3f}" if pd.notna(ibs) else "IBS N/A")
                    log.info(f"{asset}: no entry ({', '.join(reasons)})")

        # 更新 state
        self._state["last_processed_date"] = trade_date_str
        save_state(self._state)

        return signals

    def _check_exit_signals(self, trade_date_str: str) -> list[Signal]:
        """日期已处理时，仅检查持仓退出条件。"""
        signals = []
        for strat in self.core_strategies:
            asset = strat["asset"]
            position = self._state["positions"].get(asset)
            if position:
                log.info(f"{asset}: holding since {position['buy_date']} "
                         f"(day {position['days_held']}/{strat['max_hold']})")
        return signals

    @staticmethod
    def _close_db_position(strategy: str, symbol: str):
        from qbot import db
        for p in db.get_open_positions(strategy=strategy, symbol=symbol):
            db.close_position(p["id"])

    # ── 订单设计 ──────────────────────────────────────────

    def _get_quantity(self, symbol: str) -> int:
        """从配置获取交易数量。"""
        for strat in self.core_strategies:
            if strat["asset"] == symbol:
                return strat.get("quantity", 100)
        return 100

    def design_orders(self, signal: Signal) -> list[OrderSuggestion]:
        close = signal.data.get("close", 0)
        qty = self._get_quantity(signal.symbol)

        if signal.direction == "BUY":
            # 买入价 = close + 小幅 buffer
            target = round(close + 0.05, 2) if close else 0
            return [OrderSuggestion(
                symbol=signal.symbol,
                side="BUY",
                quantity=qty,
                order_type="LIMIT",
                suggested_price=target,
                notes=(
                    f"IBS: {signal.data.get('ibs', 'N/A')} (threshold: ≤{signal.data.get('entry_threshold', 'N/A')})\n"
                    f"Combo: {signal.data.get('combo', 'N/A')}\n"
                    f"Max Hold: {signal.data.get('max_hold', 'N/A')} days\n"
                    f"Exit Target: IBS ≥ {signal.data.get('exit_ibs', 'N/A')}"
                ),
            )]
        else:
            # 卖出价 = close (market-on-close 或 limit at close)
            target = round(close, 2) if close else 0
            entry_price = signal.data.get("entry_price", 0)
            hold_ret = signal.data.get("hold_return", 0)
            return [OrderSuggestion(
                symbol=signal.symbol,
                side="SELL",
                quantity=qty,
                order_type="LIMIT",
                suggested_price=target,
                notes=(
                    f"持仓: {signal.data.get('entry_date', '?')} @ ${entry_price:.2f}\n"
                    f"持有: {signal.data.get('days_held', '?')} 天\n"
                    f"预估收益: {hold_ret:+.2f}%\n"
                    f"退出原因: {signal.data.get('reason', 'N/A')}"
                ),
            )]

    # ── 安全检查 ──────────────────────────────────────────

    def safety_checks(self, signal: Signal) -> list[CheckResult]:
        checks = []

        # Combo 匹配检查
        combo = signal.data.get("combo", "")
        if signal.direction == "BUY":
            # 找到对应策略
            for strat in self.core_strategies:
                if strat["asset"] == signal.symbol:
                    if combo == strat["entry_combo"]:
                        checks.append(CheckResult("combo_match", True, f"Combo: {combo}"))
                    else:
                        checks.append(CheckResult("combo_match", False,
                                                   f"Combo mismatch: {combo} != {strat['entry_combo']}"))
                    break

            # 熔断器检查
            from qbot.safety import check_circuit_breaker
            checks.append(check_circuit_breaker(f"{signal.symbol}_IBS"))

            # 持仓检查
            positions = db.get_open_positions(strategy=f"{signal.symbol}_IBS", symbol=signal.symbol)
            if positions:
                checks.append(CheckResult("no_existing_position", False,
                                          f"Already holding {signal.symbol}"))
            else:
                checks.append(CheckResult("no_existing_position", True,
                                          f"No existing {signal.symbol} position"))
        else:
            # 卖出信号直接通过
            checks.append(CheckResult("exit_valid", True, signal.data.get("reason", "Exit condition met")))

        return checks
