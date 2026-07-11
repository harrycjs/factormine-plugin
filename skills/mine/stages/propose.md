# propose 阶段执行卡

> **目标**：基于用户给的方向 + 失败教训库 + 方法论参考，由 AI **完全自由**设计 1 个候选因子；**通过可行性审查**（F-1 ~ F-8 + G-PR-7 机器闸门），产出可被下游 stage 消费的规格说明。
>
> ⚠️ **不强制使用任何因子白名单**。AI 可基于任何合理的金融直觉、文献启发、跨域灵感自由构造因子。`templates/factor_formulas.md` 是可选参考，不是约束。

## 前置必做（主会话执行）

1. **必须完整读取失败教训**（硬规则 5，**不得摘要**）：
   ```bash
   # 主会话 Read 完整文件全文
   [ -f library/lessons/failure_lessons.md ] && cat library/lessons/failure_lessons.md
   # 同时读所有结构化失败档案
   for f in library/failures/*.md; do [ -f "$f" ] && echo "=== $f ===" && cat "$f"; done
   ```
   把**全文**（不是摘要）随 prompt 喂给 `factor-proposer`。**严禁摘要**——每条失败条目都必须喂入，避免下游 agent 漏掉部分。
2. **可选读取方法论参考**：`Read templates/factor_formulas.md` + `templates/methodology.md` 第八章（已知因子撞库清单）。
3. **读取已知因子撞库清单**：主会话把 `templates/methodology.md` 第八章内容（或该文件路径）随 prompt 喂给 proposer。

## 派发合同（主会话给 agent 的输入）

```
输入：
1. 用户方向字符串（如 "行情价量类"、"财务质量类"、"我自己描述: 20 天跌幅 5% 反转"）
2. **失败库全文**（不是摘要！）：
   - library/lessons/failure_lessons.md 完整内容
   - library/failures/*.md 全部档案
3. 已知因子撞库清单（templates/methodology.md 第八章全文）
4. templates/factor_formulas.md 的可选参考（**非强制**）
5. templates/methodology.md 的关键章节摘要（"挖因子流程" + "评估指标"）
6. .mine.json 的全局配置（数据路径 / 股票池 / 年份区间）
7. 已成功入库因子列表（library/approved/INDEX.md 摘要，避免重复造轮子）

【设计自由度】因子表达式完全自由，可构造任何形式的因子——算术组合、
滚动统计、截面运算、时序序列、跨域类比、LLM 灵感。**不强制白名单**。
**但不能是任何已知因子**——必须通过 F-9 撞库自检，列出 ≥3 个最接近
的已知因子并说明关键差异。

【失败库读取】你必须**完整读取**失败库（不是摘要），并在 proposal 中
**逐条引用每一条失败条目的 ID**（如 f003 / f007 / f012），说明本因子
如何回避。**只读部分 / 摘要都会被驳回**。

【可行性自查】你必须在 factor_proposal.md 中逐项勾选 F-1 ~ F-9 共 9 项
可行性自查清单（见 templates/factor_formulas.md），任一项缺失或未勾将导致驳回。

【输出合同】
workspace/{id}/spec/factor_proposal.md：
  1. 因子定义（公式 + 数据依赖 + 计算步骤）
  2. 预期方向 + 经济直觉 + 分类标签
  3. 数据可用性自检（标注 available/derive/missing）
  4. **失败教训逐条回避声明**（**每条失败 ID 必引**，不止 ≥3 条——必须全部覆盖）
  5. **已知因子撞库声明（F-9）**（≥3 个最接近的已知因子 + 关键差异）
  6. 可行性自查清单 F-1 ~ F-9 全勾
  7. 与已入库因子的差异声明
```

## 派发（factor-proposer, opus）

```python
Agent(
    subagent_type="factor-proposer",
    prompt=PROMPT,  # 见上文
    description="提出候选因子（自由设计 + 可行性自查）"
)
```

## 输出合同（必须逐一产出）

