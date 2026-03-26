# FXY 作为条件分层变量的交互研究

> 生成时间: 2026-03-25 14:41:36
> FXY Regime: `FXY >= 0.80%` 为 Yen Strength, `FXY <= -0.80%` 为 Yen Weakness
> Event Type 独立于 FXY 方向，避免把汇率直接塞回事件分类。

## 一、使用的基础信号参数

| 标的 | IBS 参数 | Gap 参数 |
| ---- | -------- | -------- |
| DXJ | IBS<=0.30 / IBS>=0.90 / 5d | Gap<=-1.0% / Hold 5d |
| EWJ | IBS<=0.25 / IBS>=0.60 / 2d | Gap<=-1.5% / Hold 5d |

## 二、策略 x FXY Regime

| 标的 | 策略 | FXY Regime | 笔数 | 胜率 | 总收益 | 均收益 | 最大亏损 | 平均持有 |
| ---- | ---- | ---------- | ---- | ---- | ------ | ------ | -------- | -------- |
| EWJ | IBS | Neutral | 73 | 66% | +37.2% | +0.51% | -2.35% | 1.5d |
| DXJ | IBS | Neutral | 46 | 70% | +26.0% | +0.57% | -5.06% | 3.9d |
| DXJ | Gap | Neutral | 32 | 62% | +22.9% | +0.72% | -7.97% | 6.0d |
| DXJ | IBS | Yen Strength | 10 | 70% | +22.2% | +2.22% | -3.03% | 3.6d |
| EWJ | Gap | Yen Weakness | 3 | 100% | +17.1% | +5.69% | +2.73% | 6.0d |
| EWJ | IBS | Yen Weakness | 11 | 73% | +14.2% | +1.29% | -0.50% | 1.5d |
| DXJ | Gap | Yen Weakness | 1 | 100% | +10.3% | +10.32% | +10.32% | 6.0d |
| EWJ | IBS | Yen Strength | 10 | 80% | +8.6% | +0.86% | -6.25% | 1.5d |
| DXJ | IBS | Yen Weakness | 2 | 50% | +6.4% | +3.22% | -0.31% | 4.0d |
| EWJ | Gap | Neutral | 15 | 67% | +5.7% | +0.38% | -4.22% | 6.0d |
| EWJ | IBS | Unknown | 1 | 100% | +1.0% | +1.02% | +1.02% | 2.0d |
| EWJ | Gap | Yen Strength | 5 | 80% | -6.6% | -1.32% | -11.25% | 6.0d |
| DXJ | Gap | Yen Strength | 8 | 50% | -9.0% | -1.13% | -14.28% | 6.0d |

## 三、策略 x Event Type

| 标的 | 策略 | Event Type | 笔数 | 胜率 | 总收益 | 均收益 | 最大亏损 | 平均持有 |
| ---- | ---- | ---------- | ---- | ---- | ------ | ------ | -------- | -------- |
| DXJ | IBS | Cross-Hedge Divergence | 15 | 80% | +39.5% | +2.63% | -0.89% | 4.1d |
| DXJ | Gap | Non-event | 14 | 79% | +29.6% | +2.11% | -1.31% | 6.0d |
| EWJ | IBS | Cross-Hedge Divergence | 22 | 77% | +26.7% | +1.21% | -6.25% | 1.6d |
| EWJ | IBS | Non-event | 55 | 58% | +14.1% | +0.26% | -2.35% | 1.5d |
| EWJ | Gap | Non-event | 2 | 100% | +12.8% | +6.40% | +1.62% | 6.0d |
| EWJ | IBS | Shared Down Shock | 9 | 100% | +12.5% | +1.39% | +0.51% | 1.3d |
| DXJ | Gap | Cross-Hedge Divergence | 7 | 71% | +9.7% | +1.39% | -2.73% | 6.0d |
| DXJ | IBS | Non-event | 36 | 64% | +8.6% | +0.24% | -5.06% | 4.0d |
| DXJ | IBS | Shared Down Shock | 4 | 100% | +6.3% | +1.58% | +0.25% | 2.0d |
| EWJ | Gap | Cross-Hedge Divergence | 6 | 83% | +5.5% | +0.92% | -0.21% | 6.0d |
| EWJ | IBS | DXJ-only Stress | 4 | 100% | +5.3% | +1.31% | +0.30% | 1.2d |
| DXJ | Gap | DXJ-only Stress | 3 | 33% | +3.1% | +1.04% | -1.70% | 6.0d |
| EWJ | IBS | Shared Up Shock | 1 | 100% | +1.8% | +1.76% | +1.76% | 2.0d |
| EWJ | Gap | DXJ-only Stress | 1 | 100% | +1.2% | +1.24% | +1.24% | 6.0d |
| DXJ | Gap | EWJ-only Stress | 1 | 100% | +1.2% | +1.23% | +1.23% | 6.0d |
| DXJ | IBS | DXJ-only Stress | 2 | 50% | +0.7% | +0.34% | -1.00% | 2.0d |
| EWJ | IBS | EWJ-only Stress | 4 | 50% | +0.7% | +0.17% | -0.50% | 1.5d |
| DXJ | IBS | EWJ-only Stress | 1 | 0% | -0.4% | -0.38% | -0.38% | 5.0d |
| EWJ | Gap | EWJ-only Stress | 3 | 33% | -1.5% | -0.50% | -2.23% | 6.0d |
| EWJ | Gap | Shared Down Shock | 11 | 73% | -1.8% | -0.17% | -11.25% | 6.0d |
| DXJ | Gap | Shared Down Shock | 16 | 44% | -19.5% | -1.22% | -14.28% | 6.0d |

