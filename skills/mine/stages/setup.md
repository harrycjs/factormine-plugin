# setup 阶段执行卡（首次使用配置向导，幂等可重跑）

> **目标**：交互式收集 4 项全局配置（数据路径 / 股票池 / 年份区间 / 默认因子方向），落地 `.mine.json` + 目录树 + 数据可用性自检。后续所有 `/mine new` 默认继承这些配置。

## 触发

- 形态 A（本仓库直跑）：用户显式调 `/mine setup` 或形态 B 下首次 `/mine new` 自动跳入。
- 形态 B（插件安装在用户目录）：**首次 `/mine new` 前**若 cwd 无 `.mine.json`，自动跳入。

## 第一批：AskUserQuestion（4 项）

```python
AskUserQuestion(questions=[
    {
        "question": "本地数据根目录（必含 share_stock_*.parquet 或 ashare_stock_*.parquet 类股票数据）",
        "header": "数据路径",
        "options": [
            {"label": "D:\\local_data (默认)", "description": "标准路径，与 ghquant_plugin-main 兼容"},
            {"label": "~/local_data", "description": "Linux/Mac 风格，默认回退"},
        ],
    },
    {
        "question": "股票池范围（影响因子普适性评估）",
        "header": "股票池",
        "options": [
            {"label": "全 A 股（剔 ST/停牌/上市<60日）", "description": "最贴近实盘，推荐"},
            {"label": "沪深 300", "description": "大盘股池"},
            {"label": "中证 500/1000", "description": "中小盘，alpha 机会多但流动性弱"},
        ],
        "multi_select": False,
    },
    {
        "question": "因子挖掘覆盖的年份区间（用于 IC 计算、回测、OOS 留 20%）",
        "header": "年份区间",
        "options": [
            {"label": "近 10 年 (2016-2025)", "description": "覆盖牛熊周期 + 一轮完整信用周期"},
            {"label": "近 5 年 (2021-2025)", "description": "近期市场风格贴近当前，但样本偏短"},
            {"label": "全历史 (2010-2025)", "description": "样本最完整，对财务因子尤为合适"},
        ],
        "multi_select": False,
    },
    {
        "question": "默认因子方向（每轮 /mine new 可随时覆盖）",
        "header": "默认方向",
        "options": [
            {"label": "行情价量类", "description": "动量/反转/换手/波动/资金流"},
            {"label": "财务基本面类", "description": "估值/盈利/质量/成长，需财务 parquet"},
            {"label": "让 Claude 自行探寻", "description": "混合 + 新颖 alpha，每轮由失败教训驱动"},
        ],
        "multi_select": False,
    },
])
```

## 落地（一次 Bash 调用，`&&` 串联全部记账）

```bash
uv run python tools/setup_workspace.py \
  --target . \
  --data-root "<用户答>" \
  --pool "<全A|HS300|ZZ500|ZZ1000>" \
  --year-start <start> \
  --year-end <end> \
  --default-direction "<行情|财务|混合>" \
  && uv run python tools/check_gates.py --stage setup --record  # 首次也走门禁
```

`setup_workspace.py` 职责：
- 落地 `.mine.json`
- 拷贝 `templates/` 到 cwd（用户可改）
- 拷贝 `common/` 种子
- 创建 `pyproject.toml`（若缺）
- 创建目录树 `library/{approved,rejected,failures,lessons}/` + `workspace/`
- **数据可用性自检**：扫 `--data-root`，列出 parquet 文件清单，更新 `templates/data_catalog.md` 草稿（用户后续维护）

## 输出合同

- `.mine.json`（全局配置）
- `templates/data_catalog.md`（草稿 + 自动列出的本地 parquet）
- `library/{approved,rejected,failures,lessons}/` 全在
- `workspace/` 在

## 出口门禁 G-SU

| 编号 | 检查 |
|------|------|
| G-SU-1 | `.mine.json` 存在且字段齐 |
| G-SU-2 | `templates/data_catalog.md` 存在 |
| G-SU-3 | `library/lessons/failure_lessons.md` 在（首次创建空骨架） |
| G-SU-4 | 数据根目录下至少 1 个 ashare_stock_*.parquet 或 share_stock_*.parquet 存在 |

## 失败处理

G-SU-4 FAIL：提示用户数据路径选错，**回退到 AskUserQuestion 重选数据路径**，不允许强行继续。