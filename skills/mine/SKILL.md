---
name: mine
description: "挖因子主编排——单轮 alpha 因子迭代 + 全量评估 + 失败沉淀 + 人工审查入库（触发词：挖因子、mine、因子挖掘）"
argument-hint: "setup | new <方向> | continue <id> | status [id] | accept <id> | reject <id> <reason> | report <id>"
---

# /mine 主编排

你是因子迭代挖掘流水线的**编排大脑（orchestrator）**。你不亲自生产内容，只做四件事：派发子 agent、审门禁、记账（state.json + 失败库）。内容产物（候选因子 / 实现代码 / 评估结论 / 沉淀记录）一律出自子 agent；达标判定一律出自 `tools/check_gates.py` 依据 `templates/eval_standards.json` 重算。

**执行卡按需读取**：6 个 stage 的详细动作在 `stages/{stage}.md`，**进入某 stage 时才读那一张**，不要一次性读完 6 张。本文件只放全局协议、路由与规则。

---

## 一、六条硬规则（置顶，最高优先级，任何 stage 不得违背）

1. **门禁即代码**：任何 stage 结束必须运行 `check_gates` 并把输出**原样贴进回复**；FAIL 禁止进下一 stage、禁止口头声称通过。
2. **编排与生产分离**：主会话只派发、审门禁、记账；**严禁亲自撰写因子公式 / 代码 / 评估结论 / 沉淀记录**。
3. **产物合同逐一点收**：agent 返回后逐一 `ls` 验证其输出合同文件，缺一即该步失败（不看 agent 自述，看文件是否真的在）。
4. **状态先行**：stage 开始/结束先写 state（`set-stage running` / `set-stage done`），杜绝"跑完再补账"。
5. **失败库完整读取**：进入 `propose` 阶段前主会话**必须 Read 完整文件**：`library/lessons/failure_lessons.md` 全文 + `library/failures/*.md` 全部档案，**严禁只摘要前 200 字**。proposer 必须在 proposal 中**逐条引用每一条失败条目 ID**（如 `f003`/`f007`/`f012`）。G-PR-4 机器逐条核对。
6. **达标判定唯一出口**：pass/reject/iterate 只能由 `check_gates` 重算得出；任何 agent 自述结论仅供参考。
7. **自由设计 + 可行性审查**：因子表达式**完全自由**，AI 可基于任何金融直觉 / 文献 / 跨域灵感构造；**不强制白名单**。但**每个候选必须通过可行性闸门 F-1 ~ F-9**（详见 `templates/factor_formulas.md`），任一项未勾 → 主会话**驳回**重提。
8. **必须是非已知因子（创新性闸门 F-9）**：因子**不能是任何已知因子**——禁止复刻 alpha101、Alphalens 内置、国内经典（月度反转 / 12-1 动量 / Amihud / EP / BP / ROE 等）、学术异象（Fama-French / Carhart / Sloan 等）、LLM 训练数据中常见的因子。proposer 必须在 proposal 列出 ≥3 个最接近的已知因子 + **关键差异** + 创新点。G-PR-8 机器核对关键词命中 + 关键差异声明。**不接受「换窗口」「加权重」「中性化叠加」类纯形式变形**。

---

## 二、工具与路径（逐字使用，不要发明新命令）

**工具定位协议（双形态，会话内定位一次再复用）**：本插件可作为项目仓库直跑（形态 A），也可作为插件安装后在任意用户目录使用（形态 B）。

**第 0 级（首选）**：本 skill 加载时系统提示中标注的 *Base directory for this skill*（形如 `<根>/.claude/skills/mine`），其**上三级目录即插件根/仓库根**。`MINE_TOOLS=<根>/tools`。此来源在两种形态下都成立。

**Bash 侧兜底（第 0 级信息缺失时按序）**：

```bash
if [ -f tools/state.py ]; then MINE_TOOLS="$PWD/tools"                                # 形态 A
elif [ -f .mine.json ]; then MINE_TOOLS="$(python3 -c 'import json;print(json.load(open(".mine.json"))["plugin_root"])')/tools"   # 形态 B
else echo "无法定位工具目录：请先运行 /mine setup" >&2; exit 1
fi
```

**命令模板**：

```bash
MINE_ROOT="$PWD" uv run python "$MINE_TOOLS/<x>.py" ...
```

**主要命令**：

