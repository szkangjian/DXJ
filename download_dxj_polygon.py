"""
从 Polygon.io 分批下载 DXJ 的 1 分钟历史数据。

默认下载近两年数据，并按 90 天分批，兼顾免费版的 50,000 条上限
和每分钟 5 次请求的速率限制。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pandas as pd
import requests

from config import POLYGON_KEY


API_KEY = POLYGON_KEY
TICKER = "DXJ"
OUTPUT_FILE = "dxj_minute_data.csv"
START_DATE = datetime(2024, 3, 1).date()
END_DATE = datetime.now().date()
BATCH_DAYS = 90
REQUEST_INTERVAL = 13


def fetch_batch(date_from: str, date_to: str) -> pd.DataFrame | None:
    """获取一批分钟数据。"""
    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{TICKER}/range/1/minute/"
        f"{date_from}/{date_to}"
        f"?adjusted=true&sort=asc&limit=50000&apiKey={API_KEY}"
    )
    resp = requests.get(url, timeout=30)

    if resp.status_code == 200:
        results = resp.json().get("results", [])
        if not results:
            return None

        df = pd.DataFrame(results)
        # Polygon 返回的是 UTC 时间戳，这里统一转成美东时间并去掉时区。
        df["timestamp"] = (
            pd.to_datetime(df["t"], unit="ms", utc=True)
            .dt.tz_convert("US/Eastern")
            .dt.tz_localize(None)
        )
        df.set_index("timestamp", inplace=True)
        df.rename(
            columns={
                "o": "Open",
                "h": "High",
                "l": "Low",
                "c": "Close",
                "v": "Volume",
                "vw": "VWAP",
                "n": "Trades",
            },
            inplace=True,
        )
        return df[["Open", "High", "Low", "Close", "Volume", "VWAP", "Trades"]]

    if resp.status_code == 429:
        print("  rate limited, waiting 60s before retry...")
        time.sleep(60)
        return fetch_batch(date_from, date_to)

    print(f"  request failed: {resp.status_code} - {resp.text[:200]}")
    return None


def main() -> None:
    print(f"Downloading {TICKER} minute data")
    print(f"  range: {START_DATE} -> {END_DATE}")
    print(f"  batch size: {BATCH_DAYS} days")
    print(f"  interval: {REQUEST_INTERVAL}s")
    print()

    current_start = START_DATE
    all_dfs: list[pd.DataFrame] = []
    total_rows = 0
    batch_num = 0

    while current_start <= END_DATE:
        current_end = min(current_start + timedelta(days=BATCH_DAYS - 1), END_DATE)
        date_from = current_start.strftime("%Y-%m-%d")
        date_to = current_end.strftime("%Y-%m-%d")
        batch_num += 1

        print(f"[{batch_num:02d}] {date_from} -> {date_to} ... ", end="", flush=True)
        df = fetch_batch(date_from, date_to)
        if df is None or df.empty:
            print("no data")
        else:
            all_dfs.append(df)
            total_rows += len(df)
            print(f"{len(df):,} rows (total {total_rows:,})")

        current_start = current_end + timedelta(days=1)
        if current_start <= END_DATE:
            time.sleep(REQUEST_INTERVAL)

    if not all_dfs:
        print("No data downloaded.")
        return

    final_df = pd.concat(all_dfs).sort_index()
    final_df = final_df[~final_df.index.duplicated(keep="first")]
    final_df.to_csv(OUTPUT_FILE)

    print()
    print("Download complete")
    print(f"  rows: {len(final_df):,}")
    print(f"  span: {final_df.index.min()} -> {final_df.index.max()}")
    print(f"  file: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
