# review 阶段执行卡

> **目标**：把评估产物**呈现给用户**，等待用户做人工审查（accept / reject / iterate）。**机器不替你拍板**。

## 前置断言

`check_gates.py --stage evaluate --assert-done` 必须 PASS。

## 动作（主会话执行，不派 agent）

review 是**人机界面**，不派 agent。主会话做四件事：

1. **读取评估产物**：`workspace/{id}/evaluate_result.json` + `metrics.json` + `eval_summary.md` + 5 张图。
2. **结构化呈现给用户**：
   - 一句话总结（verdict）
   - 核心指标表（IC / ICIR / 多空 / OOS 衰减）
   - 5 张图（用 `Read` 工具嵌入显示）
   - 已知风险（如 OOS 衰减、参数敏感性、拥挤风险）
   - 决策建议（**仅作参考**，不替用户拍板）：若 verdict=pass，建议 accept；verdict=partial，标黄提醒；verdict=fail，建议 reject
3. **人工审查闸门**：把决策权交给用户。主会话**绝不自行 accept/reject**。
4. 状态写：`set-stage review done`（不写 `status`，留待用户决策后写）。

## 用户决策（主会话响应的子命令）

### `accept <id>`（人工审查通过）

派 `factor-archivist` 走 `approve` 分支（详见 `stages/archive.md`）：
1. 因子归档到 `library/approved/{id}/`（md + parquet + config 副本）。
2. 更新 `library/approved/INDEX.md`（追加一行：id / 方向 / 类别 / 关键指标 / 入库日期）。
3. 写入 `library/lessons/success_notes.md`（**正向经验沉淀**，让后人知道"什么样的因子值得入"）。
4. `set-stage archive done` → `set status done`。

### `reject <id> "<reason>"`（人工拒收）

派 `factor-archivist` 走 `reject` 分支：
1. 因子归档到 `library/rejected/{id}/`。
2. 失败案例写入 `library/failures/{id}.md`（按 `failure_lessons_schema.md`）。
3. **追加教训到 `library/lessons/failure_lessons.md`**（关键！下轮 propose 必读）。增量追加而非覆盖。
4. `set-stage archive done` → `set status done_rejected`。

### `iterate <id> "<方向>"`（想重做）

1. 在 `workspace/{id}/iterations/` 下开 `iter_NN/`。
2. `set-stage design running`（回到 design，但**保留 algorithm_spec.md**作为参照）→ 用户给的方向喂给 proposer 重出。
3. 计数加 1（避免无限迭代，3 次强制 reject）。

## 出口门禁 G-RV

| 编号 | 检查 |
|------|------|
| G-RV-1 | `evaluate_result.json` 的 verdict 已在用户面前呈现 |
| G-RV-2 | 用户决策（accept / reject / iterate）已记录到 `workspace/{id}/review_decision.md` |
| G-RV-3 | 决策时间戳存在（用于沉淀时的"最近拒绝时间"标注） |

review 阶段的 G-RV 主要是**记账**，不阻断流程——真正的判定是用户决策本身。

## 兜圈断路器

同一 factor_id 同一 design 的迭代轮次 ≥3 → 强制 reject（不允许继续迭代），报告里点出"该方向已迭代 3 轮仍不达标"。