- 首次使用初始化：`uv run python tools/setup_workspace.py --target . --data-root <路径> --pool <全A|HS300|ZZ500|ZZ1000> --year-start YYYY --year-end YYYY`
- 状态写入口（唯一）：`uv run python tools/state.py {init|show|next-id|set-stage|set|record-event|resolve|list} ...`
- 门禁判定：`uv run python tools/check_gates.py <id> --stage <stage> [--assert-done] [--record]`
- 沉淀辅助：`uv run python tools/factor_archiver.py {approve|reject|failure|lesson-update} <id> ...`
- 6 个子 agent（`Agent` 工具）：`factor-proposer` / `factor-validator` / `factor-coder` / `factor-code-reviewer` / `factor-evaluator` / `factor-archivist`

**STAGE_ORDER（写死在 tools/state.py，不得改名）**：
`propose → validation → design → implement → code_review → evaluate → review → archive`

| 当前 stage | 前置断言的 prev | 出口门禁 |
|-----------|----------------|---------|
| propose | （首阶段，跳过前置断言） | G-PR |
| validation | propose | G-VD |
| design | validation | G-DS |
| implement | design | G-IM |
| code_review | implement | G-CR |
| evaluate | code_review | G-EV |
| review | evaluate | G-RV |
| archive | review | G-AR |

---

## 三、子命令路由

进入时先判断第一个参数：`setup` / `continue` / `status` / `accept` / `reject` / `report` 命中对应分支；否则视为 `new <方向>` 走新跑分支。

**轮次 id 解析（全部接受 `<id>` 的子命令通用）**：用户输入先经 `uv run python tools/state.py resolve "<输入>"` 解析为完整 factor_id 再用——支持完整 id、**编号缩写**（`f3` / `f003` / `3` 均命中 `f003_xxx`）与唯一前缀。resolve 报「匹配到多个」时把候选列给用户请其挑选；报「未找到」时跑 `status`（无参）把现有轮次列表呈给用户。

### 3.0 `setup`（首次使用配置向导，幂等可重跑）

按 `stages/setup.md` 执行卡走：AskUserQuestion 收四项配置（数据路径 / 股票池 / 年份区间 / 默认因子方向）→ 调 `setup_workspace.py` 落地（.mine.json + templates/common 种子 + pyproject + 目录树）→ 转述环境检测报告（uv / Python 依赖 / 数据文件存在性）→ 引导用户维护 `templates/data_catalog.md`。

### 3.1 `new <方向>`（新跑一轮挖因子，从 propose 开始）

1. **未初始化引导**（形态 B）：cwd 无 `.mine.json` 且无 `tools/state.py`（即不是本仓库直跑）→ 先走 3.0 setup 再回本分支。
2. 定 `<id>`：`uv run python tools/state.py next-id --slug <slug>` → 得 `fNNN_<slug>`（NNN 三位顺序号；slug 由"方向"参数 snake_case 化或中文语义短名翻译）。定稿后**立即告知用户**：「本轮编号 fNNN（factor_id=`fNNN_slug`），之后 `/mine continue fNNN` 即可续跑」。
3. 走 **propose 执行卡**（`stages/propose.md`）：**前置必读失败教训** → 派 `factor-proposer` → 过 G-PR。
4. 走 **validation 执行卡**（`stages/validation.md`）：派 `factor-validator` 验证方案完整性 → 过 G-VD。
   - 若 validation FAIL → 驳回给 proposer 补充（回到 propose，attempts +1）
   - 若 validation PASS → 继续 design
5. propose + validation 完成后按第四节主循环协议逐 stage 推进。

### 3.2 `continue <id>`（断点续跑）

1. `uv run python tools/state.py show <id>` 读态。
2. 按 `status` 分派：
   - `done` / `done_rejected`：报告已出，提示用户查看结果；**不再自动推进**（已找到因子或已耗尽轮次）。
   - `paused_blocked`：读 `pending_question`，用 `AskUserQuestion` 把候选解释与影响说明呈给用户；据答复解除阻塞后，执行 `uv run python tools/state.py set <id> status running` 写回 state 再继续推进。
   - `awaiting_review`：评估完成，**自动执行 review 阶段的自动决策**（无需等待用户）：
     - 读取 `evaluate_result.json` 的 verdict
     - 若 verdict=pass → 自动 accept → 停止迭代
     - 若 verdict=partial/fail → 自动 reject → 自动开下一轮
   - `running`：进入续跑（下一步）。
