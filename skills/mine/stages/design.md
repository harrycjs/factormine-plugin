# design 阶段执行卡

> **目标**：把 proposer 的因子**规格**翻译成**可实现的算法描述**——给出精确的向量计算步骤、滚动窗口定义、数据 join 键、可选的中性化 / 缩尾方案，以及完整的测试用例（手工可算 / NaN 处理 / 异常值）。下游 coder 据此实现。

## 前置断言

`check_gates.py --stage propose --assert-done` 必须 PASS。

## 输入

- `workspace/{id}/spec/factor_proposal.md`
- `workspace/{id}/spec/design_notes.md`
- `workspace/{id}/spec/param_card.yaml`
- `templates/data_catalog.md`
- `common/` 现有模块签名（`factor_utils.py` / `factor_eval.py` / `data_loader.py`）
- `templates/methodology.md` 的"防未来函数" + "中性化" 章节

## 动作（主会话执行，不派 agent）

design 阶段不派 agent，由主会话**亲自**完成算法规范——这是编排与生产分离边界的特例（design 是机械翻译，不涉及主观判断）。但**严禁主会话写代码或调参实验**。

产出 `workspace/{id}/spec/algorithm_spec.md`，必须含：

1. **变量定义表**：每个中间变量含义、来源、shape、dtype。
2. **算法伪代码**：纯文字描述（"对每只股票，在每月底计算..."），列出全部 join、shift、rolling、groupby 操作。
3. **未来函数三查自检**：
   - [ ] 财务数据是否按 `info_publ_date` 对齐（不是 `end_date`）
   - [ ] 信号 T 日算出是否 T+1 执行
   - [ ] 滚动窗口只用 ≤ T 日数据
4. **NaN 处理规则**：各阶段 NaN 怎么填（drop / 0 / 前向填充？）。
5. **数值稳定性**：分母为零 / 极小值 / 极端值的处理（如 `sign(x) * log1p(abs(x))`、clip）。
6. **单元测试用例**：≥3 个手工可算的小样本（含 NaN / 极值 / 边界），下游 coder 用作自验证。
7. **依赖的 common 函数清单**：`winsorize / standardize / neutralize_factor / ...`，注明调用顺序。

## 输出合同

- `workspace/{id}/spec/algorithm_spec.md`（≥500 字）

## 出口门禁 G-DS

| 编号 | 检查 |
|------|------|
| G-DS-1 | `algorithm_spec.md` 存在且 >500 字 |
| G-DS-2 | 含"变量定义表"+"伪代码"+"未来函数三查"+"NaN 规则"+"单元测试"五个章节 |
| G-DS-3 | 未来函数三查勾选全部 ✓（任何一项未勾必 FAIL） |
| G-DS-4 | 至少 3 个单元测试用例，每个含输入样本 + 期望输出 |
| G-DS-5 | 列出的 common 函数全部存在（grep common/*.py 验证） |

## 失败处理

任一 FAIL：补缺后重审；G-DS-3 FAIL（未勾未来函数三查）视为**严重越界**，不允许 retry，直接 `paused_blocked` 报人工。