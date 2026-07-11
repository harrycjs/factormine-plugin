# 因子挖掘方法论参考（固化版）

> 本文件固化本插件采用的方法论，**`factor-proposer` 与 `factor-evaluator` 在派发 prompt 里必须包含本文件的摘要**。来源包括：WorldQuant 101 Formulaic Alphas、Alphalens（Quantopian 因子评估开源库）、gplearn 遗传编程、AlphaGen / MASTER / IGSG（深度学习生成因子）、Alpha-GPT / QuantAgent（LLM 辅助因子挖掘）、WorldQuant Brain / AlphaWorks 平台文档，以及公开学术论文与社区博客。

---

## 一、挖因子标准流程（一张图说清）

```
[用户方向 / 灵感]
     │
     ▼
[读取失败教训库] ← library/lessons/failure_lessons.md（强制）
     │
     ▼
[提出候选因子] ← factor-proposer（白名单 + 直觉）
     │
     ▼
[设计算法规范] ← 主会话（机械翻译，不派 agent）
     │
     ▼
[实现 + 冒烟]  ← factor-coder
     │
     ▼
[全量评估 + OOS] ← factor-evaluator
     │
     ▼
[人工审查]      ← 用户 accept / reject / iterate
     │
     ├── accept → 入 approved 库 + 追加正向经验
     └── reject → 入 failures 库 + 追加失败教训（关键！下轮 propose 必读）
```

---

## 二、因子表达式空间（factor-proposer 的"白名单"）

详细范式见 `templates/factor_formulas.md`。本节是高层分类：

### 1. 经典动量 / 反转

- N 日动量：`close / close.shift(N) - 1`
- N 日反转：`-(close / close.shift(N) - 1)`
- 跳跃动量（skip-N-day momentum）：`close / close.shift(N+K) - 1`，跳开最近 K 天
- 时间加权动量（exponentially weighted）：`(close.pct_change().ewm(span=N).mean())`

### 2. 价量关系

- 量价相关性：`rolling(N).corr(volume, close)`（注意：是否当日相关性，还是 close 与 volume 各自的 rolling）
- 资金流：`((close - low) - (high - close)) / (high - low) * volume`（typical money flow）
- 换手率加权收益：`change_pct * turnover_rate`
- 资金净流入：`close * volume * sign(close_change)`

### 3. 波动率 / 风险类

- 已实现波动率：`rolling(N).std(change_pct)`
- Parkinson 波动：`sqrt(1/(4*N*ln2) * (ln(high/low))^2).rolling(N).mean()`
- Garman-Klass 波动：综合 OHLC
- 上行 / 下行波动比

### 4. 流动性 / 微观结构

- Amihud 非流动性：`abs(change_pct) / turnover_value`，滚动平均
- 换手率趋势：`turnover_rate / turnover_rate.shift(N) - 1`
- 成交额集中度：`top N 成交额占全市场比例`（截面）

### 5. 估值 / 基本面（财务类，需 `info_publ_date` 对齐）

- EP / BP / SP / DP：`net_profit / market_value` 等
- PEG：`PE / earnings_growth`
- ROE / ROA
- 资产负债率
- 现金流 / 净利润比

### 6. 截面 / 横截面类

- 截面分位（factor = rank / pct_rank）
- 行业中性化（剔除行业 Beta）
- 市值中性化（剔除小盘溢价 / 大盘溢价）
- 双重排序（先按市值分组再按目标因子分组）

### 7. 复合 / 机器学习衍生

- 算术 / 几何 / 调和平均（多窗口）
- 时序聚合：`max / min / median / quantile` over rolling windows
- gplearn 遗传编程的树形组合
- 神经网络 / 树模型的特征重要性派生因子
- LLM 表达式生成（Alpha-GPT 类）

---

## 三、因子有效性评估指标（factor-evaluator 的"达标判定"）

### 3.1 主指标

