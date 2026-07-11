# implement 阶段执行卡

> **目标**：依据 `algorithm_spec.md` 实现因子计算 + 一键回测脚本，**冒烟运行可执行**（不宣布指标结论）。

## 前置断言

`check_gates.py --stage design --assert-done` 必须 PASS。

## 派发合同

```
输入：
1. workspace/{id}/spec/algorithm_spec.md（权威）
2. workspace/{id}/spec/param_card.yaml
3. common/ 现有模块（factor_utils.py / factor_eval.py / data_loader.py）
4. templates/factor.md（如果存在；类型模板）
5. .mine.json 全局配置
```

## 派发（factor-coder, opus）

```python
Agent(
    subagent_type="factor-coder",
    prompt=PROMPT,
    description="实现因子计算与回测脚本"
)
```

## 输出合同

- `workspace/{id}/src/factor.py`——纯函数 `compute_factor(panel, params) -> DataFrame[stock_code, date, factor]`，无 IO、无随机种子。
- `workspace/{id}/src/config.py`——参数集中（从 param_card.yaml 读入）。
- `workspace/{id}/src/main.py`——调 common 跑完整流水线：加载数据 → 算因子 → 预处理（winsorize/standardize/neutralize）→ 算 forward_return → 评估（IC/分组/多空）→ 出图 + Excel。
- `workspace/{id}/src/_smoke.py`——单元测试脚本（跑 algorithm_spec.md 给的 ≥3 个手工用例），**只许冒烟通过**，不允许宣布"因子有效"。

## 硬约束（agent 必守）

- **未来函数三查**（**这是 implement 阶段最容易翻车的点**）：
  - 财务数据按 `info_publ_date` 对齐（不是 `end_date`）
  - T 日信号 T+1 执行（`forward_return` 用 T+1 ~ T+21 区间收益）
  - 滚动窗口只用历史数据
- **config.py 集中参数**，函数体内禁魔法数字。
- **冒烟运行**：只跑 `_smoke.py` 与 `python -m compileall src/`，**不跑完整回测**（评估结论归 factor-evaluator）。
- **不读 / 写 `workspace/{id}/state.json`**。
- **不调 codex**（codex 是评估阶段反虚报用，不在实现阶段用）。
- **复用 common/**：禁止在 src/ 重复实现 winsorize / standardize / 中性化 / IC 计算。

## 出口门禁 G-IM

| 编号 | 检查 |
|------|------|
| G-IM-1 | `factor.py / config.py / main.py / _smoke.py` 全部存在 |
| G-IM-2 | `_smoke.py` 单元测试全部通过（机器跑） |
| G-IM-3 | `python -m compileall workspace/{id}/src/` 无语法错误 |
| G-IM-4 | `main.py` 能 import 成功（机器跑 `python -c "from workspace.{id}.src.main import main"` 之类 dry-run） |
| G-IM-5 | config.py 参数全部能从 param_card.yaml 反查（grep 比对） |

## 失败处理

- G-IM-2 FAIL：冒烟测试失败 → 重派 coder（不允许擅自改 spec）。
- G-IM-3/4 FAIL：语法 / import 错误 → 重派 coder。
- G-IM-5 FAIL：有魔法数字 → 重派 coder 让其登记到 config.py。

## 兜圈断路器

G-IM 连续 3 次 FAIL → `paused_blocked` 报人工（很可能是 algorithm_spec 本身有问题，回 design 修复）。