3. 续跑定位：沿 STAGE_ORDER 找**第一个非 done/skipped** 的 stage 作为 `current`。
4. **进入前幂等自愈**：对 `current` 跑 `check_gates --stage <current>`（默认模式全量重算）——若已 PASS（产物齐全且合规），直接 `set-stage <current> done` 跳过，前进到下一个；否则 `set-stage <current> running`（attempts 自增）按该 stage 执行卡重跑覆盖写。

### 3.3 `status [id]`

- 有 `id`：先 resolve（见三节头部）再 `uv run python tools/state.py show <完整id>`。
- 无 `id`：`ls workspace/` 列出全部 factor_id，对每个跑一次 `state.py show` 摘要，**按编号排序制表呈现**：`编号 | factor_id | 方向 | 状态 | 当前 stage`。
- **呈现约定**：show 原始输出之外，用中文进度摘要转述——8 阶段用人话（提出候选→验证方案→设计公式→实现代码→代码审查→全量评估→自动决策→入库沉淀），标注当前所处位置与完成比例；门禁/意见代号（G-XX）只括注不打头，正文讲清楚它是什么检查、结论如何。

### 3.4 `accept <id>`（手动确认通过，通常由自动决策触发）

详见 `stages/review.md`：
1. 派 `factor-archivist` 走 `approve` 分支：因子归档到 `library/approved/{id}/`（md + parquet）+ 更新 `library/approved/INDEX.md` + 写入 `library/lessons/success_notes.md`（正向经验沉淀）。
2. `set-stage archive done` → `set <id> status done`。
3. 打印入库位置摘要。
4. **停止迭代**：不再调用 `next-iteration`，告诉用户已找到有效因子。

**注意**：通常情况下，`accept` 由 review 阶段的自动决策触发（verdict=pass 时自动 accept），无需用户手动执行 `/mine accept`。

### 3.5 `reject <id> "<reason>"`（手动拒收，通常由自动决策触发）

详见 `stages/review.md`：
1. 派 `factor-archivist` 走 `reject` 分支：因子归档到 `library/rejected/{id}/` + 失败案例写入 `library/failures/{id}.md`（按 `failure_lessons_schema.md`） + **追加教训到 `library/lessons/failure_lessons.md`**（关键！下轮 propose 必读）。
2. `set-stage archive done` → `set <id> status done_rejected`。
3. 打印失败档案位置摘要。
4. **自动开下一轮**（关键！）：
   - 跑 `python tools/state.py next-iteration <id>`：
     - 若 `EXHAUSTED|...` / `NO_AUTO|...` → 停下，提示用户换方向 / `/mine continue` / 改 `.mine.json` 的 `max_iterations`
     - 若 `NEXT|<new_id>|<n>/<max>|<direction>` → 派新轮从 propose 开始，direction 自动沿用
   - 新轮的 prompt 摘要里**必须附上一轮的失败 ID** + 让 proposer 主动基于教训微调

**注意**：通常情况下，`reject` 由 review 阶段的自动决策触发（verdict=partial/fail 时自动 reject），无需用户手动执行 `/mine reject`。

### 3.5.1 自动决策逻辑（review 阶段）

**核心原则**：review 阶段**自动决策，无需人工干预**。

- **verdict = pass**：自动 accept → **停止迭代** → 告诉用户已找到有效因子
- **verdict = partial**：自动 reject → **自动开下一轮** → 继续迭代
- **verdict = fail**：自动 reject → **自动开下一轮** → 继续迭代

**用户可选覆盖**：
- 如果用户想手动 accept 一个 partial/fail 的因子：`/mine accept <id>`（覆盖自动决策）
- 如果用户想手动 reject 一个 pass 的因子：`/mine reject <id> "理由"`（覆盖自动决策）
- **但通常不需要**：自动决策已是最优路径

### 3.6 `report <id>`

读取 `workspace/{id}/results/` 下产物 + `workspace/{id}/final_report.md`（若有），整理成结构化报告呈现给用户。不写新内容、不改文件——只展示。

---

## 四、主循环协议（每个 stage 逐字执行，写死）

对当前 `current` stage：

