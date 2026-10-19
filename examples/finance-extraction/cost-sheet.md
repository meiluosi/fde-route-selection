# 成本表（教学假设）

币种与计量单位：元；单价为**假设值**，不是真实报价；真实项目须来自带日期的记录（见 references/market-snapshot.md）。

| 参数 | 值 | 来源 | 状态 |
|---|---|---|---|
| 每次调用输入 / 输出 token | 3000 / 500 | 假设的典型材料 | 假设 |
| 输入 / 输出单价（每百万 token） | 2 / 8（仅用于对比结构） | 假设 | 假设 |
| 每单调用次数、重试率 | 1、5% | 假设 | 假设 |
| 检索等其他每单成本 | 0.01 | 假设 | 假设 |
| 人工复核占比 / 单次成本 | 30% / 0.5 | 假设 | 假设 |
| 日均单量、运行天数 | 2000、250（客户工作日） | 假设的 ramp 数字 | 假设 |
| 峰值小时占比 | 20% | 假设 | 假设 |
| 每单人工成本、预期节省比例、可兑现比例 | 6、40%、70%（节省比例未扣复核，故复核成本在支出侧计入） | 假设的 ramp 数字 | 假设 |
| 私有化固定年成本 | 600000（算力折旧与运维） | 假设 | 假设 |

## 结构 A：按调用计费（仅在 C2 通过、处理脱敏文本时成立）
```sh
python3 scripts/cost_model.py --in-tokens 3000 --out-tokens 500 --in-price 2 --out-price 8 \
  --orders-per-day 2000 --days 250 --retry-rate 0.05 --other-per-order 0.01 \
  --review-share 0.3 --review-cost 0.5 --human-cost 6 --saving-share 0.4 \
  --realizable-share 0.7 --peak-hour-share 0.2 --volume-multipliers 1,3,10
```
每单有效成本 0.1705；年总成本 85250；每单价值上限 1.68；在上限内；峰值约 7 次调用/分钟。成本随量近似线性增长，量级敏感性主要看单价变化。

## 结构 B：私有化（单价设为 0，成本在固定年成本里）
```sh
python3 scripts/cost_model.py --in-tokens 3000 --out-tokens 500 --in-price 0 --out-price 0 \
  --orders-per-day 2000 --days 250 --retry-rate 0.05 --other-per-order 0.01 \
  --review-share 0.3 --review-cost 0.5 --fixed-annual 600000 --human-cost 6 \
  --saving-share 0.4 --realizable-share 0.7 --volume-multipliers 1,3,10
```
每单有效成本 1.36（年总成本 680000）；净价值约 0.32/单；盈亏平衡约 1579 单/天。量级×3 时每单降到 0.56，×10 降到 0.28；反过来，量级若降到约 1579 单/天以下，私有化在价值上限内就不再成立。

## 读法
- 两种结构的成本形态不同：A 随量线性，B 靠摊销，对量的变化敏感，且受利用率约束。
- 结论取决于 C2–C5 的答复，本表只说明“若客户答复是……则成本形态是……”，不能反过来替客户选择部署。
- 假设的复核占比与单价对结果影响很大，真实项目要先测复核占比和 token 量。
