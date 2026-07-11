# factormine-plugin · 本地 alpha 因子迭代挖掘流水线

> 一个 **Claude Code 插件**，把"挖因子 + 评估 + 入库 / 沉淀教训"封装成可分发的流水线。

## 它解决什么

挖 alpha 因子最痛的不是"算"，是**少踩坑 + 不忘教训 + 不替用户拍板 + 不重复造已知轮子**。本插件提供：

1. **单轮流水线**：一次命令挖一个因子，按 `propose → design → implement → evaluate → review → archive` 走完。
2. **AI 完全自由设计 + 可行性审查**：因子表达式**不强制白名单**——AI 可基于任何金融直觉 / 文献 / 跨域灵感自由构造。但每个候选必须通过 **F-1 ~ F-9 可行性自查**（数据可得 / 无未来函数 / 计算可行 / 样本充足 / 数值稳定 / 解释清晰 / 与已入库不雷同 / 失败教训回避 / **非已知因子撞库**），机器 + 主会话双重审查，**不可行直接驳回重提**。
3. **强制创新性（撞库自检 F-9）**：禁止复刻 alpha101、Alphalens 内置、国内经典、学术异象、LLM 训练数据中常见的因子。proposer 必声明 ≥3 个最接近的已知因子 + **关键差异** + 创新点。
4. **失败库完整读取 + 沉淀**：每轮 reject 自动写入 `library/lessons/failure_lessons.md`；下轮 propose **强制完整读取**（不是摘要，逐条 ID 引用）以避免重蹈覆辙。
5. **人工审查回路**：机器只评估指标门槛（IC / ICIR / 多空 / OOS / 衰减 / 稳健性），**最终入因子库必须人工 accept**——机器不替你拍板。
6. **可分发**：作为 Claude Code 插件安装后，任何用户都能在自己数据上跑。

## 安装

```bash
# 第一步：注册插件源（marketplace 名 = factormine，源自 .claude-plugin/marketplace.json）
/plugin marketplace add https://github.com/harrycjs/factormine-plugin

# 第二步：安装（语法：<plugin>@<marketplace>）
/plugin install factormine-plugin@factormine

# 首次使用：交互式配置数据路径 / 股票池 / 年份区间 / 默认方向 / 迭代轮数
/mine setup

# 起一轮挖因子
/mine new 行情价量类
/mine new 财务质量类
/mine new 让我自己描述: "过去 20 天换手率上升 + 跌幅大于 5% 的反转因子"

# 断点续跑
/mine continue f003

# 看现状
/mine status

# 人工审查
/mine accept f003
/mine reject f003 "IC 在 2018 单边下跌市失效"
```

## 方法论

本插件遵循的方法论固化在 `templates/methodology.md`，参考来源包括：

- 101 Formulaic Alphas（WorldQuant）
- Alphalens（Quantopian 因子评估开源库）
- gplearn 遗传编程自动挖因子
- AlphaGen / MASTER / IGSG 等深度学习 / RL 生成因子论文
- Alpha-GPT / QuantAgent 等 LLM 辅助因子挖掘
- WorldQuant Brain / AlphaWorks 平台公开文档

评估指标门槛在 `templates/eval_standards.json`；失败因子库的字段定义在 `templates/failure_lessons_schema.md`。

## 与 ghquant_plugin-main 的关系

本插件的设计模式（状态机 + 多 agent + 门禁 + 沉淀 + 编排与生产分离）大量借鉴 `ghquant_plugin-main`，但**跑道**不同：

| 维度 | ghquant_plugin-main | factormine-plugin |
|------|---------------------|-------------------|
| 输入 | 一份研报 PDF | 用户的因子方向 / 灵感 |
| 产出 | 复现策略代码 + 对齐报告 | 单个因子 + 评估 + 入库决定 |
| 节奏 | 一份一跑到底 | 一次一个因子，n 轮迭代 |
| 终态 | 机器判定复现达标 | **人工 accept/reject** |
| 沉淀 | 假设登记簿 | **失败因子库 + 教训笔记** |

## 环境

- Python 3.10+，建议通过 [uv](https://docs.astral.sh/uv/) 管理依赖。
- 本地 parquet 数据根目录（默认 `~/local_data`）。
- 数据可用性以 `templates/data_catalog.md` 为唯一判定依据。

## 变更记录

- 0.4.0（2026-07-11）：**新增迭代轮数 + 自动开下一轮**——`/mine setup` 第五题询问每方向自动迭代上限（0/3/5/10 + 自由输入 0~100）；`accept` / `reject` 后主会话跑 `state.py next-iteration <id>`：未用完自动开新轮（沿用方向、附上一轮失败 ID 触发微调），用完停下汇报。
- 0.3.0（2026-07-11）：**强制创新性 + 失败库完整读取**——新增 F-9 已知因子撞库闸门（≥3 个最接近的已知因子 + 关键差异 + 创新点，禁复刻 alpha101/Alphalens/国内经典/学术异象/LLM 常见）；失败教训读取从「摘要前 200 字」升级为「完整读取 + 逐条 ID 引用」。机器 G-PR-4 升级 / 新增 G-PR-8。
- 0.2.0（2026-07-11）：**移除白名单强制约束**——因子表达式完全自由设计，新增 F-1 ~ F-8 可行性自查闸门（机器 G-PR-7 + 人工可驳回）。
- 0.1.0（2026-07-11）：插件骨架初版——目录、SKILL、4 agent、方法论模板、tools 脚本框架。