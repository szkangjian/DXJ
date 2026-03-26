# 条件格子稳定性检查

> 生成时间: 2026-03-25 14:45:21
> 只分析样本数 >= 6 的联合条件格子。
> 说明: 这里测试的是“条件格子”的时间稳定性，不是参数搜索的严格样本外优化。

## 一、稳定性总表

| 标记 | 标的 | 策略 | 联合条件 | 总笔数 | 全样本均收益 | 前半段笔数 | 前半段均收益 | 后半段笔数 | 后半段均收益 | 正收益桶数 | 活跃桶数 |
| ---- | ---- | ---- | -------- | ------ | ------------ | ---------- | ------------ | ---------- | ------------ | ---------- | -------- |
| Early Decay | DXJ | IBS | Non-event | Neutral | 34 | +0.27% | 15 | +0.71% | 19 | -0.08% | 3 | 4 |
| Early Decay | EWJ | Gap | Shared Down Shock | Neutral | 9 | +0.74% | 5 | +1.34% | 4 | -0.01% | 3 | 4 |
| Late Improve | DXJ | Gap | Shared Down Shock | Neutral | 14 | -0.44% | 8 | -0.88% | 6 | +0.15% | 1 | 4 |
| Stable | DXJ | Gap | Non-event | Neutral | 12 | +1.59% | 7 | +1.18% | 5 | +2.16% | 4 | 4 |
| Stable | EWJ | IBS | Cross-Hedge Divergence | Yen Weakness | 8 | +1.71% | 4 | +2.24% | 4 | +1.19% | 4 | 4 |
| Stable | EWJ | IBS | Non-event | Neutral | 54 | +0.24% | 26 | +0.23% | 28 | +0.25% | 4 | 4 |
| Stable | EWJ | IBS | Shared Down Shock | Neutral | 8 | +1.41% | 5 | +1.12% | 3 | +1.91% | 4 | 4 |
| Stable | EWJ | IBS | Cross-Hedge Divergence | Neutral | 9 | +1.18% | 3 | +1.90% | 6 | +0.83% | 4 | 4 |
| Stable | DXJ | IBS | Cross-Hedge Divergence | Neutral | 8 | +1.31% | 3 | +0.46% | 5 | +1.82% | 3 | 4 |

## 二、四个连续时间桶明细