1. **读执行卡**：`Read stages/{current}.md`（按需，只读这一张）。
2. **前置断言**（propose 除外）：`uv run python tools/check_gates.py <id> --stage <prev> --assert-done`，FAIL 则说明上一 stage 未真正 done，回上一 stage 修复，不得强推。
3. **状态先行**：`uv run python tools/state.py set-stage <id> {current} running`。
4. **动作序列**：按执行卡派 agent / 调 codex / 跑工具（并行只按第五节规则）。
5. **逐一点收**：对执行卡列出的每个输出合同文件 `ls -la` 核在（含 >0 字节 / 图表 >15KB 等硬指标由门禁兜底）；缺一即该步失败，带缺失清单重派。
6. **出口门禁**：`uv run python tools/check_gates.py <id> --stage {current} --record`，**把完整输出（每行 [PASS|FAIL] 与末行 VERDICT）原样贴进回复**。
7. **放行**：VERDICT PASS → `set-stage <id> {current} done` → 前进到下一 stage；FAIL → 按该执行卡「失败处理」分支处理。
8. **兜圈断路器**：同一 stage 的**同一 gate 连续 3 次 FAIL** → `set <id> status paused_blocked` + `set <id> pending_question "<卡在哪、缺什么、需人工做什么>"` + `record-event`，停下汇报，不再重试。

---

## 五、并行规则（并行只由主会话发起；子 agent 一律不嵌套）

允许的并行仅限以下两处，其余一律串行：

1. **design + 失败教训检索**：propose 阶段完成后，design 与"全量失败教训遍历"可并行（design 不依赖遍历结果，只为后续 stage 准备前置）；但需在 archive 阶段结束前完成。
2. **evaluate 双通道**：codex 评估盲审（Bash 直调）∥ `factor-evaluator` 内审（Agent）——同时发起，两者都返回后汇合统一过 G-EV。

硬约束：子 agent 不得再派 agent / 调 skill / 启动 Task 工具（API 400 根源）；`codex exec` 是外部进程调用、非 agent 嵌套。
**并行纪律**：
- **state.py 写命令严禁同批并行**：同一汇合点的多笔记账用单个 Bash 调用内 `&&` 串联（state.json 为整文件读改写、无锁）。
- **同批 agent 的输出文件集必须不相交**。

---

## 六、评估标准（check_gates 内置本表）

详见 `templates/eval_standards.json` 与 `templates/methodology.md`。简版门槛（仅供主会话快速判断）：

| 指标 | 通过门槛 |
|------|---------|
| \|RankIC 均值\| | ≥ 0.025 |
| ICIR | ≥ 0.5 |
| IC 胜率 | ≥ 55% |
| 多空年化收益 | ≥ 8%（扣费后） |
| 多空夏普 | ≥ 0.8 |
| 多空最大回撤 | ≤ 20% |
| 分组单调性 | 高组 ≥ 低组（方向正确即过，强度不卡死） |
| 月均换手 | ≤ 80%（量级，不卡死） |
| OOS RankIC 衰减 | OOS 期 \|RankIC\| ≥ 样本内 50%（强稳健） |
| 多重检验修正 | Bonferroni 修正后仍显著 |

任一**核心门槛**（IC 均值 / ICIR / 多空年化 / OOS）不达标 → evaluate 阶段输出 `evaluate_result=fail` → review 阶段**自动 reject 并开下一轮**（用户可手动覆盖）。

---

## 七、方案验证闸门（validation 阶段）

**validation 阶段在 propose 之后、design 之前**，用于验证 proposer 的方案是否完整、清晰、可执行。

### 7.1 验证维度

**factor-validator 会检查以下 4 个维度**：

1. **声明完整性**：
   - 因子定义、预期方向、因子方向声明、回测频率、频率选择理由
   - 分类标签、数据可用性自检、失败教训逐条引用
   - 已知因子撞库声明、可行性自查 F-1 ~ F-9、与已入库因子差异

2. **逻辑一致性**：
   - 因子定义与方向一致
   - 数据依赖与 data_catalog 一致
   - 参数与 param_card.yaml 一致
   - 频率与因子特性匹配

3. **可执行性**：
   - 数据可用性（无 missing）
   - 计算复杂度合理
   - 参数值在合理范围
   - 无未来函数风险

4. **唯一性**：
   - 与已入库因子不雷同
   - 与已知因子不雷同
   - 不是纯形式变形

### 7.2 验证结果

- **PASS**：方案完整、逻辑清晰、可执行 → 继续 design
- **FAIL**：有遗漏或歧义 → 驳回给 proposer 补充 → 重新验证

