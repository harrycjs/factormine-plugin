# validation 阶段执行卡

> **目标**：验证 proposer 设计的因子方案是否声明齐全、逻辑清晰、可执行。**只验证不设计，只检查不实现**。

## 前置断言

`check_gates.py --stage propose --assert-done` 必须 PASS。

## 动作（主会话执行，派 factor-validator agent）

1. **派 factor-validator**（`Agent` 工具，`subagent_type: factor-validator`）：
   - 输入：`workspace/{id}/spec/` 全部规格文档 + `templates/data_catalog.md` + `templates/factor_formulas.md` + `library/approved/INDEX.md`
   - 输出：`workspace/{id}/spec/validation_result.md`

2. **逐一点收**：
   - `ls -la workspace/{id}/spec/validation_result.md` 确认存在
   - 读取 validation_result.md，检查 verdict

3. **出口门禁 G-VD**：
   - G-VD-1：`validation_result.md` 存在
   - G-VD-2：`verdict` ∈ {pass, fail}
   - G-VD-3：若 fail，`issues` 列表非空

4. **决策**：
   - **PASS**：`set-stage validation done` → 前进到 design
   - **FAIL**：`set-stage validation done`（但记录失败）→ 驳回给 proposer → 回到 propose（attempts +1）

## 驳回处理

当 validation FAIL 时：

1. **记录驳回原因**：读取 `validation_result.md` 的 `issues` 列表
2. **派 factor-proposer 补充**：
   - 输入：原有 proposal + validation_result.md 的 issues 列表
   - 要求：针对每个 issue 补充声明或修正逻辑
   - 输出：更新后的 `workspace/{id}/spec/factor_proposal.md` + `param_card.yaml` + `design_notes.md`
3. **重新验证**：再次派 factor-validator 验证
4. **兜圈断路器**：同一 propose 连续 3 次 validation FAIL → `paused_blocked` 报用户决定

## 兜圈断路器

同一 factor_id 同一 propose 的 validation FAIL 次数 ≥3 → 强制 reject（不允许继续），报告里点出"该方案连续 3 次验证不通过，建议换方向"。

## 产物清单

- `workspace/{id}/spec/validation_result.md`（验证结果）
