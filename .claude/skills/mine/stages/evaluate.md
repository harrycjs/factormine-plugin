# evaluate 阶段执行卡

> **目标**：**亲自跑 main.py 出全套评估指标**——IC / ICIR / RankIC / 分组回测 / 多空组合 / 换手 / 衰减 / **样本外 (OOS) 表现**——并按 `templates/eval_standards.json` 的门槛判定是否达标。**只评估，不替用户拍板 accept/reject**。

## 前置断言

`check_gates.py --stage implement --assert-done` 必须 PASS。

## 派发合同

```
输入：
1. workspace/{id}/src/ （coder 交付的代码）
2. workspace/{id}/spec/ （全部规格文档）
3. .mine.json 全局配置（数据路径 / 年份区间 / 股票池）
4. templates/eval_standards.json（评估门槛）
5. templates/methodology.md 的"评估指标" + "防过拟合"章节
6. main.py 的运行方式
```

## 派发（factor-evaluator, opus）

```python
Agent(
    subagent_type="factor-evaluator",
    prompt=PROMPT,
    description="全量评估 + 样本外检验"
)
```

## 评估维度（必出，缺一不可）

1. **全样本 IC 序列**：月度 RankIC 柱状图 + 累计图。
2. **IC 分布直方图**：检验是否接近正态（极端偏态 → 怀疑样本污染）。
3. **分组回测**（默认 5 组）：等权分组年化收益 + 单调性 + 多空。
4. **多空组合**：年化、夏普、最大回撤、Calmar、胜率。
5. **换手率**：每月换手（高频 → 实盘成本高）。
6. **稳健性**：
   - **不同年份切片**：把样本期切成 3 段（早/中/晚），分别看 IC。
   - **不同股票池切片**：大盘 vs 中盘 vs 小盘，分别看。
   - **参数敏感性**：核心参数 ±20%，看 IC 衰减（衰减 > 50% 视为脆弱）。
7. **样本外 (OOS)**：把年份区间**末 20%** 留作 OOS，剩余做样本内；OOS 期 |RankIC| ≥ 样本内 50% 视为强稳健。
8. **多重检验修正**：若本轮迭代 ≥3 个候选同方向挖，Bonferroni / FDR 修正显著性。

## 输出合同

`workspace/{id}/results/`：
- `ic_series.png / ic_distribution.png / group_cumulative_returns.png / group_returns_bar.png / net_value_comparison.png`（5 张标准图，300 DPI，蓝红配色）
- `factor_eval.xlsx`（多 sheet：回测摘要 / IC 序列 / 分组收益 / 分组净值 / OOS 对比 / 稳健性）
- `oos_comparison.json`（结构化：样本内 vs 样本外指标）
- `eval_summary.md`（人读摘要）
- `metrics.json`（**机器可读全部指标**，门禁重算的唯一来源）

`workspace/{id}/`：
- `evaluate_result.json`（最终判定：`pass` / `partial` / `fail`，由 metrics.json + standards.json 重算得出）

## 硬约束

- **亲自跑 main.py**（或 factor-evaluator 内部脚本），不采信 coder 自述。
- **不调优参数**：评估阶段不允许根据指标反馈调整因子计算逻辑——调参属于 implement 的下一轮迭代。
- **不宣布 accept / reject**：evaluate_result.json 只输出 `pass/partial/fail`，由用户在 review 阶段决定。

## 出口门禁 G-EV

| 编号 | 检查 |
|------|------|
| G-EV-1 | `metrics.json` 存在且含 ≥12 个核心指标 |
| G-EV-2 | `oos_comparison.json` 存在且 OOS 期 ≥ 24 个月 |
| G-EV-3 | 5 张图全部存在且 ≥15KB |
| G-EV-4 | `factor_eval.xlsx` 存在且 ≥30KB |
| G-EV-5 | `evaluate_result.json` 存在；其 `verdict` 字段 ∈ {pass, partial, fail} |
| G-EV-6 | **核心门槛检查**：对照 eval_standards.json 至少 4 项达标才能 pass，否则 fail（partial 容忍 1 项核心未达标且非 OOS） |
| G-EV-7 | **OOS 衰减检查**：OOS RankIC / 样本内 RankIC ≥ 0.5，否则即便样本内全过也判 partial（OOS 不稳健） |

## 失败处理

- G-EV-1/2/3/4 FAIL：评估未跑全，重派 evaluator。
- G-EV-6/7 FAIL：达标/不达标是结果**不是 stage 失败**——evaluate 阶段仍可 done，但 verdict 为 fail / partial，由 review 阶段决定 reject / iterate。