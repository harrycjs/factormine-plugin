# Factormine-Plugin（本地 alpha 因子迭代挖掘流水线）

> **形态定位**：本仓库是一个 **Claude Code 插件**（`factormine-plugin`），既可在仓库内直接使用（形态 A，维护者模式），也可作为插件安装在任意用户目录使用（形态 B）。插件入口命令为 `/mine`，配套 4 个子 agent、common 回测库、templates 方法论参考与失败库 schema。

所有回复、思考、文档、提示词一律使用**中文**。

## 一、核心范式（区别于研报复现）

| 维度 | 研报复现（ghquant_plugin） | **本插件（factormine-plugin）** |
|------|---------------------------|--------------------------------|
| 跑道 | 给定一份研报 PDF，逐项对齐复现 | **无固定输入**，由用户每轮指定方向（行情/财务/混合/具体灵感），由 Claude 提出候选 |
| 产物 | 与原文逐项对照的策略代码 | **单个 alpha 因子** + 评估报告 + 入库决定 |
| 节奏 | 一份研报一跑到底 | **一次命令挖一个因子**，n 轮迭代 |
| 终态 | 复现达标（pass/partial） | **人工审查**（accept 入库 / reject 入失败库 / iterate 重做） |
| 沉淀 | 假设登记簿 | **失败因子库 + 教训笔记**（每轮强制读 → 避免重蹈覆辙） |

## 二、单轮状态机

```
propose → design → implement → evaluate → review → archive
   ↑                                                  ↓
   └──────────── iterate（用户拒/迭代修正） ←─────────┘
```

每轮状态由 `tools/state.py` 唯一写入口维护，门禁由 `tools/check_gates.py` 重算判定。

## 三、硬规则（任何 stage 不得违背）

1. **门禁即代码**：任何 stage 结束必须运行 `check_gates`，FAIL 禁止进下一 stage、禁止口头声称通过。
2. **编排与生产分离**：主会话只派发、审门禁、记账；**严禁亲自撰写因子公式 / 代码 / 评估结论 / 沉淀记录**。
3. **产物合同逐一点收**：agent 返回后逐一 `ls` 验证输出文件，缺一即该步失败。
4. **状态先行**：stage 开始/结束先写 state，杜绝"跑完再补账"。
5. **失败库完整读取**：进入 `propose` 阶段前主会话**必须 Read 完整文件**：`library/lessons/failure_lessons.md` 全文 + `library/failures/*.md` 全部档案，**严禁只摘要前 200 字**。proposer 必须在 proposal 中**逐条引用每一条失败条目 ID**（如 `f003`/`f007`/`f012`）。G-PR-4 机器逐条核对。
6. **达标判定唯一出口**：pass/reject/iterate 只能由 `check_gates` 重算得出；agent 自述结论仅供参考。
7. **自由设计 + 可行性审查**：因子表达式**完全自由**，AI 可基于任何金融直觉 / 文献 / 跨域灵感构造；**不强制白名单**。但**每个候选必须通过可行性闸门 F-1 ~ F-9**（详见 templates/factor_formulas.md），任一项未勾 → 主会话**驳回**重提。
8. **必须是非已知因子（创新性闸门 F-9）**：因子**不能是任何已知因子**——禁止复刻 alpha101、Alphalens 内置、国内经典（月度反转 / 12-1 动量 / Amihud / EP / BP / ROE 等）、学术异象（Fama-French / Carhart / Sloan 等）、LLM 训练数据中常见的因子。proposer 必须在 proposal 列出 ≥3 个最接近的已知因子 + **关键差异** + 创新点。G-PR-8 机器核对关键词命中 + 关键差异声明。**不接受「换窗口」「加权重」「中性化叠加」类纯形式变形**。

## 四、目录骨架

