"""
DXJ 底层研究脚本。

读取分钟级数据，生成日线统计、极端事件恢复、成交量分布、除息行为分析，
并将结果写入 docs/01_dxj_research.md。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from config import POLYGON_KEY


TICKER = "DXJ"
CSV_FILE = Path("dxj_minute_data.csv")
DOC_FILE = Path("docs/01_dxj_research.md")


@dataclass
class RecoverySummary:
    total: int
    within_3d: int
    within_5d: int
    within_10d: int
    unrecovered_30d: int


def fetch_ex_dates() -> pd.DataFrame:
    """优先从 Polygon 获取除息日，失败则回退到 yfinance。"""
    url = (
        "https://api.polygon.io/v3/reference/dividends"
        f"?ticker={TICKER}&limit=50&apiKey={POLYGON_KEY}"
    )
    try:
        resp = requests.get(url, timeout=30).json()
        results = resp.get("results", [])
        if results:
            rows = []
            for row in results:
                ex_date = row.get("ex_dividend_date")
                if not ex_date:
                    continue
                rows.append(
                    {
                        "ex_date": pd.to_datetime(ex_date),
                        "amount": float(row.get("cash_amount", 0) or 0),
                    }
                )
            if rows:
                return pd.DataFrame(rows).sort_values("ex_date").reset_index(drop=True)
    except Exception:
        pass

    try:
        ticker = yf.Ticker(TICKER)
        dividends = ticker.dividends
        if dividends.empty:
            return pd.DataFrame(columns=["ex_date", "amount"])

        dividends.index = dividends.index.tz_localize(None)
        return (
            pd.DataFrame({"ex_date": dividends.index, "amount": dividends.values})
            .sort_values("ex_date")
            .reset_index(drop=True)
        )
    except Exception:
        return pd.DataFrame(columns=["ex_date", "amount"])


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not CSV_FILE.exists():
        raise SystemExit(f"Missing {CSV_FILE}. Run download_dxj_polygon.py first.")

    minute_df = pd.read_csv(CSV_FILE, parse_dates=["timestamp"])
    minute_df = minute_df.sort_values("timestamp").reset_index(drop=True)
    minute_df["timestamp"] = pd.to_datetime(minute_df["timestamp"])

    # 旧版下载脚本保存的是 UTC-naive 时间戳，若检测到晚于 21:00 的大量样本，
    # 说明还未转到美东时间，这里统一在内存中修正。
    if minute_df["timestamp"].dt.hour.max() > 21:
        minute_df["timestamp"] = (
            minute_df["timestamp"]
            .dt.tz_localize("UTC")
            .dt.tz_convert("US/Eastern")
            .dt.tz_localize(None)
        )
    minute_df.set_index("timestamp", inplace=True)
    minute_df = minute_df.between_time("09:30", "16:00").copy()
    minute_df["hour"] = minute_df.index.hour
    minute_df["date"] = minute_df.index.date
    minute_df["dollar_volume"] = minute_df["Close"] * minute_df["Volume"]

    daily_df = (
        minute_df.resample("D")
        .agg(
            Open=("Open", "first"),
            High=("High", "max"),
            Low=("Low", "min"),
            Close=("Close", "last"),
            Volume=("Volume", "sum"),
            DollarVolume=("dollar_volume", "sum"),
        )
        .dropna()
    )
    daily_df["ret"] = daily_df["Close"].pct_change()
    daily_df["ma200"] = daily_df["Close"].rolling(200).mean()
    daily_df["intraday_range_pct"] = (daily_df["High"] - daily_df["Low"]) / daily_df["Open"] * 100
    daily_df["gap_pct"] = daily_df["Open"] / daily_df["Close"].shift(1) - 1
    daily_df["close_vs_ma200"] = daily_df["Close"] > daily_df["ma200"]
    return minute_df, daily_df


def find_recovery_days(daily_df: pd.DataFrame, loc: int, pre_drop_price: float) -> int | None:
    for step in range(1, min(31, len(daily_df) - loc)):
        if daily_df.iloc[loc + step]["Close"] >= pre_drop_price * 0.995:
            return step
    return None


def summarize_recoveries(daily_df: pd.DataFrame, threshold: float) -> RecoverySummary:
    drops = daily_df[daily_df["ret"] <= threshold]
    within_3d = 0
    within_5d = 0
    within_10d = 0
    unrecovered_30d = 0

    for date in drops.index:
        loc = daily_df.index.get_loc(date)
        if loc == 0:
            continue
        pre_drop = daily_df.iloc[loc - 1]["Close"]
        recovery = find_recovery_days(daily_df, loc, pre_drop)
        if recovery is None:
            unrecovered_30d += 1
            continue
        if recovery <= 3:
            within_3d += 1
        if recovery <= 5:
            within_5d += 1
        if recovery <= 10:
            within_10d += 1

    return RecoverySummary(
        total=len(drops),
        within_3d=within_3d,
        within_5d=within_5d,
        within_10d=within_10d,
        unrecovered_30d=unrecovered_30d,
    )


def collect_big_drop_events(daily_df: pd.DataFrame, threshold: float = -0.02) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    drops = daily_df[daily_df["ret"] <= threshold]

    for date, row in drops.tail(12).iterrows():
        loc = daily_df.index.get_loc(date)
        pre_drop = daily_df.iloc[loc - 1]["Close"] if loc > 0 else row["Open"]
        recovery = find_recovery_days(daily_df, loc, pre_drop)
        future_rets = []
        for step in (1, 3, 5):
            if loc + step < len(daily_df):
                future_close = daily_df.iloc[loc + step]["Close"]
                future_rets.append(f"D+{step}:{(future_close / row['Close'] - 1) * 100:+.1f}%")
        rows.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "open": f"${row['Open']:.2f}",
                "close": f"${row['Close']:.2f}",
                "drop": f"{row['ret'] * 100:+.2f}%",
                "low": f"${row['Low']:.2f}",
                "recovery": f"{recovery}d" if recovery is not None else ">30d",
                "path": " ".join(future_rets) if future_rets else "N/A",
            }
        )
    return rows


def analyze_ex_div(daily_df: pd.DataFrame, div_df: pd.DataFrame) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if div_df.empty:
        return rows

    for _, row in div_df.iterrows():
        ex_date = row["ex_date"]
        amount = float(row["amount"])
        matches = daily_df.index[daily_df.index >= ex_date]
        if len(matches) == 0:
            continue
        actual_ex = matches[0]
        loc = daily_df.index.get_loc(actual_ex)
        if loc < 1:
            continue

        prev_close = daily_df.iloc[loc - 1]["Close"]
        ex_open = daily_df.iloc[loc]["Open"]
        actual_drop = prev_close - ex_open
        cushion = amount - actual_drop

        rows.append(
            {
                "date": actual_ex.strftime("%Y-%m-%d"),
                "prev_close": f"${prev_close:.2f}",
                "ex_open": f"${ex_open:.2f}",
                "amount": f"${amount:.3f}",
                "actual_drop": f"{actual_drop:+.3f}",
                "cushion": f"{cushion:+.3f}",
            }
        )
    return rows


def build_report(minute_df: pd.DataFrame, daily_df: pd.DataFrame, div_rows: list[dict[str, str]]) -> str:
    minute_ranges = minute_df["High"] - minute_df["Low"]
    nonzero_ranges = minute_ranges[minute_ranges > 0]
    avg_price = float(minute_df["Close"].mean())
    avg_daily_volume = float(daily_df["Volume"].mean())
    avg_daily_dollar_volume = float(daily_df["DollarVolume"].mean())

    vol20 = daily_df["ret"].rolling(20).std() * np.sqrt(252) * 100
    vol60 = daily_df["ret"].rolling(60).std() * np.sqrt(252) * 100

    gt2 = summarize_recoveries(daily_df, -0.02)
    gt3 = summarize_recoveries(daily_df, -0.03)
    gt5 = summarize_recoveries(daily_df, -0.05)
    big_drop_rows = collect_big_drop_events(daily_df)

    hourly_volume = minute_df.groupby("hour")["Volume"].sum()
    hourly_share = hourly_volume / hourly_volume.sum() * 100
    top_hours = hourly_share.sort_values(ascending=False).head(4)

    yearly_close = daily_df["Close"].resample("YE").last()
    yearly_lines = []
    for i in range(1, len(yearly_close)):
        prev = yearly_close.iloc[i - 1]
        curr = yearly_close.iloc[i]
        ret = (curr / prev - 1) * 100
        yearly_lines.append(f"- {yearly_close.index[i].year}: {ret:+.1f}%")
    if not yearly_lines:
        yearly_lines.append("- 样本不足，暂未形成完整年度比较")

    latest_close = float(daily_df["Close"].iloc[-1])
    current_ma200 = daily_df["ma200"].iloc[-1]
    above_ma200_pct = daily_df["close_vs_ma200"].dropna().mean() * 100 if daily_df["close_vs_ma200"].notna().any() else np.nan

    observations = []
    if nonzero_ranges.median() / avg_price * 100 < 0.05:
        observations.append("分钟级价差代理很窄，基础交易摩擦较低，具备研究短线策略的必要条件。")
    else:
        observations.append("分钟级价差代理不算窄，短线策略需更严格计入成本和滑点。")

    if gt2.total > 0 and gt2.within_3d / gt2.total >= 0.55:
        observations.append("较大单日下跌后在 3 个交易日内修复的比例偏高，短期均值回归值得进入下一阶段验证。")
    else:
        observations.append("大跌后的快速修复比例不高，不能先验假设均值回归是主要模式。")

    if pd.notna(above_ma200_pct) and above_ma200_pct >= 60:
        observations.append("样本期内收盘多数时间位于 MA200 上方，后续应测试趋势过滤后的回撤交易。")
    else:
        observations.append("价格相对 MA200 并无稳定优势，趋势过滤未必是核心条件。")

    if top_hours.index.max() >= 15:
        observations.append("成交量明显集中在尾盘时段，实际执行和信号判定应优先考虑收盘附近的流动性。")

    lines = [
        f"# {TICKER} 底层研究",
        "",
        f"> 生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f">",
        f"> 数据范围: {minute_df.index.min()} -> {minute_df.index.max()}",
        f"> 分钟数据量: {len(minute_df):,} 条 | 日线样本: {len(daily_df)} 天",
        "",
        "## 一、价格与流动性画像",
        "",
        "| 指标 | 数值 |",
        "| ---- | ---- |",
        f"| 平均价格 | ${avg_price:.2f} |",
        f"| 分钟级非零波幅中位数 | ${nonzero_ranges.median():.4f} |",
        f"| 分钟级非零波幅占价格比 | {nonzero_ranges.median() / avg_price * 100:.3f}% |",
        f"| 零波幅分钟占比 | {(minute_ranges == 0).mean() * 100:.1f}% |",
        f"| 日均成交量 | {avg_daily_volume:,.0f} 股 |",
        f"| 日均成交额 | ${avg_daily_dollar_volume / 1_000_000:.1f}M |",
        "",
        "## 二、波动率结构",
        "",
        "| 指标 | 数值 |",
        "| ---- | ---- |",
        f"| 日内波动率中位数 | {daily_df['intraday_range_pct'].median():.2f}% |",
        f"| 20 日年化波动率均值 | {vol20.mean():.1f}% |",
        f"| 20 日年化波动率当前值 | {vol20.iloc[-1]:.1f}% |",
        f"| 60 日年化波动率当前值 | {vol60.iloc[-1]:.1f}% |",
        f"| 最大单日跌幅 | {daily_df['ret'].min() * 100:+.2f}% |",
        f"| 最大单日涨幅 | {daily_df['ret'].max() * 100:+.2f}% |",
        f"| 当前收盘价 | ${latest_close:.2f} |",
        f"| 当前 MA200 | ${current_ma200:.2f} |" if pd.notna(current_ma200) else "| 当前 MA200 | N/A |",
        f"| 收盘位于 MA200 上方占比 | {above_ma200_pct:.1f}% |" if pd.notna(above_ma200_pct) else "| 收盘位于 MA200 上方占比 | N/A |",
        "",
        "## 三、收益率分布",
        "",
        "| 指标 | 数值 |",
        "| ---- | ---- |",
        f"| 日均收益率 | {daily_df['ret'].mean() * 100:.3f}% |",
        f"| 日收益率标准差 | {daily_df['ret'].std() * 100:.3f}% |",
        f"| 偏度 | {daily_df['ret'].skew():.3f} |",
        f"| 峰度 | {daily_df['ret'].kurtosis():.3f} |",
        f"| 正收益天数占比 | {(daily_df['ret'] > 0).mean() * 100:.1f}% |",
        "",
        "## 四、极端下跌后的恢复特征",
        "",
        "| 跌幅阈值 | 事件数 | 3 日内恢复 | 5 日内恢复 | 10 日内恢复 | 30 日未恢复 |",
        "| -------- | ------ | ---------- | ---------- | ----------- | ----------- |",
        f"| <= -2% | {gt2.total} | {gt2.within_3d} | {gt2.within_5d} | {gt2.within_10d} | {gt2.unrecovered_30d} |",
        f"| <= -3% | {gt3.total} | {gt3.within_3d} | {gt3.within_5d} | {gt3.within_10d} | {gt3.unrecovered_30d} |",
        f"| <= -5% | {gt5.total} | {gt5.within_3d} | {gt5.within_5d} | {gt5.within_10d} | {gt5.unrecovered_30d} |",
        "",
        "### 最近 12 次单日跌幅超过 2% 的样本",
        "",
        "| 日期 | 开盘 | 收盘 | 日收益 | 最低价 | 恢复时间 | 后续路径 |",
        "| ---- | ---- | ---- | ------ | ------ | -------- | -------- |",
    ]

    for row in big_drop_rows:
        lines.append(
            f"| {row['date']} | {row['open']} | {row['close']} | {row['drop']} | {row['low']} | {row['recovery']} | {row['path']} |"
        )

    lines.extend(
        [
            "",
            "## 五、成交量时间分布",
            "",
            "| 小时 (ET) | 成交量占比 |",
            "| --------- | ---------- |",
        ]
    )
    for hour, share in top_hours.items():
        lines.append(f"| {hour:02d}:00 | {share:.1f}% |")

    lines.extend(
        [
            "",
            "## 六、除息行为",
            "",
            "| 除息日 | 前日收盘 | 除息日开盘 | 股息 | 实际跳空 | Cushion |",
            "| ------ | -------- | ---------- | ---- | -------- | ------- |",
        ]
    )
    if div_rows:
        for row in div_rows:
            lines.append(
                f"| {row['date']} | {row['prev_close']} | {row['ex_open']} | {row['amount']} | {row['actual_drop']} | {row['cushion']} |"
            )
    else:
        lines.append("| 无可用除息样本 | - | - | - | - | - |")

    lines.extend(
        [
            "",
            "## 七、年度收盘表现",
            "",
            *yearly_lines,
            "",
            "## 八、第一轮观察",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in observations])
    lines.extend(
        [
            "",
            "这些观察只是第一轮统计结论，还不是策略结论。",
            "下一步应进入驱动映射，确认大波动究竟更受汇率、日股 beta、美国风险偏好还是结构性日期影响。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    minute_df, daily_df = load_data()
    div_df = fetch_ex_dates()
    div_rows = analyze_ex_div(daily_df, div_df)
    report = build_report(minute_df, daily_df, div_rows)
    DOC_FILE.write_text(report, encoding="utf-8")

    print(f"Loaded {len(minute_df):,} minute rows and {len(daily_df)} daily rows.")
    print(f"Wrote research report to {DOC_FILE}")
    print(f"Range: {minute_df.index.min()} -> {minute_df.index.max()}")
    print(f"Latest close: ${daily_df['Close'].iloc[-1]:.2f}")


if __name__ == "__main__":
    main()
