"""
common.data_loader — 本地 parquet 加载（兼容 share_stock_* 与 ashare_stock_* 双前缀）

设计要点：
- 自动识别 .mine.json 的 data_root；找不到时回退到 ~/local_data
- 文件名双前缀兼容：通过 _resolve() 优先 ashare_stock_*，回退到 share_stock_*
- 纯加载层：不调任何衍生计算（衍生在 factor.py）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Sequence

import pandas as pd


# ---------------------------------------------------------------------------
# 数据根目录解析
# ---------------------------------------------------------------------------
def get_data_root() -> Path:
    """解析本地数据根目录。
    优先级：cwd .mine.json → cwd .reproduce.json（与 ghquant_plugin 兼容） → ~/local_data
    """
    for directory in [Path.cwd(), *Path.cwd().parents]:
        for cfg_name in (".mine.json", ".reproduce.json"):
            cfg = directory / cfg_name
            if cfg.is_file():
                try:
                    data_root = json.loads(cfg.read_text(encoding="utf-8")).get("data_root")
                    if data_root:
                        return Path(data_root).expanduser()
                except (json.JSONDecodeError, OSError):
                    continue
    return Path.home() / "local_data"


LOCAL_DATA_DIR = get_data_root()


# ---------------------------------------------------------------------------
# 文件名双前缀兼容
# ---------------------------------------------------------------------------
def _resolve(prefix_options: Sequence[str], data_dir: Path = LOCAL_DATA_DIR) -> Path:
    """按顺序找第一个存在的 parquet 文件路径。"""
    for prefix in prefix_options:
        p = data_dir / f"{prefix}.parquet"
        if p.is_file():
            return p
    raise FileNotFoundError(
        f"数据目录 {data_dir} 下未找到 {prefix_options} 任一文件"
    )


# ---------------------------------------------------------------------------
# 核心加载器
# ---------------------------------------------------------------------------
def load_stock_price(
    data_dir: Path = LOCAL_DATA_DIR,
    columns: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """加载日行情数据（未复权）。

    返回列：[stock_code, date, prev_close, close, open, high, low, vwap, ...]
    """
    path = _resolve(["ashare_stock_price", "share_stock_price"], data_dir)
    df = pd.read_parquet(path, columns=columns)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_stock_price_forward(
    data_dir: Path = LOCAL_DATA_DIR,
    columns: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """加载前复权日行情（回测算收益优先用）。"""
    path = _resolve(["ashare_stock_price_forward", "share_stock_price_forward"], data_dir)
    df = pd.read_parquet(path, columns=columns)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_stock_trade(
    data_dir: Path = LOCAL_DATA_DIR,
    columns: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """加载日交易数据：涨跌幅、成交、换手、市值。

    返回列：[stock_code, date, change_pct, range_pct, market_value,
             negotiable_market_value, turnover_rate, turnover_rate_free,
             volume, turn_value, ...]
    """
    path = _resolve(["ashare_stock_trade", "share_stock_trade"], data_dir)
    df = pd.read_parquet(path, columns=columns)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_suspend(data_dir: Path = LOCAL_DATA_DIR) -> pd.DataFrame:
    """加载停牌标记。"""
    path = _resolve(["ashare_stock_suspend", "share_stock_suspend"], data_dir)
    df = pd.read_parquet(path, columns=["stock_code", "date", "if_suspend"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_st_data(data_dir: Path = LOCAL_DATA_DIR) -> pd.DataFrame:
    """加载 ST 区间记录。"""
    path = _resolve(["ashare_stock_st", "share_stock_st"], data_dir)
    df = pd.read_parquet(path, columns=["stock_code", "implement_date", "remove_date"])
    df["implement_date"] = pd.to_datetime(df["implement_date"])
    df["remove_date"] = pd.to_datetime(df["remove_date"])
    return df


def load_industry(
    data_dir: Path = LOCAL_DATA_DIR,
    standard_code: int = 37,
) -> pd.DataFrame:
    """加载行业分类（默认 CITICS 一级，standard_code=37；申万一级 38）。"""
    path = _resolve(["ashare_stock_industry", "share_stock_industry"], data_dir)
    df = pd.read_parquet(path)
    df = df.loc[df["standard_code"] == standard_code, ["stock_code", "first_industry_name"]]
    return df.drop_duplicates(subset=["stock_code"]).reset_index(drop=True)


def load_limit(data_dir: Path = LOCAL_DATA_DIR) -> pd.DataFrame:
    """加载涨跌停标记。"""
    path = _resolve(["ashare_stock_limit", "share_stock_limit"], data_dir)
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_trade_calendar(
    data_dir: Path = LOCAL_DATA_DIR,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """加载交易日历。"""
    path = _resolve(["ashare_tradeday", "share_tradeday"], data_dir)
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["IfTradingDay"] == 1]
    if start_date:
        df = df[df["date"] >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df["date"] <= pd.Timestamp(end_date)]
    return df.sort_values("date").reset_index(drop=True)


def load_stock_basic(data_dir: Path = LOCAL_DATA_DIR) -> pd.DataFrame:
    """加载个股基础信息（上市日期、上市状态）。"""
    path = _resolve(["ashare_stock", "share_stock"], data_dir)
    return pd.read_parquet(path)


def load_balance(data_dir: Path = LOCAL_DATA_DIR) -> pd.DataFrame:
    """加载资产负债表（含 info_publ_date / end_date）。"""
    path = _resolve(["ashare_stock_balance", "share_stock_balance"], data_dir)
    return pd.read_parquet(path)


def load_income(data_dir: Path = LOCAL_DATA_DIR) -> pd.DataFrame:
    """加载利润表（含 info_publ_date / end_date）。"""
    path = _resolve(["ashare_stock_income", "share_stock_income"], data_dir)
    return pd.read_parquet(path)


def load_cashflow(data_dir: Path = LOCAL_DATA_DIR) -> pd.DataFrame:
    """加载现金流量表（含 info_publ_date / end_date）。"""
    path = _resolve(["ashare_stock_cashflow", "share_stock_cashflow"], data_dir)
    return pd.read_parquet(path)


# ---------------------------------------------------------------------------
# 辅助：调仓日 / 股票池
# ---------------------------------------------------------------------------
def get_month_end_trading_days(
    start_date: str,
    end_date: str,
    data_dir: Path = LOCAL_DATA_DIR,
) -> pd.DatetimeIndex:
    """[start, end] 区间内的月末交易日。"""
    cal = load_trade_calendar(data_dir, start_date, end_date)
    month_ends = cal[cal["IfMonthEnd"] == 1]["date"]
    return pd.DatetimeIndex(month_ends.values)


def filter_st_stocks(
    stock_codes: pd.Index,
    date: pd.Timestamp,
    st_data: pd.DataFrame,
) -> pd.Index:
    """剔除 ST 状态的股票。"""
    st_on_date = st_data[
        (st_data["implement_date"] <= date)
        & ((st_data["remove_date"] > date) | st_data["remove_date"].isna())
    ]["stock_code"].unique()
    return stock_codes.difference(pd.Index(st_on_date))


def filter_suspended(
    panel: pd.DataFrame,
    suspend_data: pd.DataFrame,
    stock_col: str = "stock_code",
    date_col: str = "date",
) -> pd.DataFrame:
    """剔除停牌日记录。"""
    merged = panel.merge(
        suspend_data[[stock_col, date_col, "if_suspend"]],
        on=[stock_col, date_col],
        how="left",
    )
    return merged[merged["if_suspend"] != 1].drop(columns=["if_suspend"])


def filter_limit(panel: pd.DataFrame, limit_data: pd.DataFrame) -> pd.DataFrame:
    """剔除涨停 / 跌停日记录（防流动性失效）。"""
    keys = ["stock_code", "date"]
    merged = panel.merge(
        limit_data[keys + ["surged_limit", "decline_limit"]],
        on=keys,
        how="left",
    )
    mask = (merged["surged_limit"] != 1) & (merged["decline_limit"] != 1)
    return merged.loc[mask].drop(columns=["surged_limit", "decline_limit"])


# ---------------------------------------------------------------------------
# 一站式：构建回测面板（调仓日 × 全市场股票，含 ST/停牌/涨跌停 过滤）
# ---------------------------------------------------------------------------
def build_panel(
    start_date: str,
    end_date: str,
    data_dir: Path = LOCAL_DATA_DIR,
    *,
    pool: str = "全A",
    freq: str = "monthly",
) -> pd.DataFrame:
    """构建回测面板：调仓日 + 股票池 + 过滤。

    Args:
        start_date: 起始日期（含）
        end_date: 结束日期（含）
        pool: "全A" / "HS300" / "ZZ500" / "ZZ1000"
        freq: "monthly" / "weekly"

    Returns:
        DataFrame[stock_code, date, ...]，按 [stock_code, date] 排序。
    """
    # 调仓日
    if freq == "monthly":
        dates = get_month_end_trading_days(start_date, end_date, data_dir)
    elif freq == "weekly":
        cal = load_trade_calendar(data_dir, start_date, end_date)
        dates = cal[cal["IfWeekEnd"] == 1]["date"]
        dates = pd.DatetimeIndex(dates.values)
    else:
        raise ValueError(f"freq 必须为 monthly/weekly：{freq}")

    # 价格（用前复权）
    price = load_stock_price_forward(
        data_dir,
        columns=["stock_code", "date", "prev_close", "close", "open", "high", "low", "vwap"],
    )
    trade = load_stock_trade(
        data_dir,
        columns=[
            "stock_code", "date", "change_pct", "range_pct",
            "market_value", "negotiable_market_value", "turnover_rate",
            "volume", "turn_value",
        ],
    )

    # 多看 400 日 lookback（算滚动因子用）
    buffer = pd.Timestamp(start_date) - pd.DateOffset(days=400)
    price = price[(price["date"] >= buffer) & (price["date"] <= pd.Timestamp(end_date))]
    trade = trade[(trade["date"] >= buffer) & (trade["date"] <= pd.Timestamp(end_date))]

    panel = price.merge(trade, on=["stock_code", "date"], how="inner")
    panel = panel.sort_values(["stock_code", "date"]).reset_index(drop=True)

    # 过滤 ST / 停牌 / 涨跌停（仅对调仓日过滤——非调仓日用来算滚动因子）
    st_data = load_st_data(data_dir)
    suspend = load_suspend(data_dir)
    limit = load_limit(data_dir)

    # 提取调仓日
    is_rebalance = panel["date"].isin(dates)
    rebalance_panel = panel[is_rebalance].copy()

    # 剔除 ST
    rebalance_panel = rebalance_panel[
        rebalance_panel.apply(
            lambda r: r["stock_code"] not in filter_st_stocks(
                pd.Index([r["stock_code"]]), r["date"], st_data
            ),
            axis=1,
        )
    ]
    # 剔除停牌
    rebalance_panel = filter_suspended(rebalance_panel, suspend)
    # 剔除涨跌停
    rebalance_panel = filter_limit(rebalance_panel, limit)

    # 上市不足 60 日剔除
    basic = load_stock_basic(data_dir)
    if "list_date" in basic.columns:
        rebalance_panel = rebalance_panel.merge(
            basic[["stock_code", "list_date"]],
            on="stock_code",
            how="left",
        )
        rebalance_panel = rebalance_panel[
            (rebalance_panel["date"] - rebalance_panel["list_date"]).dt.days >= 60
        ].drop(columns=["list_date"])

    # 股票池（仅全 A 暂时实现，其他留接口）
    if pool != "全A":
        # TODO: 沪深 300 / 中证 500 / 1000 成分股过滤
        pass

    return rebalance_panel.sort_values(["stock_code", "date"]).reset_index(drop=True)