| 指标 | 公式 | 通过门槛（默认） | 备注 |
|------|------|----------------|------|
| **RankIC 均值** | Spearman(factor, forward_return) 的均值 | \|x\| ≥ 0.025 | 月频横截面 |
| **ICIR** | IC 均值 / IC 标准差 × sqrt(12) | ≥ 0.5 | 年化 |
| **IC 胜率** | P(IC > 0) | ≥ 55% | 方向稳定性 |
| **多空年化收益** | (top_group - bottom_group) 年化 | ≥ 8%（扣费后） | 月频调仓 |
| **多空夏普** | mean(excess) / std × sqrt(12) | ≥ 0.8 | |
| **多空最大回撤** | 累计净值最大跌幅 | ≤ 20% | |
| **分组单调性** | G1 < G2 < ... < G5 | 方向正确即可 | 强度不卡死 |
| **月均换手** | 各组每月成分股变化率均值 | ≤ 80% | 量级 |

### 3.2 稳健性 / OOS（最强门槛）

| 维度 | 检查 | 通过门槛 |
|------|------|---------|
| **OOS RankIC 衰减** | 末 20% 期 / 样本内 | OOS ≥ 50% 强稳健；< 30% 视为失效 |
| **参数敏感性** | 核心窗口 ±20% | IC 衰减 ≤ 50% |
| **年份切片** | 早/中/晚 3 段 | 各段 IC 同号 |
| **股票池切片** | 大/中/小盘 | 大盘至少不显著反号 |
| **多重检验** | Bonferroni 修正 | 修正后仍显著 |

### 3.3 评级口径（机器硬编码）

- **pass**：核心 4 项（|RankIC| / ICIR / 多空年化 / OOS 衰减）**全部达标**
- **partial**：4 项中 ≤1 项未达标，且未达标项**不是 OOS**
- **fail**：≥2 项未达标，或 OOS 显著失效

详细字段与阈值在 `templates/eval_standards.json`，机器以该 JSON 为唯一判定依据。

---

## 四、常见失败陷阱（factor-proposer 必读，factor-archivist 沉淀）

> 本节是失败教训库的种子内容。后续每轮 reject 都会**追加**新条目。

### 4.1 数据 / 时点类

1. **未来函数（look-ahead bias）**
   - 表现：样本内指标完美，OOS 完全失效
   - 根因：用 `end_date`（报告期）而非 `info_publ_date`（披露日）对齐；信号用到 T+1 之后的数据
   - 防御：所有财务字段强制 `info_publ_date`；滚动窗口 shift(1)；`forward_return` 用 T+1 起算

2. **幸存者偏差（survivorship bias）**
   - 表现：在退市股上"高收益"看起来很稳，但实盘买不到
   - 根因：股票池只取当前仍在交易的，剔除已退市
   - 防御：始终保留退市股历史数据，剔除逻辑只剔除"今日不可买"的（停牌、ST、上市未满）

3. **涨跌停未剔除**
   - 表现：因子在涨停日看似"动量"极强，实为流动性失效
   - 根因：把涨停日当正常交易日
   - 防御：因子计算日剔除 `ashare_stock_limit.parquet` 标记的涨停 / 跌停 / 停牌日

### 4.2 因子构造类

4. **未中性化的市值伪 alpha**
   - 表现：小盘因子 IC 极高，但扣除市值后归零
   - 根因：因子与 ln(市值) 高度相关
   - 防御：中性化流程必须包含 `ln(market_cap)` 回归剔除

5. **未中性化的行业伪 alpha**
   - 表现：行业轮动而非个股 alpha
   - 根因：因子在某些行业系统性偏高 / 低
   - 防御：行业 dummy 回归（CITICS 一级 standard_code=37）

6. **窗口过短的过拟合**
   - 表现：5 日动量极强但不稳定
   - 根因：短窗口对噪声敏感，IC 衰减快
   - 防御：核心窗口 ≥ 20 日（除非有强假设）

