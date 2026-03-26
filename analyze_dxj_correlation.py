"""
DXJ 驱动映射脚本。

从 Yahoo Finance 拉取候选代理变量，计算相关性、滚动相关、beta，
并将结果写入 docs/02_dxj_event_drivers.md 的初始版本。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf


TARGET_TICKER = "DXJ"
DOC_FILE = Path("docs/02_dxj_event_drivers.md")

TICKERS = {
    "DXJ": "研究标的",
    "EWJ": "日本股票未对冲代理",
    "EFA": "发达市场 beta 代理",
    "SPY": "美国大盘风险偏好",
    "FXY": "日元代理",
    "TLT": "美国长久期利率代理",
}


def fetch_close_series(ticker: str, period: str = "2y") -> pd.Series:
    df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    close = df["Close"].copy()
    close.index = close.index.tz_localize(None)
    close.name = ticker
    return close


def build_report(prices: pd.DataFrame) -> str:
    returns = prices.pct_change().dropna()
    corr = returns.corr()
    candidates = [ticker for ticker in prices.columns if ticker != TARGET_TICKER]

    detailed_rows = []
    observation_lines = []

    for ticker in candidates:
        pair = returns[[TARGET_TICKER, ticker]].dropna()
        corr_val = pair[TARGET_TICKER].corr(pair[ticker])
        rolling = pair[TARGET_TICKER].rolling(60).corr(pair[ticker]).dropna()
        cov = pair.cov()
        beta = cov.loc[TARGET_TICKER, ticker] / pair[ticker].var()

        detailed_rows.append(
            {
                "ticker": ticker,
                "desc": TICKERS[ticker],
                "corr": corr_val,
                "beta": beta,
                "roll_latest": rolling.iloc[-1] if not rolling.empty else float("nan"),
                "roll_max": rolling.max() if not rolling.empty else float("nan"),
                "roll_min": rolling.min() if not rolling.empty else float("nan"),
            }
        )

    strongest = sorted(detailed_rows, key=lambda row: abs(row["corr"]), reverse=True)
    if strongest:
        observation_lines.append(
            f"静态相关性最高的候选因子是 `{strongest[0]['ticker']}`，需要优先作为主驱动假设验证。"
        )

    japan_proxy = next((row for row in detailed_rows if row["ticker"] == "EWJ"), None)
    us_proxy = next((row for row in detailed_rows if row["ticker"] == "SPY"), None)
    yen_proxy = next((row for row in detailed_rows if row["ticker"] == "FXY"), None)

    if japan_proxy and us_proxy:
        if abs(japan_proxy["corr"]) > abs(us_proxy["corr"]):
            observation_lines.append(f"{TARGET_TICKER} 与日本股市代理的联动强于与美国大盘的联动，应先从日本 beta 和日本主题驱动解释。")
        else:
            observation_lines.append(f"{TARGET_TICKER} 与美国大盘代理的联动不弱，说明全球风险偏好不能被忽略。")

    if yen_proxy:
        if abs(yen_proxy["corr"]) >= 0.3:
            observation_lines.append(f"日元代理与 {TARGET_TICKER} 存在可见联动，后续应单独测试汇率环境对策略表现的影响。")
        else:
            observation_lines.append("日元代理的线性相关并不算强，汇率影响可能更多通过 regime 或事件窗口体现。")

    target_big_drop = returns[returns[TARGET_TICKER] <= -0.02]
    big_drop_lines = []
    if not target_big_drop.empty:
        for ticker in candidates:
            avg_ret = target_big_drop[ticker].mean() * 100
            big_drop_lines.append(f"| {ticker} | {avg_ret:+.2f}% |")
    else:
        big_drop_lines.append("| 样本不足 | N/A |")

    lines = [
        f"# {TARGET_TICKER} 驱动映射与事件归因（第一版）",
        "",
        f"> 生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ">",
        "> 本文档当前只覆盖驱动映射部分，后续可继续追加异动事件归因。",
        "",
        "## 一、候选驱动篮子",
        "",
        "以下是第一轮候选代理，不代表最终结论：",
        "",
    ]

    for ticker, desc in TICKERS.items():
        lines.append(f"- `{ticker}`: {desc}")

    lines.extend(
        [
            "",
            "## 二、样本说明",
            "",
            f"- 样本区间: {prices.index.min().date()} -> {prices.index.max().date()}",
            f"- 重叠交易日: {len(prices)}",
            "",
            "## 三、日收益率相关矩阵",
            "",
            "| 标的 | " + " | ".join(corr.columns) + " |",
            "| ---- | " + " | ".join(["----"] * len(corr.columns)) + " |",
        ]
    )

    for ticker in corr.index:
        values = " | ".join(f"{corr.loc[ticker, col]:.3f}" for col in corr.columns)
        lines.append(f"| {ticker} | {values} |")

    lines.extend(
        [
            "",
            f"## 四、{TARGET_TICKER} 与各候选因子的关系",
            "",
            "| 因子 | 含义 | 相关系数 | Beta | 60 日滚动相关最新值 | 60 日滚动相关区间 |",
            "| ---- | ---- | -------- | ---- | ------------------- | ---------------- |",
        ]
    )

    for row in detailed_rows:
        lines.append(
            f"| {row['ticker']} | {row['desc']} | {row['corr']:.3f} | {row['beta']:.3f} | "
            f"{row['roll_latest']:.3f} | {row['roll_min']:.3f} -> {row['roll_max']:.3f} |"
        )

    lines.extend(
        [
            "",
            f"## 五、{TARGET_TICKER} 单日跌幅超过 2% 时，其他因子的平均表现",
            "",
            "| 因子 | 平均当日收益 |",
            "| ---- | ------------ |",
            *big_drop_lines,
            "",
            "## 六、第一轮观察",
            "",
        ]
    )
    lines.extend([f"- {line}" for line in observation_lines])
    lines.extend(
        [
            "",
            "这些结论仍是驱动映射层，不是交易结论。",
            f"下一步应把 {TARGET_TICKER} 的异动日逐一分类，分清哪些是日本 beta、哪些是汇率窗口、哪些是全球风险事件。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    series = {ticker: fetch_close_series(ticker) for ticker in TICKERS}
    prices = pd.DataFrame(series).dropna()
    report = build_report(prices)
    DOC_FILE.write_text(report, encoding="utf-8")

    print(f"Wrote driver report to {DOC_FILE}")
    print(f"Range: {prices.index.min()} -> {prices.index.max()}")
    print(f"Rows: {len(prices)}")


if __name__ == "__main__":
    main()
