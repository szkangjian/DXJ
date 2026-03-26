"""
从 Yahoo Finance 获取今天的 DXJ 1 分钟数据，并追加到主数据文件。
"""

from __future__ import annotations

import pandas as pd
import yfinance as yf


MAIN_CSV = "dxj_minute_data.csv"
TICKER = "DXJ"


def main() -> None:
    print(f"Fetching today's {TICKER} minute data from Yahoo Finance...")
    data = yf.download(TICKER, period="1d", interval="1m", progress=False)

    if data.empty:
        raise SystemExit("No intraday data returned from Yahoo Finance.")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data.index = data.index.tz_convert("US/Eastern").tz_localize(None)
    data.index.name = "timestamp"
    data = data[["Open", "High", "Low", "Close", "Volume"]]

    hist = pd.read_csv(MAIN_CSV, index_col="timestamp", parse_dates=True)

    # 兼容旧版下载脚本产生的 UTC-naive 历史文件。
    if hist.index.hour.max() > 21:
        hist.index = (
            hist.index.tz_localize("UTC")
            .tz_convert("US/Eastern")
            .tz_localize(None)
        )
    combined = pd.concat([hist, data])
    combined = combined[~combined.index.duplicated(keep="last")]
    combined.sort_index(inplace=True)
    combined.to_csv(MAIN_CSV)

    print(f"Appended {len(data):,} rows. Total rows: {len(combined):,}")
    print(f"Range: {combined.index.min()} -> {combined.index.max()}")


if __name__ == "__main__":
    main()