### 4.3 评估类

7. **未做 OOS 检验的假 alpha**
   - 表现：样本内 IC 0.05 / ICIR 1.2，OOS 直接反转
   - 根因：参数在样本内调优
   - 防御：年份区间**末 20%** 强制留 OOS，不参与调参

8. **未做多重检验修正的 p-hacking**
   - 表现：连续挖 10 个方向，1 个显著即报"找到 alpha"
   - 根因：抽样误差
   - 防御：Bonferroni 修正（除以候选数）

9. **换手未扣费的虚高多空**
   - 表现：月换手 200%，多空 30% 年化，扣费后归零
   - 根因：评估时只算毛收益
   - 防御：双边千三成本扣减

### 4.4 入库类

10. **"达标即入库"的过松门槛**
    - 表现：accept 一堆 pass 因子，实际不能用于实盘
    - 根因：指标门槛只是"值得考虑"，不等于"实际可用"
    - 防御：review 阶段**人工审查**（不看指标看逻辑），机器不替你拍板

11. **同类因子重复入库**
    - 表现：approved 库里 20 个因子其实相关性 > 0.9
    - 根因：未与 INDEX.md 比对
    - 防御：propose 阶段必读 INDEX.md，重复需变形理由

12. **过度拟合市场风格**
    - 表现：在某年风格（如 2020 抱团）有效，其他年份反转
    - 根因：IC 高集中在特定年份
    - 防御：年份切片 3 段同号才入库

---

## 五、沉淀机制（失败库 + 教训笔记）

### 失败库（library/failures/{id}.md）

每次 reject 写一份，字段见 `templates/failure_lessons_schema.md`。**结构化、可 grep**。**文件名以 factor_id 命名**（如 `f001_xxx.md`），保证 G-PR-4 能 grep `f001` 这类 ID 标记。

### 教训笔记（library/lessons/failure_lessons.md）

每次 reject **追加**一节。**节标题必须以 factor_id 开头**（如 `## f001_xxx · 行情价量类 · 2026-07-12`），保证 G-PR-4 能 grep `f001` 这类 ID 标记。

结构：

```markdown
## {factor_id} · {方向} · {日期}

- **失败模式类别**：市值伪 alpha / 行业轮动伪 alpha / OOS 失效 / 换手虚高 / ...
- **因子公式**：...
- **样本内指标**：IC={x} ICIR={y} 多空年化={z}
- **OOS 指标**：IC={x'} 衰减={%}
- **教训要点**：
  1. ...
  2. ...
- **回避建议**：下次若再想做类似方向，应改 ...
```

### G-PR-4 核对协议（机器逐条引用校验）

`tools/check_gates.py` 的 G-PR-4 实现细节：

1. 扫描 `library/lessons/failure_lessons.md` 全文，提取所有 `\bf\d{3}\b` ID
2. 扫描 `library/failures/*.md` 文件名，提取所有 `f\d{3}` ID
3. 合并去重得到失败库 ID 集合 `failure_ids`
4. 扫描 `factor_proposal.md`，提取所有 `\bf\d{3}\b` ID
5. **逐条核对**：`missing_ids = failure_ids - referenced_ids`
6. 若 `missing_ids` 非空 → G-PR-4 FAIL，列出缺失的 ID
7. 若失败库为空（首次运行）→ G-PR-4 自动 PASS（无失败可参考）

**关键含义**：proposer 必须**逐条引用每一条失败条目的 ID**——不是摘要，不是只列 ≥3 条，**必须全覆盖**。这保证 AI 不会因为摘要漏看部分失败模式而重蹈覆辙。

### 关键：append 而非覆盖

`failure_lessons.md` **追加**（append）而非覆盖。覆盖会丢历史教训，让后人重蹈覆辙。`tools/factor_archiver.py reject` 已硬编码 append 行为。

