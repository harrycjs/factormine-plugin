# 本地数据目录（data_catalog）

> 供 `factor-proposer` / `factor-evaluator` 判定数据可用性。`factor-proposer` 在 propose 阶段必须按本表标注每个数据字段的 status（available / derive / missing），不允许伪造可计算。
>
> 数据根目录：由 `.mine.json` 的 `data_root` 字段指定（setup 时用户填入），全部为 **parquet** 格式。
>
> 加载方式：`pd.read_parquet("<data_root>/<file>.parquet", columns=[...])`。
>
> 通用约定：日期列多为 `date`；`JSID` 为数据源内部 ID 可忽略；股票代码列为 `stock_code`（6 位字符串，如 `"600000"`）。

---

## 如何标注 data_requirement 的 status

- `available`：下表直接有对应文件与字段 → 可直接加载。
- `derive`：本地有原料但需衍生计算（如：日收益率由 `change_pct` 或 `close/prev_close-1` 得到；月频由日频重采样；行业市值中性化所需暴露由现有字段构造）。
- `missing`：下表无对应数据，且无法由现有数据衍生（如：分钟/tick 级数据、龙虎榜个股明细外的另类数据、Wind/朝阳永续特有指标、舆情/文本/卫星等另类数据）。

> ⚠️ **用户描述里的 `share_stock_xxxxxx.parquet` 是文件名前缀风格，本插件统一兼容 `share_stock_*` 与 `ashare_stock_*` 两种命名**（通过 `common/data_loader.py` 自动判定）。

---

## A 股 · 个股行情与交易

| 文件名（推荐） | 别名兼容 | 关键字段 | 覆盖 | 用途 |
|------|------|---------|------|------|
| `ashare_stock_price.parquet` | `share_stock_price.parquet` | stock_code, date, prev_close, open, high, low, close, vwap | 2000-01 ~ 至今(日) | 未复权日行情 |
| `ashare_stock_price_forward.parquet` | `share_stock_price_forward.parquet` | + adj_factor | 2000-01 ~ 至今(日) | **前复权**日行情（回测算收益优先用） |
| `ashare_stock_trade.parquet` | `share_stock_trade.parquet` | volume, market_value, negotiable_market_value, turn_value, turnover_rate, turnover_rate_free, change_pct, range_pct | 2000-01 ~ 至今(日) | 日涨跌幅、成交、换手、总/流通市值 |

## A 股 · 状态过滤

| 文件 | 关键字段 | 用途 |
|------|---------|------|
| `ashare_stock_st.parquet` / `share_stock_st.parquet` | stock_code, implement_date, remove_date | ST 区间（剔除 ST） |
| `ashare_stock_suspend.parquet` / `share_stock_suspend.parquet` | stock_code, date, if_suspend | 停牌（剔除停牌日） |
| `ashare_stock_limit.parquet` / `share_stock_limit.parquet` | stock_code, date, stock_board, limit_board, surged_limit, decline_limit, change_pct | 涨跌停标记 |
| `ashare_stock_industry.parquet` / `share_stock_industry.parquet` | stock_code, first/second/third_industry_name, standard_code | 行业分类（中性化用）。`standard_code=37` 中信一级，`38` 申万一级 |
| `ashare_tradeday.parquet` / `share_tradeday.parquet` | date, IfTradingDay, IfWeekEnd, IfMonthEnd, IfQuarterEnd, IfYearEnd | 交易日历 |

> 用财务数据务必用 `info_publ_date`（披露日）做时点对齐，**防未来函数**。

## A 股 · 财务报表（季频/年频，字段数百，按需取列）

| 文件 | 内容 | 关键定位字段 |
|------|------|------|
| `ashare_stock_balance.parquet` / `share_stock_balance.parquet` | 资产负债表 | stock_code, end_date, info_publ_date |
| `ashare_stock_income.parquet` / `share_stock_income.parquet` | 利润表 | stock_code, end_date, info_publ_date |
| `ashare_stock_income_q.parquet` | 利润表单季 | stock_code, end_date, mark |
| `ashare_stock_cashflow.parquet` / `share_stock_cashflow.parquet` | 现金流量表 | stock_code, end_date, info_publ_date |
| `ashare_stock_cashflow_q.parquet` | 现金流单季 | stock_code, end_date, mark |

## A 股 · 个股基础信息

| 文件 | 关键字段 | 用途 |
|------|---------|------|
| `ashare_stock.parquet` / `share_stock.parquet` | stock_code, stock_name, list_date, list_state | 上市日期、上市状态（剔除新股/退市） |

## 指数

| 文件 | 关键字段 | 用途 |
|------|---------|------|
| `ashare_index_components.parquet` | stock_code, in_date, out_date, index_code | 指数成分股（沪深300=`000300` 等），构造股票池 |
| `ashare_index_value.parquet` | index_code, date, pe_ttm, pb_lf, ps_ttm | 指数估值（择时可用） |

## 常见数据缺口（直接判 missing，触发异常停止）

- 分钟 / tick / 高频订单簿数据 → 无（本地最细为日频）。
- 个股逐笔、Level-2、资金流向明细 → 无。
- 舆情 / 研报文本 / 分析师预期（朝阳永续）/ 卫星 / 另类数据 → 无。
- 海外个股财务、ESG 明细 → 无。

---

## 用户首次使用后需补全

`/mine setup` 会在用户填写 `data_root` 后自动扫描 parquet 文件清单，**填入本节 "本机实际文件清单"**：

```
（本节由 setup_workspace.py 自动填入）
```