"""
DXJ/EWJ 的 IBS 信号在不同日元 regime 下的表现对比。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf


DOC_FILE = Path("docs/09_dxj_ewj_ibs_fx_regime.md")
FX_MOVE = 0.008


def load_daily(csv_file: str) -> pd.DataFrame:
    df = pd.read_csv(csv_file, parse_dates=["timestamp"])
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
    daily["ibs"] = (daily["Close"] - daily["Low"]) / (daily["High"] - daily["Low"])
    daily["ma200"] = daily["Close"].rolling(200).mean()
    return daily


def load_fxy_returns() -> pd.Series:
    df = yf.download("FXY", period="2y", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    close = df["Close"].copy()
    close.index = close.index.tz_localize(None)
    ret = close.pct_change().dropna()
    ret.name = "FXY"
    return ret


def summarize(trades: list[dict]) -> dict | None:
    if not trades:
        return None
    tdf = pd.DataFrame(trades)
    return {
        "n": len(tdf),
        "wr": float((tdf["ret"] > 0).mean() * 100),
        "total": float(tdf["ret"].sum() * 100),
        "avg": float(tdf["ret"].mean() * 100),
        "worst": float(tdf["ret"].min() * 100),
        "avg_hold": float(tdf["days"].mean()),
    }


def run_ibs(daily: pd.DataFrame, ibs_buy: float, ibs_sell: float, max_hold: int, entry_mask: pd.Series | None = None) -> dict | None:
    trades: list[dict] = []
    position: dict | None = None

    if entry_mask is None:
        entry_mask = pd.Series(True, index=daily.index)

    for idx, row in daily.iterrows():
        if position is not None:
            position["days"] += 1
            if row["ibs"] >= ibs_sell or position["days"] >= max_hold:
                trades.append(
                    {
                        "ret": row["Close"] / position["buy_price"] - 1,
                        "days": position["days"],
                    }
                )
                position = None
                continue

        if position is None:
            if not bool(entry_mask.get(idx, False)):
                continue
            if pd.notna(row["ibs"]) and row["ibs"] <= ibs_buy:
                position = {"buy_price": row["Close"], "days": 0}

    return summarize(trades)


def find_best_ibs(daily: pd.DataFrame) -> dict:
    results = []
    for ibs_buy in [0.10, 0.15, 0.20, 0.25, 0.30]:
        for ibs_sell in [0.60, 0.70, 0.80, 0.90]:
            if ibs_sell <= ibs_buy:
                continue
            for max_hold in [1, 2, 3, 5, 10]:
                summary = run_ibs(daily, ibs_buy, ibs_sell, max_hold)
                if summary is None:
                    continue
                summary.update(
                    {
                        "ibs_buy": ibs_buy,
                        "ibs_sell": ibs_sell,
                        "max_hold": max_hold,
                    }
                )
                results.append(summary)
    return pd.DataFrame(results).sort_values(["total", "avg", "wr"], ascending=False).iloc[0].to_dict()


def evaluate_regimes(asset_name: str, daily: pd.DataFrame, fxy: pd.Series, params: dict) -> list[dict]:
    aligned = daily.join(fxy, how="left")
    aligned["regime"] = "Neutral"
    aligned.loc[aligned["FXY"] >= FX_MOVE, "regime"] = "Yen Strength"
    aligned.loc[aligned["FXY"] <= -FX_MOVE, "regime"] = "Yen Weakness"

    masks = {
        "All": pd.Series(True, index=aligned.index),
        "Yen Strength": aligned["regime"] == "Yen Strength",
        "Yen Weakness": aligned["regime"] == "Yen Weakness",
        "Neutral": aligned["regime"] == "Neutral",
        "Exclude Yen Strength": aligned["regime"] != "Yen Strength",
        "Exclude Yen Weakness": aligned["regime"] != "Yen Weakness",
    }

    rows = []
    for label, mask in masks.items():
        summary = run_ibs(aligned, params["ibs_buy"], params["ibs_sell"], int(params["max_hold"]), entry_mask=mask)
        if summary is None:
            continue
        rows.append(
            {
                "asset": asset_name,
                "regime": label,
                "entry": f"IBS<={params['ibs_buy']:.2f}",
                "exit": f"IBS>={params['ibs_sell']:.2f}",
                "hold": int(params["max_hold"]),
                **summary,
            }
        )
    return rows


def build_report(dxj_best: dict, ewj_best: dict, rows: pd.DataFrame) -> str:
    observations = []

    dxj_all = rows[(rows["asset"] == "DXJ") & (rows["regime"] == "All")].iloc[0]
    dxj_ex_strength = rows[(rows["asset"] == "DXJ") & (rows["regime"] == "Exclude Yen Strength")].iloc[0]
    ewj_all = rows[(rows["asset"] == "EWJ") & (rows["regime"] == "All")].iloc[0]
    ewj_ex_weak = rows[(rows["asset"] == "EWJ") & (rows["regime"] == "Exclude Yen Weakness")].iloc[0]

    if dxj_ex_strength["avg"] > dxj_all["avg"]:
        observations.append("对 DXJ 来说，去掉“日元走强”入场日后，单笔收益更好，说明强日元环境可能削弱其 IBS 信号质量。")
    else:
        observations.append("对 DXJ 来说，排除“日元走强”并没有明显改善 IBS，说明其主要 alpha 仍可能来自日内价格结构本身。")

    if ewj_ex_weak["avg"] > ewj_all["avg"]:
        observations.append("对 EWJ 来说，去掉“日元走弱”入场日后，IBS 表现更稳，说明弱日元环境可能拖累未对冲版本的修复质量。")
    else:
        observations.append("对 EWJ 来说，排除“日元走弱”并没有带来明显收益改善。")

    dxj_strength = rows[(rows["asset"] == "DXJ") & (rows["regime"] == "Yen Strength")].iloc[0]
    dxj_weak = rows[(rows["asset"] == "DXJ") & (rows["regime"] == "Yen Weakness")].iloc[0]
    ewj_strength = rows[(rows["asset"] == "EWJ") & (rows["regime"] == "Yen Strength")].iloc[0]
    ewj_weak = rows[(rows["asset"] == "EWJ") & (rows["regime"] == "Yen Weakness")].iloc[0]

    if dxj_weak["avg"] > dxj_strength["avg"] and ewj_strength["avg"] > ewj_weak["avg"]:
        observations.append("分 regime 看，DXJ 在日元走弱环境更受益，EWJ 在日元走强环境更受益，和产品结构方向一致。")
    else:
        if dxj_strength["avg"] > dxj_weak["avg"]:
            observations.append("DXJ 的 IBS 在“日元走强”样本里的平均单笔收益反而更高，说明其 alpha 不能简单解释为‘弱日元受益’。")
        if ewj_weak["avg"] > ewj_strength["avg"]:
            observations.append("EWJ 的 IBS 在“日元走弱”样本里平均单笔收益更高，说明日元方向并不是决定其 IBS 优劣的单一变量。")

    lines = [
        "# DXJ/EWJ 的 IBS 与日元 Regime",
        "",
        f"> 生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> Regime 定义: `FXY >= {FX_MOVE*100:.2f}%` 为 Yen Strength, `FXY <= -{FX_MOVE*100:.2f}%` 为 Yen Weakness",
        "",
        "## 一、各标的全样本最佳 IBS 参数",
        "",
        "| 标的 | 最优入场 | 最优出场 | 最大持有 | 总收益 | 均收益 | 胜率 |",
        "| ---- | -------- | -------- | -------- | ------ | ------ | ---- |",
        f"| DXJ | IBS<={dxj_best['ibs_buy']:.2f} | IBS>={dxj_best['ibs_sell']:.2f} | {int(dxj_best['max_hold'])}d | {dxj_best['total']:+.1f}% | {dxj_best['avg']:+.2f}% | {dxj_best['wr']:.0f}% |",
        f"| EWJ | IBS<={ewj_best['ibs_buy']:.2f} | IBS>={ewj_best['ibs_sell']:.2f} | {int(ewj_best['max_hold'])}d | {ewj_best['total']:+.1f}% | {ewj_best['avg']:+.2f}% | {ewj_best['wr']:.0f}% |",
        "",
        "## 二、在不同日元 regime 下的表现",
        "",
        "| 标的 | Regime | 笔数 | 胜率 | 总收益 | 均收益 | 最大亏损 | 平均持有 |",
        "| ---- | ------ | ---- | ---- | ------ | ------ | -------- | -------- |",
    ]

    for _, row in rows.iterrows():
        lines.append(
            f"| {row['asset']} | {row['regime']} | {int(row['n'])} | {row['wr']:.0f}% | "
            f"{row['total']:+.1f}% | {row['avg']:+.2f}% | {row['worst']:+.2f}% | {row['avg_hold']:.1f}d |"
        )

    lines.extend(
        [
            "",
            "## 三、第一轮观察",
            "",
        ]
    )
    lines.extend([f"- {line}" for line in observations])
    lines.extend(
        [
            "",
            "下一步建议：",
            "- 对 DXJ 和 EWJ 的 IBS 信号加入简单的 FXY 过滤器，直接测试是否提升样本外稳健性",
            "- 把“Yen Strength / Weakness”与事件分类文档联动，确认这些 regime 是否集中在少数极端时期",
            "- 若 regime 影响稳定，再研究 DXJ/EWJ 的相对价值切换，而不是只做单标的绝对收益",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    dxj_daily = load_daily("dxj_minute_data.csv")
    ewj_daily = load_daily("ewj_minute_data.csv")
    fxy = load_fxy_returns()

    dxj_best = find_best_ibs(dxj_daily)
    ewj_best = find_best_ibs(ewj_daily)

    rows = evaluate_regimes("DXJ", dxj_daily, fxy, dxj_best)
    rows.extend(evaluate_regimes("EWJ", ewj_daily, fxy, ewj_best))
    result_df = pd.DataFrame(rows)

    report = build_report(dxj_best, ewj_best, result_df)
    DOC_FILE.write_text(report, encoding="utf-8")

    print(f"Wrote FX-regime IBS report to {DOC_FILE}")
    print(f"Rows: {len(result_df)}")


if __name__ == "__main__":
    main()
