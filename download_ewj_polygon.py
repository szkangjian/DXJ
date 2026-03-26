"""
EWJ 分钟级数据下载入口。

复用 DXJ 下载逻辑，只替换标的和输出文件。
"""

from __future__ import annotations

import download_dxj_polygon as base


base.TICKER = "EWJ"
base.OUTPUT_FILE = "ewj_minute_data.csv"


if __name__ == "__main__":
    base.main()