`workspace/{id}/spec/`：
1. `factor_proposal.md`——候选因子规格说明，必须含：
   - **因子定义**：公式 / 操作符 / 数据依赖（按 data_catalog 字段名）
   - **直观假设**：为什么这个因子可能有效（行为金融 / 风险溢价 / 套利逻辑 / **跨域类比 / LLM 灵感**）
   - **预期方向**：因子值大 → 未来收益高 还是 低？
   - **分类标签**：`market / fundamental / hybrid`，`trend / reversal / quality / value / volatility / liquidity / 其他`
   - **数据可用性自检**：按 data_catalog 标注字段 status（available / derive / missing）
   - **失败教训回避声明**：「本因子刻意回避了以下失败模式：...」——**逐条引用每一条失败条目 ID**（如 f003 / f007 / f012），并说明如何回避（**不是摘要，不是 ≥3 条——必须全覆盖**）
   - **已知因子撞库声明（F-9）**：≥3 个最接近的已知因子（含 Alpha#X、Alphalens Name、国内经典名、学术异象名）+ 关键差异 + 创新点
   - **可行性自查清单 F-1 ~ F-9**：9 项必须**全部 ✓**，任何一项缺失 → 主会话驳回
   - **与已入库因子的差异声明**
2. `design_notes.md`——设计要点（计算复杂度 / 滚动窗口长度 / 中性化方案 / 频率）
3. `param_card.yaml`——参数卡（窗口长度、中性化开关、是否缩尾、换仓频率），全部进 config 化，下游 coder 不允许魔法数字

## 硬约束（agent 必守）

- **不派发任何其他 agent**、不调用 skill、不启动 Task 工具。
- **不读 / 写 `workspace/{id}/state.json`**（主会话专用）。
- **全中文输出**，不使用 emoji。
- **必须复述失败教训**：在 `factor_proposal.md` 自检 checklist 里逐条回答「本因子如何回避教训 N」。
- **不允许提"经典 alpha101 第 N 号"的简单复刻**——必须基于自由设计给出**新组合 / 新变形 / 全新构造**，且附理由。
- **可行性自查必须逐项勾选**：F-1 ~ F-8 任一项未勾或 NA → 主会话直接驳回。

## 出口门禁 G-PR

`check_gates.py --stage propose` 机器核对：

| 编号 | 检查 |
|------|------|
| G-PR-1 | `factor_proposal.md` 存在且 >500 字 |
| G-PR-2 | `design_notes.md` 存在 |
| G-PR-3 | `param_card.yaml` 存在且 YAML 可解析 |
| G-PR-4 | `factor_proposal.md` 自检区有「失败教训回避声明」且 ≥3 条 |
| G-PR-5 | 因子定义里数据字段在 data_catalog 全部 status=available 或 derive（不允许 missing） |
| G-PR-6 | 不与 library/approved/INDEX.md 中已入库因子定义完全雷同（允许相关性，但公式需有显著差异） |
| **G-PR-7** | **可行性自查 F-1 ~ F-8 全部勾选**（机器 grep 八项关键词） |

## 驳回协议（关键）

主会话在收到 proposer 返回后，必须按以下顺序审查：

### 第一层：机器门禁（G-PR-1 ~ G-PR-7）

- 任一 FAIL → 缺失清单，重派 proposer（pass 7 项才算通过）。
- G-PR-7 FAIL（可行性自查未勾全）→ **视为不可行，主会话直接驳回**，proposer 必须重提（不算重试，attempts +1）。

### 第二层：人工可行性审查

即便机器全 PASS，主会话**仍可基于人工判断驳回**。驳回理由示例：

- "想法太模糊（虽然机器没抓到，但实际不可执行）"
- "数据可得但计算成本过高（60s 内完不成）"
- "预期方向反了（金融直觉有误）"
- "与已入库因子雷同（虽变形但本质相同）"
- "听起来像数据挖掘巧合（无清晰经济直觉）"

### 第三层：兜圈断路器

- 同一 propose 连续 **3 次驳回**（无论机器还是人工）→ `set status paused_blocked` + `pending_question "propose 连续 3 次驳回，请用户决定：换方向 / 放低门槛 / 放弃"` + `record-event`。
- 驳回时主会话记录到 `state.events`，记 `set-stage propose running` 重跑 attempts +1。

### 第四层：通过放行

所有门禁通过 → `set-stage propose done`，前进到 design 阶段。

## 失败处理

- G-PR-1/2/3 任一 FAIL：缺失文件清单，重派 proposer。
- G-PR-4 FAIL：未真正读失败教训，主会话**当场复读教训摘要**后重派。
- G-PR-5 FAIL：proposer 漏看了数据缺口，需降级（用 derive 字段）或换方向。
- G-PR-6 FAIL：与已入库因子雷同，需明确变形理由，否则重派。
- **G-PR-7 FAIL**：可行性自查未勾全，主会话**驳回**（不是简单重试，要求 proposer 重做可行性分析）。