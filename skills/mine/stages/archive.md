# archive 阶段执行卡

> **目标**：把本轮产物**正式归档**——approved 入因子库 / rejected 入失败库 / 两者都要**追加教训笔记**。所有归档走 `tools/factor_archiver.py` 工具，**严禁主会话手动 cp / 写 md**（防遗漏字段）。

## 前置断言

`check_gates.py --stage review --assert-done` 必须 PASS。

## 输入

- `workspace/{id}/` 全套产物
- 用户决策（accept / reject）
- `library/failures/failure_lessons_schema.md`（沉淀格式）

## 派发（factor-archivist, opus）

按 review 阶段的决策分两个分支：

### 分支 A：accept

```python
Agent(
    subagent_type="factor-archivist",
    prompt=PROMPT_ACCEPT,  # 含 approved 分支指令
    description="因子入 approved 库 + 追加正向经验"
)
```

执行：
1. `python tools/factor_archiver.py approve {id} --decision-time <ts>`（工具负责文件落位、INDEX.md 更新、YAML 校验）。
2. 写 `library/lessons/success_notes.md`（正向经验：什么样的因子通过了，类目归纳：动量类 / 反转类 / 质量类 / 估值类 等）。

### 分支 B：reject

```python
Agent(
    subagent_type="factor-archivist",
    prompt=PROMPT_REJECT,
    description="因子入 failures 库 + 追加教训"
)
```

执行：
1. `python tools/factor_archiver.py reject {id} --reason "<user_reason>" --decision-time <ts>`
2. **追加教训到 `library/lessons/failure_lessons.md`**（关键！必须新增一节，而非覆盖）。
3. 教训条目至少包含：失败模式类别 / 因子公式 / 在样本内 / 在 OOS / 教训要点。

## 输出合同（factor-archivist 必产）

### accept 分支

- `library/approved/{id}/README.md`——因子规格文档（含定义、公式、参数、入库日期、关键指标）
- `library/approved/{id}/config.yaml`——参数副本
- `library/approved/{id}/factor.py`——因子纯函数副本
- `library/approved/INDEX.md` 追加一行
- `library/lessons/success_notes.md` 追加一节

### reject 分支

- `library/rejected/{id}/README.md`——简短摘要（为什么被拒）
- `library/failures/{id}.md`——按 `failure_lessons_schema.md` 全字段填写
- `library/lessons/failure_lessons.md` **追加一节**（不得覆盖）

## 硬约束

- **必须用 `factor_archiver.py` 工具**，不允许手工 cp 文件。
- **必须追加**而非覆盖 `failure_lessons.md`。
- **archive 阶段本身**写文件，但不调任何子 agent。

## 出口门禁 G-AR

### accept 分支

| 编号 | 检查 |
|------|------|
| G-AR-1 | `library/approved/{id}/README.md / config.yaml / factor.py` 全在 |
| G-AR-2 | `library/approved/INDEX.md` 已追加本轮 id |
| G-AR-3 | `library/lessons/success_notes.md` 已追加 |

### reject 分支

| 编号 | 检查 |
|------|------|
| G-AR-4 | `library/rejected/{id}/README.md` 在 |
| G-AR-5 | `library/failures/{id}.md` 在且字段齐全（对照 schema） |
| G-AR-6 | `library/lessons/failure_lessons.md` 已追加一节（行数 + N 行 vs 旧版行数 + 0） |
| G-AR-7 | **追加内容含本轮因子公式、OOS 表现、教训要点**（机器 grep 三关键词） |

## 失败处理

- G-AR-6 FAIL（教训未追加）：**严重越界**，不允许 retry，直接 `paused_blocked` 报人工（违背硬规则 5）。
- 其余 FAIL：缺失清单，重派 archivist。