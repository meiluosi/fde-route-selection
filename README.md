# fde-route-selection · v0.1.1

FDE 系列的技术路线与模型选型 Skill：在业务问题已定义之后，先过滤合规与部署等硬约束，再选适配路线，最后用客户样本比选模型的质量、成本与延迟。上游是 fde-ramp（行业入门与机会发现）和 fde-problem-framing（业务问题定义）；本 Skill 不需要安装它们，也不修改它们的仓库。

系列：[fde-ramp](https://github.com/meiluosi/fde-ramp)（行业入门与机会发现）→ [fde-problem-framing](https://github.com/meiluosi/fde-problem-framing)（业务问题定义）→ 本 Skill（技术路线与模型选型）。

## 安装与使用

将整个 `fde-route-selection` 文件夹放入宿主的 skills 目录，保留目录名与 SKILL.md。Codex 常用 `${CODEX_HOME:-$HOME/.codex}/skills/`。也可不安装，直接让助手读取本目录 SKILL.md。

```sh
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R -n fde-route-selection "${CODEX_HOME:-$HOME/.codex}/skills/"
```

如宿主未重新发现技能，开启新会话。以根路径安装后检查 references/、templates/ 等子目录是否齐全。尚未在任何宿主做实机测试。

可直接说：
- “客户问我们用哪个模型，帮我先看有哪些硬约束没问。”
- “读取定义卡，判断这个场景该走提示词、检索还是微调。”
- “这是供应商的选型方案，帮我审查。”
- “按这些参数算一下按调用计费和私有化的成本差别。”

## 工程内容
- SKILL.md：入口与四种模式路由。
- references/：模式、硬约束、路线、**速查表（cheatsheet.md）**、模型比选、成本延迟、证据、衔接、判断流程、带日期的市场快照模板。
- references/model-evidence/：社区模型实测记录的索引，目前为空。
- templates/：决策卡、约束清单、比选方案、成本表、审查报告、模型实测记录模板。
- CONTRIBUTING.md：怎样提交模型实测记录或修订速查表。
- examples/finance-extraction：教学假设示例，不是客户事实。
- scripts/cost_model.py：单位经济的条件算术，不含真实价格，不验证输入真伪。
- tests/：脚本与包结构测试，加人工回归用的行为用例。
- DEVELOPMENT.md：来源与方法修订；ROADMAP.md：推进计划。

## 速查表与社区实测
[速查表](references/cheatsheet.md)把常见场景对应到推荐起点、升级信号和硬约束变体，并按档位（小型/中型开放权重、托管 API 中档/旗舰）给出任务的起点档位；不写具体型号，带日期注记。

具体模型在具体任务上的效果不写进 README，也不做排行榜：欢迎把你的实测按 [CONTRIBUTING.md](CONTRIBUTING.md) 提交到 [model-evidence](references/model-evidence/index.md)。这些记录只用于缩小候选池，不替代客户样本上的实测。

## 运行验证
Python 3.9+，仅用标准库。
```sh
python3 -m unittest discover -s tests -v
python3 scripts/cost_model.py --in-tokens 3000 --out-tokens 500 --in-price 2 --out-price 8 \
  --orders-per-day 2000 --days 250 --volume-multipliers 1,3,10
```
命令里的价格与单量是占位数字。单元测试和静态检查不能证明模型必然遵守流程，更不能证明某个选型方案有效；行为用例见 tests/behavioral-cases.md，须在目标宿主重跑。

## 范围
不负责：行业入门、业务问题定义、评测执行、系统实施、法律合规结论。模型清单与价格不入库，只用带日期的快照模板记录。

## 许可
MIT，见 [LICENSE](LICENSE)。
