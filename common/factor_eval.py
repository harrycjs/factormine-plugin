"""
common.factor_eval — 因子评估全套

提供：
- calculate_ic / calculate_rank_ic（截面 IC）
- calculate_ic_series / ic_summary（IC 时序 + 汇总）
- assign_quantile_groups（截面分箱）
- quantile_backtest（分组回测：每组等权收益 + 多空）
- long_short_backtest（多空组合：年化、夏普、最大回撤、Calmar、胜率）
- performance_summary（综合指标）
- factor_evaluation_pipeline（一站式：IC + 分组 + 多空 + 换手 + OOS + 5 张图 + Excel）
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from scipy import stats

from common.factor_utils import (
    standardize_factor,
    compute_forward_return,
)

# 配色（与 ghquant_plugin 一致）
BLUE = "#1f77b4"
RED = "#d62728"
CMAP = "RdBu_r"

import seaborn as sns
sns.set_style("whitegrid")

# 中文
plt.rcParams["font.sans-serif"] = ["Songti SC", "Heiti TC", "STHeiti", "Kaiti SC", "PingFang HK", "SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.family"] = "sans-serif"


# ---------------------------------------------------------------------------
# IC 计算
# ---------------------------------------------------------------------------
def calculate_ic(factor: pd.Series, forward_return: pd.Series) -> float:
    """Pearson IC。"""
    valid = pd.DataFrame({"f": factor, "r": forward_return}).dropna()
    if valid.shape[0] < 5:
        return np.nan
    return float(valid["f"].corr(valid["r"]))


def calculate_rank_ic(factor: pd.Series, forward_return: pd.Series) -> float:
    """Spearman RankIC。"""
    valid = pd.DataFrame({"f": factor, "r": forward_return}).dropna()
    if valid.shape[0] < 5:
        return np.nan
    corr, _ = stats.spearmanr(valid["f"], valid["r"])
    return float(corr)


def calculate_ic_series(
    factor_panel: pd.DataFrame,
    factor_col: str = "factor",
    return_col: str = "forward_return",
    date_col: str = "date",
    method: str = "rank",
) -> pd.DataFrame:
    """逐期计算 IC，返回时序 DataFrame[date, ic]。"""
    ic_func = calculate_rank_ic if method == "rank" else calculate_ic
    ic_records = (
        factor_panel
        .groupby(date_col)
        .apply(lambda g: ic_func(g[factor_col], g[return_col]), include_groups=False)
        .rename("ic")
        .reset_index()
    )
    return ic_records


def ic_summary(ic_series: pd.Series, periods_per_year: int = 12) -> dict:
    """IC 时序汇总：均值 / 标准差 / ICIR / 胜率 / t 统计量。"""
    ic = ic_series.dropna()
    ic_mean = ic.mean()
    ic_std = ic.std()
    icir = ic_mean / ic_std * np.sqrt(periods_per_year) if ic_std > 0 else 0.0
    win_rate = (ic > 0).sum() / len(ic) if len(ic) > 0 else 0.0
    t_val = ic_mean / (ic_std / np.sqrt(len(ic))) if ic_std > 0 and len(ic) > 0 else 0.0
    return {
        "ic_mean": float(ic_mean),
        "ic_std": float(ic_std),
        "icir": float(icir),
        "win_rate": float(win_rate),
        "t_stat": float(t_val),
        "n_periods": len(ic),
    }


# ---------------------------------------------------------------------------
# 分组回测
# ---------------------------------------------------------------------------
def assign_quantile_groups(
    factor_panel: pd.DataFrame,
    factor_col: str = "factor",
    date_col: str = "date",
    n_groups: int = 5,
    group_col: str = "group",
) -> pd.DataFrame:
    """按因子截面排序分组：G1 = 最低，G{n} = 最高。"""
    def _assign(g: pd.DataFrame) -> pd.Series:
        valid = g[factor_col].dropna()
        if valid.empty:
            return pd.Series(np.nan, index=g.index, name=group_col)
        labels = pd.qcut(valid.rank(method="first"), n_groups, labels=False) + 1
        return labels.reindex(g.index)

    factor_panel = factor_panel.copy()
    factor_panel[group_col] = (
        factor_panel.groupby(date_col, group_keys=False).apply(_assign)
    )
    return factor_panel


def quantile_backtest(
    factor_panel: pd.DataFrame,
    factor_col: str = "factor",
    return_col: str = "forward_return",
    date_col: str = "date",
    n_groups: int = 5,
    transaction_cost: float = 0.003,
) -> dict:
    """分组回测：每组等权收益 + 多空（top - bottom），扣费后。"""
    panel = assign_quantile_groups(factor_panel, factor_col, date_col, n_groups)

    group_returns = (
        panel.dropna(subset=[return_col, "group"])
        .groupby([date_col, "group"])[return_col]
        .mean()
        .unstack("group")
        .sort_index()
    )
    group_returns.columns = [f"G{int(c)}" for c in group_returns.columns]

    top_col, bot_col = f"G{n_groups}", "G1"
    group_returns["long_short"] = group_returns[top_col] - group_returns[bot_col]

    # 换手估计
    group_members = (
        panel.dropna(subset=["group"])
        .groupby([date_col, "group"])
        .apply(lambda g: set(g["stock_code"].values) if "stock_code" in g.columns else set(), include_groups=False)
        .unstack("group")
    )

    turnover_dict: dict[str, list[float]] = {}
    for g_col in group_returns.columns:
        if g_col == "long_short":
            continue
        g_idx = int(g_col[1:])
        if g_idx in group_members.columns:
            members_series = group_members[g_idx].dropna()
            turnovers = []
            for i in range(1, len(members_series)):
                prev, curr = members_series.iloc[i - 1], members_series.iloc[i]
                if prev and curr:
                    overlap = len(prev & curr)
                    total = max(len(prev), len(curr))
                    turnovers.append(1 - overlap / total if total > 0 else 0)
                else:
                    turnovers.append(0)
            turnover_dict[g_col] = turnovers

    # 扣费
    group_returns_net = group_returns.copy()
    for g_col, tvs in turnover_dict.items():
        avg_turnover = np.mean(tvs) if tvs else 0.0
        group_returns_net[g_col] = group_returns[g_col] - transaction_cost * avg_turnover
    group_returns_net["long_short"] = group_returns_net[top_col] - group_returns_net[bot_col]

    group_nav = (1 + group_returns_net).cumprod()

    return {
        "group_returns": group_returns,
        "group_returns_net": group_returns_net,
        "group_nav": group_nav,
        "turnover": turnover_dict,
        "panel": panel,
        "n_groups": n_groups,
    }


# ---------------------------------------------------------------------------
# 多空组合
# ---------------------------------------------------------------------------
def long_short_backtest(
    factor_panel: pd.DataFrame,
    factor_col: str = "factor",
    return_col: str = "forward_return",
    date_col: str = "date",
    n_groups: int = 5,
    transaction_cost: float = 0.003,
    periods_per_year: int = 12,
) -> dict:
    """多空回测：long top，short bottom。"""
    qbt = quantile_backtest(factor_panel, factor_col, return_col, date_col, n_groups, transaction_cost)
    ls_returns = qbt["group_returns_net"]["long_short"]
    ls_nav = (1 + ls_returns).cumprod()
    ls_perf = performance_summary(ls_returns, periods_per_year, name="long_short")
    top_returns = qbt["group_returns_net"][f"G{n_groups}"]
    top_perf = performance_summary(top_returns, periods_per_year, name="top_group")

    return {
        "ls_returns": ls_returns,
        "ls_nav": ls_nav,
        "ls_performance": ls_perf,
        "top_returns": top_returns,
        "top_performance": top_perf,
        "quantile_result": qbt,
    }


# ---------------------------------------------------------------------------
# 性能指标
# ---------------------------------------------------------------------------
def calculate_sharpe(returns: pd.Series, rf: float = 0.0, periods_per_year: int = 12) -> float:
    excess = returns - rf
    if excess.std() == 0:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(periods_per_year))


def calculate_annualized_return(returns: pd.Series, periods_per_year: int = 12) -> float:
    cum = (1 + returns).prod()
    n_years = len(returns) / periods_per_year
    if n_years <= 0:
        return 0.0
    return float(cum ** (1 / n_years) - 1)


def calculate_max_drawdown(nav: pd.Series) -> float:
    running_max = nav.cummax()
    drawdown = (nav - running_max) / running_max
    return float(-drawdown.min()) if len(drawdown) > 0 else 0.0


def calculate_win_rate(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    return float((returns > 0).sum() / len(returns))


def calculate_calmar(returns: pd.Series, periods_per_year: int = 12) -> float:
    ann_ret = calculate_annualized_return(returns, periods_per_year)
    nav = (1 + returns).cumprod()
    mdd = calculate_max_drawdown(nav)
    return float(ann_ret / mdd) if mdd > 0 else 0.0


def performance_summary(returns: pd.Series, periods_per_year: int = 12, name: str = "") -> dict:
    nav = (1 + returns).cumprod()
    return {
        "name": name,
        "ann_return": calculate_annualized_return(returns, periods_per_year),
        "ann_volatility": float(returns.std() * np.sqrt(periods_per_year)),
        "sharpe": calculate_sharpe(returns, periods_per_year=periods_per_year),
        "max_drawdown": calculate_max_drawdown(nav),
        "win_rate": calculate_win_rate(returns),
        "calmar": calculate_calmar(returns, periods_per_year),
        "cumulative_return": float(nav.iloc[-1] - 1) if len(nav) > 0 else 0.0,
        "n_periods": len(returns),
    }


# ---------------------------------------------------------------------------
# 一站式评估流水线（factor-evaluator 调这个）
# ---------------------------------------------------------------------------
def factor_evaluation_pipeline(
    panel: pd.DataFrame,
    factor_col: str = "factor",
    return_col: str = "forward_return",
    date_col: str = "date",
    n_groups: int = 5,
    transaction_cost: float = 0.003,
    output_dir: Optional[Path] = None,
    report_name: str = "factor",
    periods_per_year: int = 12,
    oos_fraction: float = 0.20,
) -> dict:
    """一站式：IC + 分组 + 多空 + 换手 + OOS + 5 张图 + Excel + metrics.json + evaluate_result.json。

    Args:
        panel: 面板 [stock_code, date, factor, forward_return, ...]
        factor_col: 因子列名（默认 'factor_std'，可改）
        return_col: 前瞻收益列名
        date_col: 日期列名
        output_dir: 输出目录（若提供则写图 + Excel + JSON）
        report_name: 报告名（影响图标题与文件名）
        periods_per_year: 12 (monthly) / 52 (weekly) / 252 (daily)
        oos_fraction: OOS 占比（默认 20%）

    Returns:
        dict 含 ic_stats / ls_perf / oos_comparison / metrics.json 路径 / verdict
    """
    panel = panel.dropna(subset=[factor_col, return_col]).copy()

    # === IC ===
    ic_df = calculate_ic_series(panel, factor_col, return_col, date_col, method="rank")
    ic_stats = ic_summary(ic_df["ic"], periods_per_year)

    # === 分组回测 ===
    ls_result = long_short_backtest(panel, factor_col, return_col, date_col, n_groups, transaction_cost, periods_per_year)
    qbt = ls_result["quantile_result"]
    group_returns_net = qbt["group_returns_net"]
    group_nav = qbt["group_nav"]

    # 各组性能
    group_perf_records = []
    for col in group_returns_net.columns:
        perf = performance_summary(group_returns_net[col], periods_per_year, name=col)
        if col in qbt["turnover"]:
            perf["avg_turnover"] = float(np.mean(qbt["turnover"][col]))
        else:
            perf["avg_turnover"] = np.nan
        group_perf_records.append(perf)
    group_perf_df = pd.DataFrame(group_perf_records).set_index("name")

    # === OOS ===
    unique_dates = panel[date_col].sort_values().unique()
    n_total = len(unique_dates)
    n_oos = max(int(n_total * oos_fraction), 24)
    oos_start = unique_dates[-n_oos]

    panel_in = panel[panel[date_col] < oos_start].copy()
    panel_oos = panel[panel[date_col] >= oos_start].copy()

    in_ic = calculate_ic_series(panel_in, factor_col, return_col, date_col, "rank")
    oos_ic = calculate_ic_series(panel_oos, factor_col, return_col, date_col, "rank")
    in_stats = ic_summary(in_ic["ic"], periods_per_year)
    oos_stats = ic_summary(oos_ic["ic"], periods_per_year)

    in_ls = long_short_backtest(panel_in, factor_col, return_col, date_col, n_groups, transaction_cost, periods_per_year)
    oos_ls = long_short_backtest(panel_oos, factor_col, return_col, date_col, n_groups, transaction_cost, periods_per_year)

    oos_decay_ratio = (
        abs(oos_stats["ic_mean"]) / abs(in_stats["ic_mean"])
        if in_stats["ic_mean"] != 0 else 0.0
    )

    oos_comparison = {
        "in_sample": {
            "rank_ic_mean": in_stats["ic_mean"],
            "icir": in_stats["icir"],
            "ls_annual_return": in_ls["ls_performance"]["ann_return"],
            "ls_sharpe": in_ls["ls_performance"]["sharpe"],
            "n_periods": in_stats["n_periods"],
        },
        "oos": {
            "rank_ic_mean": oos_stats["ic_mean"],
            "icir": oos_stats["icir"],
            "ls_annual_return": oos_ls["ls_performance"]["ann_return"],
            "ls_sharpe": oos_ls["ls_performance"]["sharpe"],
            "n_periods": oos_stats["n_periods"],
        },
        "oos_decay_ratio": oos_decay_ratio,
    }

    # === metrics.json（机器唯一判定依据）===
    metrics = {
        **ic_stats,
        "rank_ic_mean": ic_stats["ic_mean"],
        "ls_annual_return": ls_result["ls_performance"]["ann_return"],
        "ls_sharpe": ls_result["ls_performance"]["sharpe"],
        "ls_max_drawdown": ls_result["ls_performance"]["max_drawdown"],
        "monthly_turnover": float(np.mean([t for vs in qbt["turnover"].values() for t in vs])) if qbt["turnover"] else np.nan,
        "oos_rank_ic": oos_stats["ic_mean"],
        "oos_icir": oos_stats["icir"],
        "oos_ls_annual_return": oos_ls["ls_performance"]["ann_return"],
        "oos_decay_ratio": oos_decay_ratio,
    }

    # === verdict 判定 ===
    standards_path = Path(__file__).resolve().parent.parent / "templates" / "eval_standards.json"
    standards = json.loads(standards_path.read_text(encoding="utf-8")) if standards_path.is_file() else {}
    core = standards.get("core_thresholds", {
        "abs_rank_ic_mean": 0.025,
        "icir": 0.5,
        "ls_annual_return": 0.08,
        "oos_decay_ratio": 0.5,
    })
    oos_fail = standards.get("oos_failure_threshold", 0.30)

    failures = []
    if abs(metrics["rank_ic_mean"]) < core["abs_rank_ic_mean"]:
        failures.append("abs_rank_ic_mean")
    if metrics["icir"] < core["icir"]:
        failures.append("icir")
    if metrics["ls_annual_return"] < core["ls_annual_return"]:
        failures.append("ls_annual_return")
    if metrics["oos_decay_ratio"] < core["oos_decay_ratio"]:
        failures.append("oos_decay_ratio")

    if oos_decay_ratio < oos_fail:
        verdict = "fail"
    elif len(failures) >= 2:
        verdict = "fail"
    elif len(failures) == 1 and "oos_decay_ratio" not in failures:
        verdict = "partial"
    else:
        verdict = "pass"

    evaluate_result = {
        "verdict": verdict,
        "core_failures": failures,
        "oos_decay_ratio": oos_decay_ratio,
        "thresholds": core,
        "metrics": metrics,
    }

    # === 输出 ===
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 5 张图
        _save_charts(ic_df, group_nav, group_perf_df, ls_result, n_groups, output_dir, report_name)

        # Excel
        _save_excel(ic_df, ic_stats, group_returns_net, group_nav, group_perf_df, output_dir, report_name)

        # JSON
        (output_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        (output_dir / "oos_comparison.json").write_text(json.dumps(oos_comparison, ensure_ascii=False, indent=2), encoding="utf-8")

        # evaluate_result.json 写到 workspace/{id}/
        workspace_id_dir = output_dir.parent
        (workspace_id_dir / "evaluate_result.json").write_text(json.dumps(evaluate_result, ensure_ascii=False, indent=2), encoding="utf-8")

        # eval_summary.md
        _save_eval_summary(metrics, in_stats, oos_stats, in_ls, oos_ls, verdict, output_dir, report_name)

    return {
        "ic_df": ic_df,
        "ic_stats": ic_stats,
        "ls_result": ls_result,
        "group_returns_net": group_returns_net,
        "group_nav": group_nav,
        "group_perf_df": group_perf_df,
        "oos_comparison": oos_comparison,
        "metrics": metrics,
        "evaluate_result": evaluate_result,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# 图表 / Excel 输出
# ---------------------------------------------------------------------------
def _save_charts(ic_df, group_nav, group_perf_df, ls_result, n_groups, output_dir, report_name):
    # 1. IC 时序
    fig, ax1 = plt.subplots(figsize=(14, 6))
    ic_values = ic_df["ic"].values
    dates = ic_df["date"].values
    n = len(dates)
    x_idx = np.arange(n)
    bar_colors = [BLUE if v >= 0 else RED for v in ic_values]
    ax1.bar(x_idx, ic_values, color=bar_colors, alpha=0.7, width=0.8, label="RankIC")
    ax1.axhline(ic_df["ic"].mean(), color="gray", linestyle="--", linewidth=1.2,
                label=f'IC均值={ic_df["ic"].mean():.4f}')
    ax1.axhline(0, color="black", linewidth=0.5)
    ax1.set_ylabel("RankIC", fontsize=12)
    tick_step = max(1, n // 8)
    ax1.set_xticks(x_idx[::tick_step])
    ax1.set_xticklabels([pd.Timestamp(d).strftime("%Y-%m") for d in dates[::tick_step]],
                        rotation=45, fontsize=9)
    ax2 = ax1.twinx()
    cum_ic = ic_df["ic"].cumsum()
    ax2.plot(x_idx, cum_ic.values, color="darkorange", linewidth=2.5, label="累计RankIC")
    ax2.set_ylabel("累计RankIC", fontsize=12, color="darkorange")
    ax2.tick_params(axis="y", labelcolor="darkorange")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=10, loc="upper left")
    ax1.set_title(f"{report_name} RankIC 时间序列", fontsize=14)
    ax1.grid(True, alpha=0.3, axis="y")
    ax1.set_xlim(-1, n)
    fig.tight_layout()
    fig.savefig(output_dir / "ic_series.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # 2. IC 分布
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(ic_df["ic"].dropna(), bins=30, color=BLUE, alpha=0.7, edgecolor="white")
    ax.axvline(ic_df["ic"].mean(), color=RED, linestyle="--", linewidth=1.5,
               label=f'均值={ic_df["ic"].mean():.4f}')
    ax.set_title(f"{report_name} RankIC 分布", fontsize=14)
    ax.set_xlabel("RankIC", fontsize=12)
    ax.set_ylabel("频数", fontsize=12)
    ax.legend(fontsize=10)
    fig.tight_layout()
    fig.savefig(output_dir / "ic_distribution.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # 3. 分组累计
    fig, ax = plt.subplots(figsize=(12, 6))
    cmap = plt.get_cmap(CMAP)
    group_cols = [c for c in group_nav.columns if c.startswith("G")]
    colors = [cmap(i / (len(group_cols) - 1)) for i in range(len(group_cols))]
    for col, color in zip(group_cols, colors):
        ax.plot(group_nav.index, group_nav[col], label=col, color=color, linewidth=1.5)
    if "long_short" in group_nav.columns:
        ax.plot(group_nav.index, group_nav["long_short"], label="多空", color="black", linewidth=2, linestyle="--")
    ax.set_title(f"{report_name} 分组累计收益", fontsize=14)
    ax.set_xlabel("日期", fontsize=12)
    ax.set_ylabel("累计净值", fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "group_cumulative_returns.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # 4. 分组年化收益
    fig, ax = plt.subplots(figsize=(10, 6))
    g_cols = [c for c in group_perf_df.index if c.startswith("G")]
    ann_rets = group_perf_df.loc[g_cols, "ann_return"]
    bar_colors = [BLUE if i >= len(g_cols) // 2 else RED for i in range(len(g_cols))]
    ax.bar(ann_rets.index, ann_rets.values * 100, color=bar_colors, alpha=0.8)
    ax.set_title(f"{report_name} 分组年化收益", fontsize=14)
    ax.set_xlabel("分组", fontsize=12)
    ax.set_ylabel("年化收益 (%)", fontsize=12)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
    fig.tight_layout()
    fig.savefig(output_dir / "group_returns_bar.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # 5. 净值对比
    fig, ax = plt.subplots(figsize=(12, 6))
    top_col = f"G{n_groups}"
    if top_col in group_nav.columns:
        ax.plot(group_nav.index, group_nav[top_col], label=f"多头({top_col})", color=BLUE, linewidth=1.5)
    if "long_short" in group_nav.columns:
        ax.plot(group_nav.index, group_nav["long_short"], label="多空组合", color=RED, linewidth=1.5)
    bot_col = "G1"
    if bot_col in group_nav.columns:
        ax.plot(group_nav.index, group_nav[bot_col], label=f"空头({bot_col})", color="gray", linewidth=1.0, linestyle="--")
    ax.set_title(f"{report_name} 净值对比", fontsize=14)
    ax.set_xlabel("日期", fontsize=12)
    ax.set_ylabel("净值", fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "net_value_comparison.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def _save_excel(ic_df, ic_stats, group_returns_net, group_nav, group_perf_df, output_dir, report_name):
    try:
        from openpyxl import load_workbook
        from openpyxl.drawing.image import Image as XlImage
        from openpyxl.styles import Font
        from openpyxl.utils import get_column_letter
    except ImportError:
        print("[WARN] openpyxl 未安装，跳过 Excel 输出")
        return

    excel_path = output_dir / f"{report_name}_results.xlsx"

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        summary_data = {
            "指标": ["RankIC均值", "RankIC标准差", "RankICIR(年化)", "RankIC胜率", "T统计量", "样本期数"],
            "值": [
                f"{ic_stats['ic_mean']:.4f}",
                f"{ic_stats['ic_std']:.4f}",
                f"{ic_stats['icir']:.2f}",
                f"{ic_stats['win_rate']:.2%}",
                f"{ic_stats['t_stat']:.2f}",
                str(ic_stats["n_periods"]),
            ],
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name="回测摘要", index=False, startrow=0)
        gp = group_perf_df.copy()
        gp.index.name = "分组"
        gp.to_excel(writer, sheet_name="回测摘要", startrow=len(summary_data["指标"]) + 3)

        ic_out = ic_df.copy()
        ic_out.columns = ["日期", "RankIC"]
        ic_out.to_excel(writer, sheet_name="IC序列", index=False)

        gr = group_returns_net.copy()
        gr.index.name = "日期"
        gr.to_excel(writer, sheet_name="分组收益")

        gn = group_nav.copy()
        gn.index.name = "日期"
        gn.to_excel(writer, sheet_name="分组净值")

    wb = load_workbook(excel_path)
    bold_font = Font(bold=True)
    for ws in wb.worksheets:
        for cell in ws[1]:
            cell.font = bold_font
        ws.sheet_properties.tabColor = "1F77B4"
        for col_idx, col_cells in enumerate(ws.columns, 1):
            max_len = max(len(str(c.value or "")) for c in col_cells)
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 30)
        ws.freeze_panes = "A2"

    def _embed(ws, img_path, anchor):
        if Path(img_path).exists():
            img = XlImage(str(img_path))
            img.width = 720
            img.height = 360
            ws.add_image(img, anchor)

    _embed(wb["IC序列"], output_dir / "ic_series.png", "D2")
    _embed(wb["IC序列"], output_dir / "ic_distribution.png", "D22")
    _embed(wb["分组收益"], output_dir / "group_returns_bar.png", "J2")
    _embed(wb["分组净值"], output_dir / "group_cumulative_returns.png", "J2")
    _embed(wb["分组净值"], output_dir / "net_value_comparison.png", "J22")

    wb.save(excel_path)
    print(f"Excel saved: {excel_path}")


def _save_eval_summary(metrics, in_stats, oos_stats, in_ls, oos_ls, verdict, output_dir, report_name):
    text = f"""# {report_name} 评估摘要

