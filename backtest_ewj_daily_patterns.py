"""
EWJ 日线规律扫描入口。
"""

from __future__ import annotations

from pathlib import Path

import backtest_dxj_daily_patterns as base


base.TICKER = "EWJ"
base.CSV_FILE = Path("ewj_minute_data.csv")
base.DOC_FILE = Path("docs/03_ewj_strategy_research.md")


if __name__ == "__main__":
    base.main()
