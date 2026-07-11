# code_review 阶段执行卡

> **目标**：审查 coder 交付的代码质量——检查冗余、性能、逻辑合理性。**只审查不实现，只报告不修改**。

## 前置断言

`check_gates.py --stage implement --assert-done` 必须 PASS。

## 动作（主会话执行，派 factor-code-reviewer agent）

1. **派 factor-code-reviewer**（`Agent` 工具，`subagent_type: factor-code-reviewer`）：
   - 输入：`workspace/{id}/src/` 全部代码 + `workspace/{id}/spec/` 规格文档 + `common/` 模块
   - 输出：`workspace/{id}/review/code_review_result.md`

2. **逐一点收**：
   - `ls -la workspace/{id}/review/code_review_result.md` 确认存在
   - 读取 code_review_result.md，检查 verdict

3. **出口门禁 G-CR**：
   - G-CR-1：`code_review_result.md` 存在
   - G-CR-2：`verdict` ∈ {pass, fail}
   - G-CR-3：若 fail，`issues` 列表非空

4. **决策**：
   - **PASS**：`set-stage code_review done` → 前进到 evaluate
   - **FAIL**：`set-stage code_review done`（但记录失败）→ 驳回给 coder 修复 → 重新 code_review

## 驳回处理

当 code_review FAIL 时：

1. **记录问题清单**：读取 `code_review_result.md` 的 `issues` 列表
2. **派 factor-coder 修复**：
   - 输入：原有代码 + code_review_result.md 的 issues 列表
   - 要求：针对每个 issue 修复代码
   - 输出：修复后的 `workspace/{id}/src/` 代码
3. **重新审查**：再次派 factor-code-reviewer 审查
4. **兜圈断路器**：同一 implement 连续 3 次 code_review FAIL → `paused_blocked` 报用户决定

## 兜圈断路器

同一 factor_id 同一 implement 的 code_review FAIL 次数 ≥3 → 强制 reject（不允许继续），报告里点出"该代码连续 3 次审查不通过，建议重新设计"。

## 产物清单

- `workspace/{id}/review/code_review_result.md`（审查结果）