---

## 六、与 WorldQuant / Alphalens 的差异

| 维度 | WorldQuant / Alphalens | 本插件 |
|------|------------------------|--------|
| 输入 | 数据 + 表达式 | **用户方向 + 失败教训**（每轮动态） |
| 产出 | 因子评估报告 | **入库决策**（人工 accept/reject） |
| 沉淀 | 单次报告 | **长期失败库 + 教训笔记**（每次 reject 追加） |
| 反馈环 | 无 | **每轮 propose 必读教训**（防重蹈覆辙） |
| 多重检验 | 平台层控制 | **强制 Bonferroni** |

---

## 七、参考来源（精选）

- WorldQuant. *101 Formulaic Alphas*. (2015).
- Quantopian. *Alphalens: Performance analysis of predictive (alpha) factors*. (2017). github.com/quantopian/alphalens
- Kakushadze, Z. *101 Formulaic Alphas – A formalized specification*. (2016).
- gplearn. github.com/trevorstephens/gplearn
- AlphaGen: Wang et al. *AlphaGen: Reinforcement Learning for Formulaic Alpha Generation*. (2024).
- MASTER: Li et al. *MASTER: Market-Guided Stock Transformer*. (2023).
- Alpha-GPT: Wang et al. *Alpha-GPT: Human-in-the-loop Mining of Alphas*. (2023).
- QuantAgent: Kou et al. *QuantAgent: LLM-based Quant Trading Agent*. (2023).
- WorldQuant Brain. brain.worldquant.com
- AlphaWorks (国内对标)。

---

## 八、已知因子撞库清单（proposer 必查，proposal F-9）

> ⚠️ 本节是**撞库参照表**。proposer 必须**主动声明**：本因子与以下哪些已知因子**最接近**？**关键差异**是什么？如发现本因子就是某个已知因子的直接复刻，**必须驳回重提**（除非有极其强的"为何值得重复尝试"理由，由主会话人工裁决）。

> 主会话与 proposer 都应明白：完全避免"任何已知因子"在工程上不可能（LLM 训练数据覆盖极广），能做的是**主动声明** + **关键差异** + **主会话人工审查**。

### 8.1 WorldQuant 101 Formulaic Alphas（公开 101 个）

完整列表见 `templates/known_factors/alpha101.md`（首版仅列代表性；proposer 必要时可主动搜索完整列表）。

代表（必须主动 grep 完整 101 个）：
- Alpha#1：`rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) - 0.5`
- Alpha#3：`-1 * correlation(rank(open), rank(volume), 10)`
- Alpha#12：`sign(delta(volume, 1)) * (-1 * delta(close, 1))`
- Alpha#18：`-1 * rank(stddev(abs(close - open), 5) + open - close + open - close)`
- Alpha#33：`rank(-1 + open / close)`
- Alpha#41：`power(high * low, 0.5) - vwap`
- Alpha#101：`(close - open) / ((high - low) + 0.001)`

### 8.2 Alphalens 内置示例因子（Quantopian）

| 因子 | 简述 |
|------|------|
| `MeanReversion` | `1 / close.pct_change(N)` |
| `Momentum` | `close.pct_change(N)` |
| `Volume` | `mean(volume, N)` |
| `PriceVolumeTrend` | `(close - close.shift(1)) / close.shift(1) * volume` |

### 8.3 国内经典因子（券商研报 / AlphaWorks 公开）

| 因子 | 简述 | 来源 |
|------|------|------|
| 月度反转 | `-(close / close.shift(21) - 1)` | 经典 |
| 12 个月动量（剔除最近 1 月） | `close / close.shift(252) - 1`，跳过最近 21 日 | Jegadeesh-Titman 1993 |
| 换手率 | `mean(turnover_rate, N)` | Amihud 2002 |
| Amihud 非流动性 | `mean(abs(returns) / turn_value, N)` | Amihud 2002 |
| EP（盈利收益率） | `EPS / price` | 经典估值 |
| BP（市净率倒数） | `book_value / market_cap` | 经典估值 |
| ROE 动量 | `ΔROE_q` | 质量动量 |
| 12-1 动量 | `close.shift(21) / close.shift(252) - 1` | Jegadeesh-Titman |

