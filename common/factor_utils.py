"""
common.factor_utils — 因子预处理工具

提供：
- winsorize（去极值：MAD 或 std 法）
- standardize（z-score 标准化）
- neutralize_factor（市值 / 行业中性化，OLS 残差法）
- standardize_factor（winsorize → neutralize → standardize 一站式）
- compute_forward_return（T+1 ~ T+H 收益，扣费可选）
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 去极值
# ---------------------------------------------------------------------------
def winsorize(
    series: pd.Series,
    method: str = "mad",
    n_sigma: float = 3.0,
) -> pd.Series:
    """横截面去极值。

    Args:
        series: 一期截面因子值（按 stock_code index）
        method: 'mad'（默认，median ± n*MAD）或 'std'（mean ± n*std）
        n_sigma: 阈值倍数

    Returns:
        截尾后的 series（原 index 原 NaN 位置）
    """
    s = series.dropna()
    if s.empty:
        return series

    if method == "mad":
        median = s.median()
        mad = (s - median).abs().median() * 1.4826
        lower, upper = median - n_sigma * mad, median + n_sigma * mad
    elif method == "std":
        mean, std = s.mean(), s.std()
        lower, upper = mean - n_sigma * std, mean + n_sigma * std
    else:
        raise ValueError(f"method 必须为 mad/std：{method}")

    return series.clip(lower=lower, upper=upper)


# ---------------------------------------------------------------------------
# 标准化
# ---------------------------------------------------------------------------
def standardize(series: pd.Series) -> pd.Series:
    """z-score 标准化（横截面）。"""
    s = series.dropna()
    if s.empty or s.std() == 0:
        return series * 0.0
    return (series - s.mean()) / s.std()


# ---------------------------------------------------------------------------
# 中性化（OLS 残差法）
# ---------------------------------------------------------------------------
def neutralize_factor(
    factor: pd.Series,
    *,
    market_cap: Optional[pd.Series] = None,
    industry: Optional[pd.Series] = None,
) -> pd.Series:
    """横截面中性化：回归剔除市值 / 行业暴露。

    Args:
        factor: 因子值（indexed by stock_code）
        market_cap: 市值序列（与 factor 同 index）
        industry: 行业标签序列

    Returns:
        中性化后的因子（OLS 残差）
    """
    valid = factor.dropna()
    if valid.empty:
        return factor

    X_parts: list[pd.DataFrame] = []

    if market_cap is not None:
        ln_cap = np.log(market_cap.reindex(valid.index).clip(lower=1))
        X_parts.append(ln_cap.to_frame("ln_cap"))

    if industry is not None:
        ind = industry.reindex(valid.index)
        dummies = pd.get_dummies(ind, drop_first=True, dtype=float)
        X_parts.append(dummies)

    if not X_parts:
        return factor

    X = pd.concat(X_parts, axis=1).reindex(valid.index)
    X.insert(0, "_const", 1.0)

    mask = X.notna().all(axis=1) & valid.notna()
    X_clean, y_clean = X.loc[mask], valid.loc[mask]

    if X_clean.shape[0] <= X_clean.shape[1]:
        return factor

    try:
        beta = np.linalg.lstsq(X_clean.values, y_clean.values, rcond=None)[0]
        residual = y_clean - X_clean.values @ beta
    except np.linalg.LinAlgError:
        return factor

    return residual.reindex(factor.index)


# ---------------------------------------------------------------------------
# 一站式：winsorize → neutralize → standardize
# ---------------------------------------------------------------------------
def standardize_factor(
    factor_df: pd.DataFrame,
    factor_col: str = "factor",
    date_col: str = "date",
    market_cap_col: Optional[str] = "market_value",
    industry_col: Optional[str] = None,
    winsorize_method: str = "mad",
) -> pd.DataFrame:
    """按截面（每个 date）走 winsorize → neutralize → z-score 流水线。

    Args:
        factor_df: 面板数据 [stock_code, date, factor, market_value?, industry?]
        factor_col: 因子列名
        date_col: 日期列名
        market_cap_col: 市值列名（None = 不做市值中性化）
        industry_col: 行业列名（None = 不做行业中性化）
        winsorize_method: 'mad' / 'std'

    Returns:
        原 DataFrame + 新列 `factor_std`（标准化后因子）
    """
    result_parts: list[pd.DataFrame] = []

    for dt, grp in factor_df.groupby(date_col):
        f = grp[factor_col].copy()
        # Step 1: winsorize
        f = winsorize(f, method=winsorize_method)
        # Step 2: neutralize
        mc = grp[market_cap_col] if market_cap_col and market_cap_col in grp.columns else None
        ind = grp[industry_col] if industry_col and industry_col in grp.columns else None
        f = neutralize_factor(f, market_cap=mc, industry=ind)
        # Step 3: z-score
        f = standardize(f)
        result_parts.append(grp.assign(factor_std=f))

    return pd.concat(result_parts, ignore_index=True) if result_parts else factor_df.assign(factor_std=np.nan)


# ---------------------------------------------------------------------------
# 前瞻收益（T+1 ~ T+H）
# ---------------------------------------------------------------------------
def compute_forward_return(
    panel: pd.DataFrame,
    h: int = 21,
    return_col: str = "close",
    date_col: str = "date",
    stock_col: str = "stock_code",
) -> pd.Series:
    """计算每只股票在每期的 forward return（T+1 ~ T+h 的累计收益）。

    关键：信号 T 日算出，T+1 执行；这里 forward_return 从 T+1 起算（不含 T 日）。

    Args:
        panel: 含 close 列的面板
        h: 持有期（交易日数，默认 21 ≈ 1 个月）
        return_col: 价格列名
        date_col: 日期列名
        stock_col: 股票代码列名

    Returns:
        pd.Series：与 panel 同 index 的 forward_return
    """
    panel = panel.sort_values([stock_col, date_col]).reset_index(drop=True)
    future = panel.groupby(stock_col)[return_col].shift(-1)  # T+1
    future_h = panel.groupby(stock_col)[return_col].shift(-h)  # T+h
    fwd = (future_h - future) / future
    fwd.index = panel.index
    return fwd.rename("forward_return")


# ---------------------------------------------------------------------------
# 横截面分位
# ---------------------------------------------------------------------------
def cross_section_rank(
    panel: pd.DataFrame,
    factor_col: str = "factor",
    date_col: str = "date",
    pct: bool = True,
) -> pd.Series:
    """按日期横截面排序，返回排名（或分位数）。"""
    return panel.groupby(date_col)[factor_col].rank(method="first", pct=pct)