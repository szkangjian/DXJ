"""
DXJ/EWJ 事件对齐研究。

目标：
1. 将 DXJ 与 EWJ 的大波动日按同一天对齐
2. 区分日本 beta 冲击与日元冲击
3. 观察不同事件类型下，DXJ 与 EWJ 哪个更强、后续修复谁更快
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf


DOC_FILE = Path("docs/08_dxj_ewj_event_alignment.md")
DXJ_CSV = Path("dxj_minute_data.csv")
EWJ_CSV = Path("ewj_minute_data.csv")

FX_MOVE = 0.008
SPREAD_MOVE = 0.0075
MARKET_MOVE = 0.012


def load_local_daily(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    if df["timestamp"].dt.hour.max() > 21:
        df["timestamp"] = (
            df["timestamp"]
            .dt.tz_localize("UTC")
            .dt.tz_convert("US/Eastern")
            .dt.tz_localize(None)
        )

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
        )
        .dropna()
    )
    daily["ret"] = daily["Close"].pct_change()
    return daily


def fetch_external_returns() -> pd.DataFrame:
    series = {}
    for ticker in ["FXY", "EFA", "SPY"]:
        df = yf.download(ticker, period="2y", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        close = df["Close"].copy()
        close.index = close.index.tz_localize(None)
        series[ticker] = close

    prices = pd.DataFrame(series).dropna()
    return prices.pct_change().dropna()


def forward_return(daily: pd.DataFrame, date: pd.Timestamp, days: int) -> float | None:
    if date not in daily.index:
        return None
    loc = daily.index.get_loc(date)
    if isinstance(loc, slice):
        return None
    if loc + days >= len(daily):
        return None
    buy = daily.iloc[loc]["Close"]
    sell = daily.iloc[loc + days]["Close"]
    return sell / buy - 1


def classify_event(row: pd.Series) -> str:
    dxj = row["DXJ"]
    ewj = row["EWJ"]
    fxy = row["FXY"]
    spread = row["spread"]

    if fxy >= FX_MOVE and spread <= -SPREAD_MOVE:
        return "Yen Strength"
    if fxy <= -FX_MOVE and spread >= SPREAD_MOVE:
        return "Yen Weakness"
    if abs(spread) <= 0.006 and abs(dxj) >= MARKET_MOVE and abs(ewj) >= MARKET_MOVE and dxj * ewj > 0:
        return "Japan Beta"
    if dxj <= -0.015 and ewj > -0.01:
        return "DXJ-only Stress"
    if ewj <= -0.015 and dxj > -0.01:
        return "EWJ-only Stress"
    if abs(spread) >= SPREAD_MOVE:
        return "Mixed Divergence"
    return "Other"


def build_event_frame(dxj_daily: pd.DataFrame, ewj_daily: pd.DataFrame, external: pd.DataFrame) -> pd.DataFrame:
    merged = pd.DataFrame(
        {
            "DXJ": dxj_daily["ret"],
            "EWJ": ewj_daily["ret"],
        }
    ).join(external, how="inner")

    merged["spread"] = merged["DXJ"] - merged["EWJ"]
    merged["abs_spread"] = merged["spread"].abs()

    event_mask = (
        (merged["abs_spread"] >= SPREAD_MOVE)
        | (merged["DXJ"].abs() >= MARKET_MOVE)
        | (merged["EWJ"].abs() >= MARKET_MOVE)
    )
    events = merged[event_mask].copy()
    events["category"] = events.apply(classify_event, axis=1)

    for horizon in [1, 3, 5]:
        events[f"dxj_fwd_{horizon}d"] = [forward_return(dxj_daily, date, horizon) for date in events.index]
        events[f"ewj_fwd_{horizon}d"] = [forward_return(ewj_daily, date, horizon) for date in events.index]
        events[f"rel_fwd_{horizon}d"] = events[f"dxj_fwd_{horizon}d"] - events[f"ewj_fwd_{horizon}d"]

    return events.sort_index()


def format_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value * 100:+.2f}%"


def build_report(events: pd.DataFrame, merged: pd.DataFrame) -> str:
    spread_fxy_corr = merged["spread"].corr(merged["FXY"])
    spread_spy_corr = merged["spread"].corr(merged["SPY"])

    category_summary = (
        events.groupby("category")
        .agg(
            n=("category", "size"),
            dxj_same=("DXJ", "mean"),
            ewj_same=("EWJ", "mean"),
            fxy_same=("FXY", "mean"),
            rel_same=("spread", "mean"),
            dxj_fwd_5d=("dxj_fwd_5d", "mean"),
            ewj_fwd_5d=("ewj_fwd_5d", "mean"),
            rel_fwd_5d=("rel_fwd_5d", "mean"),
        )
        .sort_values("n", ascending=False)
    )

    top_divergence = events.sort_values("abs_spread", ascending=False).head(12)
    common_drop = events[(events["DXJ"] <= -0.015) & (events["EWJ"] <= -0.015)].copy()

    observations = []
    if spread_fxy_corr <= -0.4:
        observations.append("DXJ-EWJ 的相对收益与日元代理呈明显负相关，说明两者差异很大一部分确实来自汇率暴露。")
    else:
        observations.append("DXJ-EWJ 的相对收益与日元代理相关性不算极端，说明除了汇率，对冲结构之外仍有其他影响。")

    if "Yen Weakness" in category_summary.index and "Yen Strength" in category_summary.index:
        weak = category_summary.loc["Yen Weakness", "rel_same"]
        strong = category_summary.loc["Yen Strength", "rel_same"]
        if weak > 0 and strong < 0:
            observations.append("按事件分类看，日元走弱时 DXJ 同日明显跑赢，日元走强时 EWJ 反而更强，这和产品结构一致。")

    if "Japan Beta" in category_summary.index:
        beta_row = category_summary.loc["Japan Beta"]
        if abs(beta_row["rel_same"]) < 0.003:
            observations.append("纯日本 beta 冲击日里，DXJ 和 EWJ 的同日表现差距通常不大，说明这类日子不适合做两者相对判断。")

    if not common_drop.empty:
        if common_drop["rel_fwd_5d"].mean() > 0:
            observations.append("在两者同跌的风险事件中，DXJ 的 5 日后续表现略优于 EWJ，值得进一步验证是否与汇率对冲带来的修复优势有关。")
        else:
            observations.append("在两者同跌的风险事件中，EWJ 的 5 日后续表现不弱于 DXJ，说明对冲版本并没有天然修复优势。")

    lines = [
        "# DXJ/EWJ 事件对齐研究",
        "",
        f"> 生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 样本事件数: {len(events)}",
        f"> 事件定义: `|DXJ-EWJ| >= {SPREAD_MOVE*100:.2f}%` 或任一标的日收益绝对值 >= {MARKET_MOVE*100:.2f}%",
        "",
        "## 一、相对收益与外部变量",
        "",
        f"- `DXJ-EWJ` 与 `FXY` 日收益相关: {spread_fxy_corr:.3f}",
        f"- `DXJ-EWJ` 与 `SPY` 日收益相关: {spread_spy_corr:.3f}",
        "",
        "## 二、事件分类汇总",
        "",
        "| 类别 | 样本数 | 当日 DXJ | 当日 EWJ | 当日 FXY | 当日相对收益(DXJ-EWJ) | 5 日后 DXJ | 5 日后 EWJ | 5 日后相对收益 |",
        "| ---- | ------ | -------- | -------- | -------- | --------------------- | ---------- | ---------- | -------------- |",
    ]

    for category, row in category_summary.iterrows():
        lines.append(
            f"| {category} | {int(row['n'])} | {row['dxj_same']*100:+.2f}% | {row['ewj_same']*100:+.2f}% | "
            f"{row['fxy_same']*100:+.2f}% | {row['rel_same']*100:+.2f}% | "
            f"{row['dxj_fwd_5d']*100:+.2f}% | {row['ewj_fwd_5d']*100:+.2f}% | {row['rel_fwd_5d']*100:+.2f}% |"
        )

    lines.extend(
        [
            "",
            "## 三、相对表现分化最大的 12 天",
            "",
            "| 日期 | 类别 | DXJ | EWJ | DXJ-EWJ | FXY | EFA | SPY | 3 日后相对收益 | 5 日后相对收益 |",
            "| ---- | ---- | --- | --- | ------- | --- | --- | --- | -------------- | -------------- |",
        ]
    )

    for date, row in top_divergence.iterrows():
        lines.append(
            f"| {date.date()} | {row['category']} | {row['DXJ']*100:+.2f}% | {row['EWJ']*100:+.2f}% | {row['spread']*100:+.2f}% | "
            f"{row['FXY']*100:+.2f}% | {row['EFA']*100:+.2f}% | {row['SPY']*100:+.2f}% | "
            f"{format_pct(row['rel_fwd_3d'])} | {format_pct(row['rel_fwd_5d'])} |"
        )

    lines.extend(
        [
            "",
            "## 四、两者同跌的风险事件",
            "",
            "| 日期 | 类别 | DXJ | EWJ | FXY | 1 日后 DXJ | 1 日后 EWJ | 5 日后 DXJ | 5 日后 EWJ |",
            "| ---- | ---- | --- | --- | --- | ---------- | ---------- | ---------- | ---------- |",
        ]
    )

    if common_drop.empty:
        lines.append("| 无样本 | - | - | - | - | - | - | - | - |")
    else:
        for date, row in common_drop.sort_values("DXJ").head(12).iterrows():
            lines.append(
                f"| {date.date()} | {row['category']} | {row['DXJ']*100:+.2f}% | {row['EWJ']*100:+.2f}% | {row['FXY']*100:+.2f}% | "
                f"{format_pct(row['dxj_fwd_1d'])} | {format_pct(row['ewj_fwd_1d'])} | "
                f"{format_pct(row['dxj_fwd_5d'])} | {format_pct(row['ewj_fwd_5d'])} |"
            )

    lines.extend(
        [
            "",
            "## 五、第一轮观察",
            "",
        ]
    )
    lines.extend([f"- {line}" for line in observations])
    lines.extend(
        [
            "",
            "下一步建议：",
            "- 对 `Yen Weakness` 和 `Yen Strength` 两类样本分别跑 IBS，确认汇率 regime 是否改变信号质量",
            "- 把 `Japan Beta` 事件单独拉出来，检查 DXJ 与 EWJ 是否存在系统性的恢复速度差",
            "- 若相对收益与 FXY 的关系稳定，可考虑把日元变量纳入 DXJ/EWJ 的过滤器或相对价值研究",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    dxj_daily = load_local_daily(DXJ_CSV)
    ewj_daily = load_local_daily(EWJ_CSV)
    external = fetch_external_returns()

    merged = pd.DataFrame(
        {
            "DXJ": dxj_daily["ret"],
            "EWJ": ewj_daily["ret"],
        }
    ).join(external, how="inner")
    merged["spread"] = merged["DXJ"] - merged["EWJ"]

    events = build_event_frame(dxj_daily, ewj_daily, external)
    report = build_report(events, merged.dropna())
    DOC_FILE.write_text(report, encoding="utf-8")

    print(f"Wrote aligned-event report to {DOC_FILE}")
    print(f"Event rows: {len(events)}")


if __name__ == "__main__":
    main()
