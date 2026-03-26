"""
EWJ 底层研究入口。
"""

from __future__ import annotations

from pathlib import Path

import dxj_backtest as base


base.TICKER = "EWJ"
base.CSV_FILE = Path("ewj_minute_data.csv")
base.DOC_FILE = Path("docs/01_ewj_research.md")


if __name__ == "__main__":
    base.main()