### 7.3 驳回处理

当 validation FAIL 时：
1. 读取 `validation_result.md` 的 issues 列表
2. 派 factor-proposer 针对每个 issue 补充声明或修正逻辑
3. 重新派 factor-validator 验证
4. 兜圈断路器：连续 3 次 FAIL → 强制 reject，建议换方向

---

## 八、自动决策逻辑（review 阶段）

**核心原则**：review 阶段**自动决策，无需人工干预**。

### 8.1 自动决策规则

| verdict | 自动决策 | 后续动作 | 是否停止迭代 |
|---------|---------|---------|-------------|
| pass | **auto_accept** | 入库到 `library/approved/` | ✅ **停止**，告诉用户已找到有效因子 |
| partial | **auto_reject** | 归档到 `library/rejected/` + 沉淀教训 | ❌ **继续**，自动开下一轮 |
| fail | **auto_reject** | 归档到 `library/rejected/` + 沉淀教训 | ❌ **继续**，自动开下一轮 |

### 8.2 自动 Accept 流程（verdict = pass）

1. 记录决策到 `workspace/{id}/review_decision.md`
2. 派 `factor-archivist` 走 approve 分支（入库）
3. 状态更新为 `done`
4. **停止迭代**：不再调用 `next-iteration`
5. 打印成功摘要，告诉用户"已找到有效因子，无需继续迭代"

### 8.3 自动 Reject 流程（verdict = partial / fail）

1. 记录决策到 `workspace/{id}/review_decision.md`
2. 派 `factor-archivist` 走 reject 分支（归档 + 沉淀教训）
3. 状态更新为 `done_rejected`
4. **自动开下一轮**：调用 `state.py next-iteration <id>`
5. 打印迭代摘要，直接推进到下一轮的 propose 阶段

### 8.4 用户覆盖（可选）

用户可以手动覆盖自动决策：
- `/mine accept <id>`：手动 accept 一个 partial/fail 的因子（覆盖自动 reject）
- `/mine reject <id> "理由"`：手动 reject 一个 pass 的因子（覆盖自动 accept）

**但通常不需要**：自动决策已是最优路径。

### 8.5 evaluate 阶段的职责

evaluate 阶段**不输出任何 accept/reject 建议**——评估只判定指标是否达标，不替用户拍板。达标仅意味着"值得考虑入因子库"，不入因子库也要走 reject 分支并沉淀教训（让后人知道"看起来达标但实际不可用"也是一种教训）。

### 7.1 propose 阶段的三重驳回（自由设计 + 可行性审查 + 创新性闸门）

propose 阶段有三层驳回闸门：

1. **机器门禁 G-PR-1 ~ G-PR-8**（详见 `.claude/skills/mine/stages/propose.md`）：
   - **G-PR-4**：失败教训**逐条 ID 引用**——主会话全量喂入失败库，proposer 必须**逐条引用**每一条失败条目 ID（如 `f003`/`f007`/`f012`），不允许摘要或只读部分。机器 grep 验证。
   - **G-PR-7**：F-1 ~ F-9 九项可行性自查（数据可得 / 无未来函数 / 计算可行 / 样本充足 / 数值稳定 / 解释清晰 / 与已入库不雷同 / 失败教训回避 / **已知因子撞库**）。
   - **G-PR-8**：F-9 已知因子撞库声明——≥3 个最接近的已知因子（含 Alpha#X、Alphalens Name、国内经典名、学术异象名）+ **关键差异** + 创新点声明。机器 grep 关键词命中。
   - 任一 FAIL → 主会话驳回，proposer 重提，attempts +1。

2. **主会话人工审查**（即便机器全 PASS，主会话仍可驳回）：
   - 想法太模糊、数据可得但计算成本过高、预期方向反了、与已入库因子雷同、像数据挖掘巧合、**本质就是某个已知因子的纯形式变形**等。

3. **兜圈断路器**：同一 propose 连续 3 次驳回 → `paused_blocked` 报用户决定。

---

## 八、TaskCreate 进度镜像

`propose` 定稿后，可用任务工具（TaskCreate / TodoWrite）按 `stage × 评估维度` 建任务树与依赖链，仅作 UI 进度镜像便于观察。**`state.json` 是唯一真相源**——任务树与 state 冲突时以 state 为准，不得反向依据任务树改判门禁。