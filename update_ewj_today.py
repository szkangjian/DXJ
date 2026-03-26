"""
EWJ 当日分钟数据更新入口。
"""

from __future__ import annotations

import update_dxj_today as base


def main():
    # 临时切换全局变量，跑完还原
    orig_ticker, orig_csv = base.TICKER, base.MAIN_CSV
    base.TICKER = "EWJ"
    base.MAIN_CSV = "ewj_minute_data.csv"
    try:
        base.main()
    finally:
        base.TICKER, base.MAIN_CSV = orig_ticker, orig_csv


if __name__ == "__main__":
    main()
