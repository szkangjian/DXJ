"""
比较 DXJ 与 EWJ 的底层统计和第一轮策略规律。

依赖本地分钟数据文件：
- dxj_minute_data.csv
- ewj_minute_data.csv
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


DOC_FILE = Path("docs/07_dxj_ewj_comparison.md")


def load_daily(csv_file: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(csv_file, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    if df["timestamp"].dt.hour.max() > 21:
        df["timestamp"] = (
            df["timestamp"]
            .dt.tz_localize("UTC")
            .dt.tz_convert("US/Eastern")
            .dt.tz_localize(None)
        )

    df["dollar_volume"] = df["Close"] * df["Volume"]
    df = df.sort_values("timestamp").reset_index(drop=True)
    df.set_index("timestamp", inplace=True)
    df = df.between_time("09:30", "16:00").copy()

    daily = (
        df.resample("D")
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
    daily["ret"] = daily["Close"].pct_change()
    daily["gap_pct"] = daily["Open"] / daily["Close"].shift(1) - 1
    daily["ibs"] = (daily["Close"] - daily["Low"]) / (daily["High"] - daily["Low"])
    daily["ma200"] = daily["Close"].rolling(200).mean()
    daily["above_ma200"] = daily["Close"] > daily["ma200"]
    daily["intraday_range_pct"] = (daily["High"] - daily["Low"]) / daily["Open"] * 100
    return df, daily


def summarize_asset(minute_df: pd.DataFrame, daily_df: pd.DataFrame) -> dict[str, float]:
    minute_ranges = minute_df["High"] - minute_df["Low"]
    nonzero_ranges = minute_ranges[minute_ranges > 0]
    vol20 = daily_df["ret"].rolling(20).std() * (252 ** 0.5) * 100

    return {
        "avg_price": float(minute_df["Close"].mean()),
        "spread_proxy": float(nonzero_ranges.median()),
        "spread_pct": float(nonzero_ranges.median() / minute_df["Close"].mean() * 100),
        "zero_range_pct": float((minute_ranges == 0).mean() * 100),
        "avg_daily_volume": float(daily_df["Volume"].mean()),
        "avg_daily_dollar_volume": float(daily_df["DollarVolume"].mean()),
        "intraday_vol_med": float(daily_df["intraday_range_pct"].median()),
        "vol20_avg": float(vol20.mean()),
        "vol20_latest": float(vol20.iloc[-1]),
        "max_down": float(daily_df["ret"].min() * 100),
        "max_up": float(daily_df["ret"].max() * 100),
    }


def summarize_recovery(daily_df: pd.DataFrame, threshold: float) -> tuple[int, int]:
    drops = daily_df[daily_df["ret"] <= threshold]
    recovered = 0
    for date in drops.index:
        loc = daily_df.index.get_loc(date)
        if loc == 0:
            continue
        pre_drop = daily_df.iloc[loc - 1]["Close"]
        recovered_flag = False
        for step in range(1, min(6, len(daily_df) - loc)):
            if daily_df.iloc[loc + step]["Close"] >= pre_drop * 0.995:
                recovered += 1
                recovered_flag = True
                break
        if not recovered_flag:
            continue
    return len(drops), recovered


def scan_ibs(daily_df: pd.DataFrame) -> dict[str, float | str]:
    results = []
    for ibs_buy in [0.10, 0.15, 0.20, 0.25, 0.30]:
        for ibs_sell in [0.60, 0.70, 0.80, 0.90]:
            for max_hold in [1, 2, 3, 5, 10]:
                position = None
                trades = []
                for idx, row in daily_df.iterrows():
                    if position is not None:
                        position["days"] += 1
                        if row["ibs"] >= ibs_sell or position["days"] >= max_hold:
                            ret = row["Close"] / position["buy_price"] - 1
                            trades.append(ret)
                            position = None
                            continue
                    if position is None and pd.notna(row["ibs"]) and row["ibs"] <= ibs_buy:
                        position = {"buy_price": row["Close"], "days": 0}
                if trades:
                    s = pd.Series(trades)
                    results.append(
                        {
                            "entry": f"IBS<={ibs_buy:.2f}",
                            "exit": f"IBS>={ibs_sell:.2f}",
                            "hold": max_hold,
                            "n": len(s),
                            "wr": float((s > 0).mean() * 100),
                            "total": float(s.sum() * 100),
                            "avg": float(s.mean() * 100),
                        }
                    )
    return pd.DataFrame(results).sort_values(["total", "avg", "wr"], ascending=False).iloc[0].to_dict()


def scan_gap(daily_df: pd.DataFrame) -> dict[str, float | str]:
    results = []
    rows = daily_df.reset_index()
    for gap_threshold in [-0.01, -0.015, -0.02, -0.025, -0.03]:
        for hold_days in [0, 1, 2, 3, 5]:
            i = 1
            trades = []
            while i < len(rows):
                row = rows.iloc[i]
                if row["gap_pct"] <= gap_threshold:
                    exit_i = min(i + hold_days, len(rows) - 1)
                    exit_row = rows.iloc[exit_i]
                    trades.append(exit_row["Close"] / row["Open"] - 1)
                    i = exit_i + 1
                else:
                    i += 1
            if trades:
                s = pd.Series(trades)
                results.append(
                    {
                        "entry": f"Gap<={gap_threshold * 100:.1f}%",
                        "exit": f"Hold {hold_days}d",
                        "hold": hold_days + 1,
                        "n": len(s),
                        "wr": float((s > 0).mean() * 100),
                        "total": float(s.sum() * 100),
                        "avg": float(s.mean() * 100),
                    }
                )
    return pd.DataFrame(results).sort_values(["total", "avg", "wr"], ascending=False).iloc[0].to_dict()


def build_report(dxj_minute: pd.DataFrame, dxj_daily: pd.DataFrame, ewj_minute: pd.DataFrame, ewj_daily: pd.DataFrame) -> str:
    dxj_stats = summarize_asset(dxj_minute, dxj_daily)
    ewj_stats = summarize_asset(ewj_minute, ewj_daily)

    dxj_drops, dxj_recovered = summarize_recovery(dxj_daily, -0.02)
    ewj_drops, ewj_recovered = summarize_recovery(ewj_daily, -0.02)

    merged = pd.DataFrame(
        {
            "DXJ": dxj_daily["ret"],
            "EWJ": ewj_daily["ret"],
        }
    ).dropna()
    relative = (1 + merged["DXJ"]).cumprod() / (1 + merged["EWJ"]).cumprod()

    dxj_ibs = scan_ibs(dxj_daily)
    ewj_ibs = scan_ibs(ewj_daily)
    dxj_gap = scan_gap(dxj_daily)
    ewj_gap = scan_gap(ewj_daily)

    observation_lines = []
    if dxj_stats["vol20_avg"] > ewj_stats["vol20_avg"]:
        observation_lines.append("DXJ 的中短期波动率高于 EWJ，说明日元对冲后的日本股票暴露在当前样本里更激进。")
    else:
        observation_lines.append("EWJ 的波动并不低于 DXJ，说明汇率未对冲并没有明显抬高整体波动。")

    if dxj_recovered / dxj_drops > ewj_recovered / ewj_drops:
        observation_lines.append("DXJ 在大跌后的 5 日修复比例高于 EWJ，后续应重点研究对冲结构是否放大了均值回归。")
    else:
        observation_lines.append("EWJ 在大跌后的 5 日修复比例不弱于 DXJ，说明简单把对冲版本视为更易修复并不成立。")

    if dxj_ibs["total"] > ewj_ibs["total"]:
        observation_lines.append("第一轮 IBS 扫描里 DXJ 强于 EWJ，说明收盘位置对 DXJ 的信息量更高。")
    else:
        observation_lines.append("第一轮 IBS 扫描里 EWJ 不弱于 DXJ，说明未对冲版本同样值得继续深挖 IBS 类模式。")

    lines = [
        "# DXJ vs EWJ 对比研究（第一版）",
        "",
        f"> 生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 样本区间: {max(dxj_daily.index.min(), ewj_daily.index.min()).date()} -> {min(dxj_daily.index.max(), ewj_daily.index.max()).date()}",
        "",
        "## 一、底层资产画像对比",
        "",
        "| 指标 | DXJ | EWJ |",
        "| ---- | --- | --- |",
        f"| 平均价格 | ${dxj_stats['avg_price']:.2f} | ${ewj_stats['avg_price']:.2f} |",
        f"| 分钟级波幅中位数 | ${dxj_stats['spread_proxy']:.4f} | ${ewj_stats['spread_proxy']:.4f} |",
        f"| 分钟级波幅占价格比 | {dxj_stats['spread_pct']:.3f}% | {ewj_stats['spread_pct']:.3f}% |",
        f"| 零波幅分钟占比 | {dxj_stats['zero_range_pct']:.1f}% | {ewj_stats['zero_range_pct']:.1f}% |",
        f"| 日均成交量 | {dxj_stats['avg_daily_volume']:,.0f} | {ewj_stats['avg_daily_volume']:,.0f} |",
        f"| 日均成交额 | ${dxj_stats['avg_daily_dollar_volume'] / 1_000_000:.1f}M | ${ewj_stats['avg_daily_dollar_volume'] / 1_000_000:.1f}M |",
        f"| 日内波动率中位数 | {dxj_stats['intraday_vol_med']:.2f}% | {ewj_stats['intraday_vol_med']:.2f}% |",
        f"| 20 日年化波动率均值 | {dxj_stats['vol20_avg']:.1f}% | {ewj_stats['vol20_avg']:.1f}% |",
        f"| 最大单日跌幅 | {dxj_stats['max_down']:+.2f}% | {ewj_stats['max_down']:+.2f}% |",
        "",
        "## 二、收益联动与相对表现",
        "",
        f"- DXJ 与 EWJ 日收益相关系数: {merged['DXJ'].corr(merged['EWJ']):.3f}",
        f"- DXJ 相对 EWJ 的累计超额收益: {(relative.iloc[-1] - 1) * 100:+.1f}%",
        "",
        "## 三、大跌后修复对比",
        "",
        "| 标的 | 单日跌幅 <= -2% 事件数 | 5 日内恢复次数 | 5 日内恢复比例 |",
        "| ---- | -------------------- | -------------- | -------------- |",
        f"| DXJ | {dxj_drops} | {dxj_recovered} | {dxj_recovered / dxj_drops * 100:.1f}% |",
        f"| EWJ | {ewj_drops} | {ewj_recovered} | {ewj_recovered / ewj_drops * 100:.1f}% |",
        "",
        "## 四、第一轮规律扫描对比",
        "",
        "| 类别 | DXJ 最优组合 | DXJ 总收益 | EWJ 最优组合 | EWJ 总收益 |",
        "| ---- | ------------ | ---------- | ------------ | ---------- |",
        f"| IBS | {dxj_ibs['entry']} / {dxj_ibs['exit']} / {int(dxj_ibs['hold'])}d | {dxj_ibs['total']:+.1f}% | "
        f"{ewj_ibs['entry']} / {ewj_ibs['exit']} / {int(ewj_ibs['hold'])}d | {ewj_ibs['total']:+.1f}% |",
        f"| Gap | {dxj_gap['entry']} / {dxj_gap['exit']} / {int(dxj_gap['hold'])}d | {dxj_gap['total']:+.1f}% | "
        f"{ewj_gap['entry']} / {ewj_gap['exit']} / {int(ewj_gap['hold'])}d | {ewj_gap['total']:+.1f}% |",
        "",
        "## 五、第一轮观察",
        "",
    ]

    lines.extend([f"- {line}" for line in observation_lines])
    lines.extend(
        [
            "",
            "下一步建议：",
            "- 把 DXJ 与 EWJ 的大跌样本按同一天事件对齐，拆出“汇率冲击”和“日本 beta 冲击”",
            "- 对同一套 IBS 参数做样本同步对比，确认 DXJ 的强势是否主要来自对冲结构",
            "- 若 DXJ 与 EWJ 在相同事件中的修复强弱稳定不同，再考虑设计相对价值或过滤器",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    dxj_minute, dxj_daily = load_daily("dxj_minute_data.csv")
    ewj_minute, ewj_daily = load_daily("ewj_minute_data.csv")
    report = build_report(dxj_minute, dxj_daily, ewj_minute, ewj_daily)
    DOC_FILE.write_text(report, encoding="utf-8")

    print(f"Wrote comparison report to {DOC_FILE}")
    print(f"DXJ rows: {len(dxj_daily)} | EWJ rows: {len(ewj_daily)}")


if __name__ == "__main__":
    main()