| 标的 | 策略 | 联合条件 | 时间桶 | 笔数 | 胜率 | 均收益 | 总收益 | 最大亏损 |
| ---- | ---- | -------- | ------ | ---- | ---- | ------ | ------ | -------- |
| DXJ | Gap | Non-event | Neutral | B1 | 2 | 100% | +2.91% | +5.8% | +0.65% |
| DXJ | Gap | Non-event | Neutral | B2 | 5 | 60% | +0.49% | +2.5% | -1.31% |
| DXJ | Gap | Non-event | Neutral | B3 | 3 | 67% | +0.60% | +1.8% | -0.83% |
| DXJ | Gap | Non-event | Neutral | B4 | 2 | 100% | +4.51% | +9.0% | +1.40% |
| DXJ | Gap | Shared Down Shock | Neutral | B1 | 6 | 50% | -0.74% | -4.5% | -7.97% |
| DXJ | Gap | Shared Down Shock | Neutral | B2 | 2 | 0% | -1.28% | -2.6% | -2.03% |
| DXJ | Gap | Shared Down Shock | Neutral | B3 | 1 | 100% | +0.96% | +1.0% | +0.96% |
| DXJ | Gap | Shared Down Shock | Neutral | B4 | 5 | 40% | -0.01% | -0.1% | -4.97% |
| DXJ | IBS | Cross-Hedge Divergence | Neutral | B1 | 2 | 0% | -0.54% | -1.1% | -0.89% |
| DXJ | IBS | Cross-Hedge Divergence | Neutral | B2 | 1 | 100% | +2.44% | +2.4% | +2.44% |
| DXJ | IBS | Cross-Hedge Divergence | Neutral | B3 | 3 | 100% | +0.82% | +2.5% | +0.30% |
| DXJ | IBS | Cross-Hedge Divergence | Neutral | B4 | 2 | 100% | +3.32% | +6.6% | +1.61% |
| DXJ | IBS | Non-event | Neutral | B1 | 6 | 67% | +0.73% | +4.4% | -2.29% |
| DXJ | IBS | Non-event | Neutral | B2 | 9 | 67% | +0.70% | +6.3% | -0.60% |
| DXJ | IBS | Non-event | Neutral | B3 | 10 | 80% | +0.54% | +5.4% | -3.83% |
| DXJ | IBS | Non-event | Neutral | B4 | 9 | 44% | -0.76% | -6.9% | -5.06% |
| EWJ | Gap | Shared Down Shock | Neutral | B1 | 4 | 75% | +1.49% | +6.0% | -0.22% |
| EWJ | Gap | Shared Down Shock | Neutral | B2 | 1 | 100% | +0.75% | +0.7% | +0.75% |
| EWJ | Gap | Shared Down Shock | Neutral | B3 | 1 | 100% | +0.39% | +0.4% | +0.39% |
| EWJ | Gap | Shared Down Shock | Neutral | B4 | 3 | 67% | -0.14% | -0.4% | -4.22% |
| EWJ | IBS | Cross-Hedge Divergence | Neutral | B1 | 1 | 100% | +4.33% | +4.3% | +4.33% |
| EWJ | IBS | Cross-Hedge Divergence | Neutral | B2 | 2 | 100% | +0.68% | +1.4% | +0.50% |
| EWJ | IBS | Cross-Hedge Divergence | Neutral | B3 | 3 | 67% | +0.66% | +2.0% | -0.14% |
| EWJ | IBS | Cross-Hedge Divergence | Neutral | B4 | 3 | 67% | +0.99% | +3.0% | -0.08% |
| EWJ | IBS | Cross-Hedge Divergence | Yen Weakness | B1 | 3 | 100% | +2.02% | +6.1% | +1.53% |
| EWJ | IBS | Cross-Hedge Divergence | Yen Weakness | B2 | 1 | 100% | +2.88% | +2.9% | +2.88% |
| EWJ | IBS | Cross-Hedge Divergence | Yen Weakness | B3 | 2 | 100% | +1.18% | +2.4% | +1.01% |
| EWJ | IBS | Cross-Hedge Divergence | Yen Weakness | B4 | 2 | 50% | +1.19% | +2.4% | -0.18% |
| EWJ | IBS | Non-event | Neutral | B1 | 11 | 64% | +0.36% | +4.0% | -1.84% |
| EWJ | IBS | Non-event | Neutral | B2 | 15 | 60% | +0.14% | +2.1% | -1.69% |
| EWJ | IBS | Non-event | Neutral | B3 | 15 | 47% | +0.23% | +3.4% | -2.16% |
| EWJ | IBS | Non-event | Neutral | B4 | 13 | 62% | +0.29% | +3.7% | -2.35% |
| EWJ | IBS | Shared Down Shock | Neutral | B1 | 3 | 100% | +1.43% | +4.3% | +0.55% |
| EWJ | IBS | Shared Down Shock | Neutral | B2 | 2 | 100% | +0.64% | +1.3% | +0.60% |
| EWJ | IBS | Shared Down Shock | Neutral | B3 | 1 | 100% | +0.51% | +0.5% | +0.51% |
| EWJ | IBS | Shared Down Shock | Neutral | B4 | 2 | 100% | +2.60% | +5.2% | +1.27% |

## 三、第一轮观察

- 当前最稳定的联合格子是 `DXJ | Gap | Non-event | Neutral`，前后半段都保持正平均收益。
- `DXJ | IBS | Non-event | Neutral` 属于前期有效、后期衰减，不能直接写进执行逻辑。
- `DXJ | Gap | Shared Down Shock | Neutral` 更像后期才变得有效，后续应检查是否与近期 regime 切换相关。

下一步建议：
- 只对 `Stable` 标签的格子继续做分钟级执行回测
- 对 `Early Decay` 标签的格子检查是否由单一时期或单一事件贡献
- 若后续要做信号引擎，应优先把“稳定格子”写成条件分层，而不是把所有格子一视同仁
