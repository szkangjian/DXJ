#!/usr/bin/env python3
"""
DXJ / EWJ IBS 信号 — launchd 调度入口。

用法:
  python dxj_orchestrator.py                  # 正常模式: 更新数据 + 信号检查
  python dxj_orchestrator.py --no-update      # 跳过数据更新 (已有当日数据)
  python dxj_orchestrator.py --test           # 测试模式: 用当前数据生成信号
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 确保 qbot 和 DXJ 本地模块可导入
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from qbot import signal_bus, notifier, order_placer, db
from qbot.log_util import get_logger
from qbot.safety import check_is_weekday

log = get_logger("orchestrator", "DXJ")


def run(do_update: bool = True):
    """正常运行：更新数据 + 信号检查 + 通知。"""
    log.info("=== DXJ/EWJ Signal Check ===")

    wd = check_is_weekday()
    if not wd.passed:
        log.info(f"Skip: {wd.detail}")
        return

    from dxj_strategy import DXJIBSStrategy
    strategy = DXJIBSStrategy(do_update=do_update)

    results = signal_bus.run_strategy(
        strategy,
        notifier=notifier,
        order_placer=order_placer,
    )

    if not results:
        log.info("No signals today")
        # 发一个简短的状态通知
        _send_daily_status(strategy)
    else:
        for r in results:
            sig = r["signal"]
            passed = r["all_passed"]
            status = "SENT" if passed else "BLOCKED"
            log.info(f"{sig.symbol} {sig.direction} {status}: {sig.data.get('reason', '')}")


def _send_daily_status(strategy):
    """无信号时发送简短状态（可选，避免太频繁）。"""
    if strategy._state is None:
        return

    positions = strategy._state.get("positions", {})
    holding = [f"{k}: day {v['days_held']}" for k, v in positions.items() if v]

    if holding:
        notifier.send_text(
            f"📊 DXJ/EWJ 日报\n\n"
            f"Combo: {strategy._combo}\n"
            f"持仓: {', '.join(holding)}\n"
            f"今日无新信号"
        )


def main():
    parser = argparse.ArgumentParser(description="DXJ/EWJ Orchestrator")
    parser.add_argument("--no-update", action="store_true",
                        help="跳过数据更新")
    parser.add_argument("--test", action="store_true",
                        help="测试模式（不更新数据，强制运行信号检查）")
    args = parser.parse_args()

    try:
        do_update = not (args.no_update or args.test)
        run(do_update=do_update)
    except Exception as e:
        log.error(f"Orchestrator error: {e}", exc_info=True)
        notifier.send_alert("DXJ Orchestrator Error", str(e), level="ERROR")
        raise


if __name__ == "__main__":
    main()
