"""
EWJ 驱动映射入口。
"""

from __future__ import annotations

from pathlib import Path

import analyze_dxj_correlation as base


base.TARGET_TICKER = "EWJ"
base.DOC_FILE = Path("docs/02_ewj_event_drivers.md")


if __name__ == "__main__":
    base.main()
