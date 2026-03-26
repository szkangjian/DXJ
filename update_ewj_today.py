"""
EWJ 当日分钟数据更新入口。
"""

from __future__ import annotations

import update_dxj_today as base


base.TICKER = "EWJ"
base.MAIN_CSV = "ewj_minute_data.csv"


if __name__ == "__main__":
    base.main()