```
.
├── CLAUDE.md                     # 本文件
├── README.md                     # 用户文档
├── .claude-plugin/plugin.json    # 插件清单
├── skills/mine/
│   ├── SKILL.md                  # /mine 主编排
│   └── stages/                   # 单 stage 执行卡（propose.md / design.md / implement.md / ...）
├── agents/                       # 4 个子 agent 定义
│   ├── factor-proposer.md        # 提出候选因子
│   ├── factor-coder.md           # 实现因子计算 + 回测
│   ├── factor-evaluator.md       # 全量评估 + 样本外
│   └── factor-archivist.md       # 入库（approved / rejected） + 更新失败教训
├── common/                       # 公共回测库（首版：data_loader / factor_utils / factor_eval）
├── templates/
│   ├── data_catalog.md           # 本地数据目录（与 ghquant_plugin 兼容）
│   ├── methodology.md            # 因子挖掘方法论参考（固化）
│   ├── factor_formulas.md        # 因子表达式白名单（落地可快速试错的范式）
│   ├── eval_standards.json       # 评估指标门槛（IC / ICIR / 多空 / 换手 / 衰减 / OOS）
│   ├── failure_lessons_schema.md # 失败因子库的字段定义
│   └── audit/                    # 审计 / 假设登记簿模板
├── tools/
│   ├── state.py                  # state.json 唯一写入口
│   ├── check_gates.py            # 门禁机器判定
│   ├── setup_workspace.py        # 首次配置（数据路径 / 股票池 / 年份）
│   └── factor_archiver.py        # 沉淀辅助（生成失败库 / 教训笔记）
├── library/                      # 沉淀的因子库与失败库
│   ├── approved/                 # 通过人工审查的因子（md + parquet）
│   ├── rejected/                 # 评估未达标但有保留价值的因子
│   ├── failures/                 # 失败案例档案（每次 reject 沉淀一份）
│   └── lessons/
│       └── failure_lessons.md    # 失败教训笔记（每轮 propose 前必读）
├── workspace/                    # 每次挖因子的工作区（state.json + spec/code/eval/report）
└── pyproject.toml                # uv 依赖
```

## 五、`/mine` 子命令路由

| 子命令 | 作用 |
|--------|------|
| `/mine setup` | 首次使用：交互式收集数据路径、股票池、年份区间、默认因子方向、**迭代轮数**（自由输入 0~100，0=不自动迭代，默认 3）；落地 `.mine.json` |
| `/mine new <方向>` | 起一轮新的因子挖掘（如 `/mine new 行情动量类`），从 `propose` 开始 |
| `/mine continue <id>` | 断点续跑（按 state.json 当前 stage 推进） |
| `/mine status [id]` | 列全部轮次摘要（id / 方向 / 状态 / 当前 stage） |
| `/mine accept <id>` | 人工审查通过：归档到 `library/approved/` + 更新 `lessons` |
| `/mine reject <id> "<reason>"` | 人工拒收：归档到 `library/rejected/` + `library/failures/` + 更新 `lessons` |
| `/mine report <id>` | 出本轮的最终评估报告（汇总 evaluate 阶段产物） |

轮次 id 形式：`fNNN_<slug>`（三位顺序号 + 语义短名，如 `f001_turnover_reversal_20d`）。

## 六、数据约定（与 ghquant_plugin 兼容）

- 财务数据一律按 `info_publ_date`（披露日）做时点对齐，**禁止用 `end_date`**（防未来函数）。
- 信号严格 **T 日算出、T+1 执行**；滚动窗口训练 / 统计只用历史数据。
- 数据可用性以 `templates/data_catalog.md` 为唯一判定依据。

## 七、输出约定（与 ghquant_plugin 兼容）

- 评估产物：`workspace/{id}/results/` 下五张图（ic_series / ic_distribution / group_cumulative / group_returns_bar / net_value）+ 一份 `factor_eval.xlsx`。
- 配色：蓝 `#1f77b4`（多头/正/高因子组）、红 `#d62728`（空头/负/低因子组）、矩阵类 `RdBu_r`，300 DPI，中文不乱码。
- Excel：第一行表头加粗、冻结首行、自动列宽。

## 八、与 ghquant_plugin-main 的设计继承

本插件大量借鉴 `D:\ghquant_plugin-main` 的设计模式：状态机 + 多 agent + 门禁 + 沉淀 + 编排与生产分离。差异在于**跑道**（单因子迭代而非研报复现）和**用户回路**（人工审查而非机器达标）。详见 `templates/methodology.md` 与 `skills/mine/SKILL.md`。