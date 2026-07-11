# 失败因子库字段定义（failure_lessons_schema）

> 每次 `/mine reject` 由 `factor-archivist` 按本 schema 写一份 `library/failures/{id}.md`。**结构化、可 grep、可作为下一轮 propose 的输入**。

## 字段规范

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `factor_id` | 是 | string | `fNNN_slug` |
| `direction` | 是 | string | 用户原始方向（行情 / 财务 / 混合 / 自定义） |
| `category` | 是 | string | `market / fundamental / hybrid` + 细类（`momentum / reversal / quality / ...`） |
| `formula` | 是 | string | 因子公式（伪代码或自然语言） |
| `params` | 是 | YAML | 全部参数 |
| `reject_reason` | 是 | string | 用户拒绝理由原文 |
| `verdict` | 是 | enum | `pass / partial / fail` |
| `metrics_in_sample` | 是 | object | 样本内指标：`{rank_ic_mean, icir, ls_annual_return, ls_sharpe, ls_max_drawdown, monthly_turnover, n_months}` |
| `metrics_oos` | 是 | object | OOS 指标（同上字段） |
| `oos_decay_ratio` | 是 | float | OOS RankIC / 样本内 RankIC |
| `failure_modes` | 是 | list[string] | 命中的失败模式标签（来自 methodology.md 第四节） |
| `lesson_summary` | 是 | string | 教训要点（≤200 字） |
| `avoidance_suggestion` | 是 | string | 下次若再想做类似方向，建议如何改（≤200 字） |
| `decision_time` | 是 | ISO 8601 | 拒绝时间戳 |
| `evaluator_notes` | 否 | string | factor-evaluator 的额外观察 |

## 文件模板

```markdown
---
factor_id: f001_turnover_reversal_20d
direction: 行情价量类
category: market / reversal
formula: "factor = -(turnover_rate / turnover_rate.shift(20) - 1)"
verdict: fail
decision_time: 2026-07-12T10:30:00+08:00
---

# f001_turnover_reversal_20d · 失败档案

## 因子公式

`factor = -(turnover_rate / turnover_rate.shift(20) - 1)`

## 参数

```yaml
window: 20
neutralize: [industry, market_cap]
winsorize: mad_3
rebalance: monthly
```

## 拒绝理由

> IC 在 2018 单边下跌市失效；OOS 期 RankIC 反号

## 样本内指标

| 指标 | 值 |
|------|---|
| RankIC 均值 | -0.038 |
| ICIR | -0.92 |
| 多空年化 | 12.3% |
| 多空夏普 | 1.05 |
| 多空最大回撤 | 14% |
| 月均换手 | 65% |

## OOS 指标

| 指标 | 值 |
|------|---|
| RankIC 均值 | +0.012（反号！） |
| 多空年化 | -2.1% |
| OOS 衰减比 | -32%（失效） |

## 失败模式标签

- OOS 失效
- 反转因子在熊市系统性反转
- 单一窗口未做敏感性测试

## 教训要点

1. 纯反转因子在不同市场风格下方向不稳，2018 单边下跌市里反转失效（资金抱团核心资产）
2. 单一 20 日窗口对短期风格变化极敏感，未做 5/10/20/60 多窗口融合
3. **未做中性化检验**：原始因子与市值相关性高，扣市值后 IC 衰减严重

## 回避建议

下次若仍想做换手反转，建议：
1. 多窗口融合（5/10/20/60 等权或加权）
2. 加入市值 / 行业中性化作为前置
3. 加入"动量辅助"项（如 `momentum × reversal` 复合）以适应不同风格
```

---

## 教训笔记（library/lessons/failure_lessons.md）追加模板

```markdown

---

## {factor_id} · {方向} · {decision_time[:10]}

- **失败模式**：OOS 失效 / 市值伪 alpha / 行业轮动 / 换手虚高 / ...
- **因子公式**：...
- **样本内**：IC={x} ICIR={y} 多空={z}
- **OOS**：IC={x'} 衰减={%}
- **教训**：...
- **下次改**：...

```

**关键**：`factor-archivist` 必须 append 而非覆盖，工具 `factor_archiver.py reject` 命令已硬编码 append 行为。

---

## 检索 / 复用

后续 proposer 可以：
```bash
# 找所有"反转因子"失败案例
grep -l "reversal" library/failures/*.md

# 找所有"OOS 失效"案例
grep -B2 "OOS 失效" library/failures/*.md

# 取最近 10 条教训
head -200 library/lessons/failure_lessons.md
```