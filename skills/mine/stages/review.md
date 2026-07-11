# review 阶段执行卡

> **目标**：根据评估结果**自动决策**——达标则 accept 并停止迭代，不达标则 reject 并自动开下一轮。**无需人工干预**。

## 前置断言

`check_gates.py --stage evaluate --assert-done` 必须 PASS。

## 动作（主会话执行，不派 agent）

review 是**自动决策点**，不派 agent。主会话做四件事：

1. **读取评估产物**：`workspace/{id}/evaluate_result.json` + `metrics.json` + `eval_summary.md` + 5 张图。
2. **结构化呈现给用户**：
   - 一句话总结（verdict）
   - 核心指标表（IC / ICIR / 多空 / OOS 衰减）
   - 5 张图（用 `Read` 工具嵌入显示）
   - 已知风险（如 OOS 衰减、参数敏感性、拥挤风险）
   - **自动决策结果**：明确告知用户是 accept 还是 reject
3. **自动决策逻辑**（**无需用户确认**）：
   - **verdict = pass**：自动 accept，**停止迭代**，告诉用户已找到有效因子
   - **verdict = partial**：自动 reject（大部分指标不达标），**自动开下一轮**
   - **verdict = fail**：自动 reject，**自动开下一轮**
4. 状态写：`set-stage review done` + 根据决策写 `set status done`（pass）或 `set status done_rejected`（partial/fail）。

## 自动决策规则

### 自动 Accept 条件（停止迭代）

当 `evaluate_result.json` 的 verdict = `pass` 时：
1. **立即执行 accept 流程**（详见下方"自动 Accept 执行"）
2. **停止迭代**：不再调用 `next-iteration`，告诉用户"已找到有效因子，无需继续迭代"
3. **打印成功摘要**：因子ID、核心指标、入库位置

### 自动 Reject 条件（继续迭代）

当 `evaluate_result.json` 的 verdict ∈ {`partial`, `fail`} 时：
1. **立即执行 reject 流程**（详见下方"自动 Reject 执行"）
2. **自动开下一轮**：调用 `state.py next-iteration <id>` 自动开新轮
3. **不停顿询问**：直接推进到下一轮的 propose 阶段
4. **打印迭代摘要**：当前轮次结果、下一轮编号、剩余轮次

## 自动 Accept 执行

当 verdict = pass 时，主会话自动执行：

1. **记录决策**：写入 `workspace/{id}/review_decision.md`
   ```markdown
   # Review Decision
   - verdict: pass
   - decision: auto_accept
   - reason: 核心指标全部达标
   - timestamp: <自动填充>
   ```

2. **派 factor-archivist 走 approve 分支**（详见 `stages/archive.md`）：
   - 因子归档到 `library/approved/{id}/`（md + parquet + config 副本）
   - 更新 `library/approved/INDEX.md`（追加一行：id / 方向 / 类别 / 关键指标 / 入库日期）
   - 写入 `library/lessons/success_notes.md`（正向经验沉淀）

3. **状态更新**：
   ```bash
   uv run python "$MINE_TOOLS/state.py" set-stage <id> archive done
   uv run python "$MINE_TOOLS/state.py" set <id> status done
   ```

4. **打印成功消息**：
   ```
   ✅ 因子 {id} 自动通过！
   核心指标：|RankIC|={IC均值:.4f}, ICIR={ICIR:.2f}, 多空年化={多空年化:.1%}
   已入库到：library/approved/{id}/
   无需继续迭代，已找到有效因子。
   ```

## 自动 Reject 执行

当 verdict ∈ {partial, fail} 时，主会话自动执行：

1. **记录决策**：写入 `workspace/{id}/review_decision.md`
   ```markdown
   # Review Decision
   - verdict: {verdict}
   - decision: auto_reject
   - reason: 核心指标不达标（{列出未达标项}）
   - timestamp: <自动填充>
   ```

2. **派 factor-archivist 走 reject 分支**（详见 `stages/archive.md`）：
   - 因子归档到 `library/rejected/{id}/`
   - 失败案例写入 `library/failures/{id}.md`（按 `failure_lessons_schema.md`）
   - **追加教训到 `library/lessons/failure_lessons.md`**（关键！下轮 propose 必读）

3. **状态更新**：
   ```bash
   uv run python "$MINE_TOOLS/state.py" set-stage <id> archive done
   uv run python "$MINE_TOOLS/state.py" set <id> status done_rejected
   ```

4. **自动开下一轮**（**不停顿询问**）：
   ```bash
   uv run python "$MINE_TOOLS/state.py" next-iteration <id>
   ```
   - 若返回 `EXHAUSTED|...` / `NO_AUTO|...` → 停下，提示用户换方向或调整配置
   - 若返回 `NEXT|<new_id>|<n>/<max>|<direction>` → 直接推进到新轮的 propose 阶段
   - **新轮 prompt 必须附上**：本轮失败 ID + 失败原因摘要 + 让 proposer 基于教训微调

5. **打印迭代摘要**：
   ```
   ❌ 因子 {id} 未达标（verdict={verdict}）
   未达标项：{列出具体指标}
   已自动开下一轮：{new_id}（第 {n}/{max} 轮）
   方向：{direction}
   继续推进中...
   ```

## 出口门禁 G-RV

| 编号 | 检查 |
|------|------|
| G-RV-1 | `evaluate_result.json` 的 verdict 已读取 |
| G-RV-2 | 自动决策（accept / reject）已记录到 `workspace/{id}/review_decision.md` |
| G-RV-3 | 决策时间戳存在 |
| G-RV-4 | **accept 时**：archive 阶段已完成，状态为 `done` |
| G-RV-5 | **reject 时**：archive 阶段已完成，状态为 `done_rejected`，且 next-iteration 已调用 |

review 阶段的 G-RV 是**记账 + 自动推进**，不阻断流程。

## 兜圈断路器

同一 factor_id 同一 design 的迭代轮次 ≥3 → 强制 reject 且**不再自动开下一轮**，报告里点出"该方向已迭代 3 轮仍不达标，建议换方向"。