### 8.4 学术常见异象（Finance Literature）

| 异象 | 引用 |
|------|------|
| 规模 (SMB) | Fama-French 1993 |
| 价值 (HML) | Fama-French 1993 |
| 动量 (UMD/WML) | Carhart 1997 |
| 盈利 (RMW) | Fama-French 2015 |
| 投资 (CMA) | Fama-French 2015 |
| 盈利公告漂移 (PEAD) | Ball-Brown 1968 |
| 应计异象 (Accruals) | Sloan 1996 |
| 净股票发行异象 (NSI) | Loughran-Ritter 1995 |
| 复合发行异象 (Composite Issuance) | Daniel-Titman 2006 |
| 短期反转 | Jegadeesh 1990 |
| 长期反转 | DeBondt-Thaler 1985 |
| 波动率 (BAB) | Frazzini-Israel-Moskowitz 2014 |
| 套利限制 (Betting Against Beta) | Frazzini-Israel-Moskowitz 2014 |
| 质量 (QMJ) | Asness-Frazzini-Israel-Moskowitz 2019 |
| 破产风险 (Distress) | Campbell-Hilscher-Szilagyi 2008 |

### 8.5 LLM 训练数据中常见的因子（基于社区搜索与博客）

> ⚠️ 这一类特别需要警惕——LLM 训练数据中包含大量博客 / 教程 / 论坛讨论的因子，proposer 容易不自觉复刻。

- 量价背离（价涨量缩 vs 价跌量缩）
- 均线偏离度（close / MA(N) - 1）
- 布林带突破（(close - MA) / std）
- ATR 比率（Average True Range / price）
- KDJ / MACD / RSI 等技术指标（**禁止**——纯技术指标在 A 股截面无效）
- 涨停板次日溢价（**典型伪 alpha**）
- 龙虎榜机构净买入

### 8.6 撞库自检协议（proposal F-9 必填）

proposer 在 `factor_proposal.md` 必须包含一节「**已知因子撞库声明**」：

```markdown
## F-9 已知因子撞库声明

**最接近的已知因子**（≥3 个）：
1. WorldQuant Alpha#X：<简述>。**关键差异**：...
2. Alphalens <Name>：<简述>。**关键差异**：...
3. 国内经典 <name>：<简述>。**关键差异**：...
4. 学术异象 <name>（如适用）：<简述>。**关键差异**：...

**创新点**：
- 本因子相对上述已知因子的**根本性不同**在于：...
- 本因子采用了**跨域类比 / 反直觉构造 / 原创组合**，具体为：...

**如果本因子本质就是某个已知因子的变形**：
- 是否仍值得做？给出**极强的理由**（如：从未在 A 股 / 你选的时间段 / 你的数据版本下验证过，且变形带来的差异可能改变 IC 方向）。
- 若理由不充分 → 主会话**驳回**。
```

### 8.7 主会话人工审查要点

即便 proposer 给出 F-9 声明，主会话仍应：

1. **直觉判断**：看到这个因子公式，第一反应是不是"这不就是 XX 吗？"
2. **查检**：对最接近的 ≥3 个已知因子，是否真的有关键差异？
3. **拒绝变形的拒绝**：若只是换窗口 / 加权重，视为雷同。
4. **接受原创**：跨域类比、反直觉构造、新颖组合，值得鼓励。

### 8.8 变更记录

- 0.3.0（2026-07-11）：新增 F-9 已知因子撞库闸门。proposer 必声明最接近的 ≥3 个已知因子 + 关键差异；主会话人工审查创新性。