# 日本 ETF 条件信号候选清单

> 生成时间: 2026-03-25 15:17:38
> 口径: 同时参考稳定性、执行敏感性、半样本样本外验证。
> 这里的结论只决定推进优先级，不重新发明参数；当前参数仍以各资产最新统一参数研究页为准。

## 一、候选总表

| 状态 | 标的 | 策略 | 条件格子 | 当前统一参数 | 执行标签 | 样本外结论 | 样本外笔数 | 样本外总收益 | 样本外均收益 |
| ---- | ---- | ---- | -------- | ------------ | -------- | ---------- | ---------- | ------------ | ------------ |
| Core | DXJ | IBS | Cross-Hedge Divergence | Neutral | IBS<=0.30 / IBS>=0.90 / 5d | Robust | Keep Unified | 6 | +11.8% | +1.96% |
| Core | EWJ | IBS | Cross-Hedge Divergence | Neutral | IBS<=0.25 / IBS>=0.60 / 2d | Robust | Keep Unified | 6 | +4.9% | +0.82% |
| Secondary | EWJ | IBS | Shared Down Shock | Neutral | IBS<=0.25 / IBS>=0.60 / 2d | Robust | Keep Unified | 4 | +13.3% | +3.32% |
| Watchlist | DXJ | Gap | Non-event | Neutral | Gap<=-1.0% / Hold 5d | Robust | Keep Unified | 2 | +0.6% | +0.30% |

## DXJ | IBS | Cross-Hedge Divergence | Neutral

- 当前状态: `Core`
- 当前统一参数: `IBS<=0.30 / IBS>=0.90 / 5d`
- 执行敏感性: `Robust`
- 半样本验证: `Keep Unified`
- 样本外表现: 6 笔, 总收益 +11.8%, 均收益 +1.96%
- 推进建议: 优先进入统一参数信号原型。

## EWJ | IBS | Cross-Hedge Divergence | Neutral

- 当前状态: `Core`
- 当前统一参数: `IBS<=0.25 / IBS>=0.60 / 2d`
- 执行敏感性: `Robust`
- 半样本验证: `Keep Unified`
- 样本外表现: 6 笔, 总收益 +4.9%, 均收益 +0.82%
- 推进建议: 优先进入统一参数信号原型。

## EWJ | IBS | Shared Down Shock | Neutral

- 当前状态: `Secondary`
- 当前统一参数: `IBS<=0.25 / IBS>=0.60 / 2d`
- 执行敏感性: `Robust`
- 半样本验证: `Keep Unified`
- 样本外表现: 4 笔, 总收益 +13.3%, 均收益 +3.32%
- 推进建议: 保留为第二梯队，先做轻量信号实现。

## DXJ | Gap | Non-event | Neutral

- 当前状态: `Watchlist`
- 当前统一参数: `Gap<=-1.0% / Hold 5d`
- 执行敏感性: `Robust`
- 半样本验证: `Keep Unified`
- 样本外表现: 2 笔, 总收益 +0.6%, 均收益 +0.30%
- 推进建议: 继续观察，不要单独提高实盘优先级。

## 二、第一轮观察

- `DXJ | IBS | Cross-Hedge Divergence | Neutral` 是当前优先级最高的统一参数候选。
- `EWJ | IBS | Shared Down Shock | Neutral` 样本外为正，但样本仍偏薄，放在第二梯队。
- `DXJ | Gap | Non-event | Neutral` 目前更适合作为观察名单，而不是核心信号。

下一步建议：
- 先对 `Core` 候选写统一参数信号脚本
- `Secondary` 先做轻量监控，不急着实盘化
- `Watchlist` 保留在研究层，等样本继续扩展后再复查