## verdict: **{verdict}**

## 样本内指标

| 指标 | 值 |
|------|---|
| RankIC 均值 | {metrics['rank_ic_mean']:.4f} |
| ICIR（年化） | {metrics['icir']:.2f} |
| IC 胜率 | {metrics['win_rate']:.2%} |
| 多空年化 | {metrics['ls_annual_return']:.2%} |
| 多空夏普 | {metrics['ls_sharpe']:.2f} |
| 多空最大回撤 | {metrics['ls_max_drawdown']:.2%} |
| 月均换手 | {metrics.get('monthly_turnover', 0):.2%} |

## OOS 指标

| 指标 | 值 |
|------|---|
| OOS RankIC | {metrics['oos_rank_ic']:.4f} |
| OOS ICIR | {metrics['oos_icir']:.2f} |
| OOS 多空年化 | {metrics['oos_ls_annual_return']:.2%} |
| OOS 衰减比 | {metrics['oos_decay_ratio']:.2%} |

> **判定**：verdict = {verdict}（按 templates/eval_standards.json 重算得出）
> 请用户审阅本报告后用 `/mine accept <id>` 或 `/mine reject <id> "<reason>"` 决策。
"""
    (output_dir / "eval_summary.md").write_text(text, encoding="utf-8")


# 用于 _save_charts / _save_excel 内部调用 json
import json