## 四、策略 x Event Type x FXY Regime

只保留样本数 >= 3 的格子，避免极小样本误导。

| 标的 | 策略 | 联合条件 | 笔数 | 胜率 | 总收益 | 均收益 | 最大亏损 | 平均持有 |
| ---- | ---- | -------- | ---- | ---- | ------ | ------ | -------- | -------- |
| DXJ | IBS | Cross-Hedge Divergence | Yen Strength | 5 | 100% | +22.6% | +4.51% | +0.84% | 4.0d |
| DXJ | Gap | Non-event | Neutral | 12 | 75% | +19.1% | +1.59% | -1.31% | 6.0d |
| EWJ | IBS | Cross-Hedge Divergence | Yen Weakness | 8 | 88% | +13.7% | +1.71% | -0.18% | 1.4d |
| EWJ | IBS | Non-event | Neutral | 54 | 57% | +13.1% | +0.24% | -2.35% | 1.4d |
| EWJ | IBS | Shared Down Shock | Neutral | 8 | 100% | +11.3% | +1.41% | +0.51% | 1.4d |
| EWJ | IBS | Cross-Hedge Divergence | Neutral | 9 | 78% | +10.7% | +1.18% | -0.14% | 1.7d |
| DXJ | IBS | Cross-Hedge Divergence | Neutral | 8 | 75% | +10.5% | +1.31% | -0.89% | 4.2d |
| DXJ | IBS | Non-event | Neutral | 34 | 65% | +9.2% | +0.27% | -5.06% | 4.0d |
| EWJ | Gap | Shared Down Shock | Neutral | 9 | 78% | +6.7% | +0.74% | -4.22% | 6.0d |
| DXJ | IBS | Shared Down Shock | Neutral | 4 | 100% | +6.3% | +1.58% | +0.25% | 2.0d |
| DXJ | Gap | Cross-Hedge Divergence | Yen Strength | 4 | 50% | +5.9% | +1.47% | -2.73% | 6.0d |
| EWJ | IBS | DXJ-only Stress | Yen Strength | 3 | 100% | +4.1% | +1.37% | +0.30% | 1.3d |
| DXJ | Gap | Cross-Hedge Divergence | Neutral | 3 | 100% | +3.9% | +1.29% | +0.36% | 6.0d |
| EWJ | IBS | Cross-Hedge Divergence | Yen Strength | 5 | 60% | +2.4% | +0.47% | -6.25% | 1.8d |
| EWJ | Gap | Cross-Hedge Divergence | Neutral | 3 | 67% | +1.7% | +0.55% | -0.21% | 6.0d |
| DXJ | Gap | Shared Down Shock | Neutral | 14 | 43% | -6.1% | -0.44% | -7.97% | 6.0d |

## 五、第一轮观察

- DXJ 的 IBS 在日元走强环境下平均单笔收益高于中性环境，说明 FXY 更适合做条件分层，而不是简单屏蔽。
- EWJ 的 Gap 信号在“Cross-Hedge Divergence”类事件里仍为正收益，但强度低于 IBS，说明缺口修复不是其核心模式。
- DXJ 的 Gap 在“Cross-Hedge Divergence | Yen Strength”格子里有独立表现，后续值得做成专门子样本。
- EWJ 的 IBS 在“Shared Down Shock | Neutral”格子里值得重点观察，这更接近纯日本 beta 冲击后的修复。

下一步建议：
- 在 `IBS x FXY Regime` 里，只保留样本数足够的格子，做滚动样本外稳定性检查
- 把 `Cross-Hedge Divergence` 和 `Shared Down Shock` 两类事件抽出来，做单独分钟级回测
- 如果联合格子稳定，再考虑把 FXY 变量写进信号引擎，而不是继续停留在研究文档里
