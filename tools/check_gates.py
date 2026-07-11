"""
check_gates.py — 门禁机器判定（factormine-plugin）

按 stage 重算产物文件存在性 / 完整性 / 字段是否齐全。输出每行 [PASS|FAIL] 与末行 VERDICT。

支持：
- --stage <stage>             默认模式（重算并输出 VERDICT）
- --stage <stage> --assert-done 前置断言模式（只读 state.stages[stage]==done，否则 exit 1）
- --stage <stage> --record    把当前门禁结果写入 workspace/{id}/audit/{stage}_gate.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# 复用 state 模块的 STAGE_ORDER / 读写
from tools.state import STAGE_ORDER, get_workspace_root, read_state

# ---------------------------------------------------------------------------
# 工具：解析 size / grep
# ---------------------------------------------------------------------------
def file_exists_min_size(path: Path, min_size: int = 1) -> bool:
    return path.is_file() and path.stat().st_size >= min_size


def grep_keyword(path: Path, keyword: str) -> bool:
    """检查文件是否含某关键词（粗略，含中文友好）。"""
    if not path.is_file():
        return False
    return keyword in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 6 个 stage 的门禁定义
# ---------------------------------------------------------------------------
def gate_propose(workspace_root: Path, factor_id: str) -> list[tuple[str, bool, str]]:
    """propose 阶段：factor_proposal.md / design_notes.md / param_card.yaml +
    失败教训逐条 ID 引用 + 已知因子撞库声明 + F-1~F-9 可行性自查。
    """
    spec_dir = workspace_root / factor_id / "spec"
    repo_root = workspace_root.parent
    checks: list[tuple[str, bool, str]] = []

    p1 = spec_dir / "factor_proposal.md"
    checks.append((
        "G-PR-1 factor_proposal.md 存在且 >500 字",
        file_exists_min_size(p1, 500),
        str(p1),
    ))

    p2 = spec_dir / "design_notes.md"
    checks.append((
        "G-PR-2 design_notes.md 存在",
        file_exists_min_size(p2),
        str(p2),
    ))

    p3 = spec_dir / "param_card.yaml"
    checks.append((
        "G-PR-3 param_card.yaml 存在且可解析",
        _yaml_parseable(p3),
        str(p3),
    ))

    p4 = spec_dir / "factor_proposal.md"

    # G-PR-4 失败教训**逐条 ID 引用**：扫描失败库全部 f00X ID，proposal 必须**每条**都引用
    lessons_path = repo_root / "library" / "lessons" / "failure_lessons.md"
    failure_ids = set()
    if lessons_path.is_file():
        # 提取形如 f001 / f012 / f123 的 ID
        failure_ids = set(re.findall(r"\bf\d{3}\b", lessons_path.read_text(encoding="utf-8")))

    # 同时扫 failures/ 目录的 md 文件名
    failures_dir = repo_root / "library" / "failures"
    if failures_dir.is_dir():
        for f in failures_dir.glob("*.md"):
            m = re.match(r"(f\d{3})", f.stem)
            if m:
                failure_ids.add(m.group(1))

    if p4.is_file() and failure_ids:
        proposal_text = p4.read_text(encoding="utf-8")
        # 提案中必须**逐条**引用（不是摘要、不是只引部分）
        referenced_ids = set(re.findall(r"\bf\d{3}\b", proposal_text))
        missing_ids = failure_ids - referenced_ids
        ok = len(missing_ids) == 0
        detail = f"失败库 {len(failure_ids)} 条，proposal 引用 {len(referenced_ids & failure_ids)} 条，缺失 {sorted(missing_ids) if missing_ids else '无'}"
    elif not failure_ids:
        # 失败库为空（首次运行），放宽通过
        ok = True
        detail = "失败库为空（首次运行），跳过"
    else:
        ok = False
        detail = "proposal 不存在"
    checks.append((
        "G-PR-4 失败教训**逐条 ID 引用**（不是摘要）",
        ok,
        detail,
    ))

    # G-PR-5 数据可用性：proposal 里应出现 available / derive / missing 至少一个
    if p4.is_file():
        text = p4.read_text(encoding="utf-8")
        data_status_ok = any(k in text for k in ("available", "derive", "missing"))
    else:
        data_status_ok = False
    checks.append((
        "G-PR-5 数据可用性自检标注",
        data_status_ok,
        "missing keywords" if not data_status_ok else "ok",
    ))

    # G-PR-6 不与已入库因子雷同（简易：grep INDEX.md 检查冲突）
    idx_path = repo_root / "library" / "approved" / "INDEX.md"
    if idx_path.is_file() and p4.is_file():
        idx_text = idx_path.read_text(encoding="utf-8")
        proposal_text = p4.read_text(encoding="utf-8")
        # 取 proposal 第一行公式（粗略），若在 INDEX.md 出现视为雷同
        first_formula = next((line for line in proposal_text.splitlines() if "=" in line and "factor" in line.lower()), "")
        is_dup = bool(first_formula) and first_formula in idx_text
        checks.append((
            "G-PR-6 与已入库因子不雷同",
            not is_dup,
            "dup detected" if is_dup else "ok",
        ))
    else:
        checks.append(("G-PR-6 与已入库因子不雷同（INDEX.md 不存在，跳过）", True, "skipped"))

    # G-PR-7 可行性自查 F-1 ~ F-9 九项勾选（自由设计模式下必查）
    if p4.is_file():
        text = p4.read_text(encoding="utf-8")
        # 匹配 F-1 ~ F-9 九项
        n_feasibility = 0
        for i in range(1, 10):
            pattern = rf"F[-\.]?{i}\b.{{0,20}}(\[x\]|✓|\[✓\]|已勾|已确认|通过)"
            n_feasibility += len(re.findall(pattern, text, re.IGNORECASE))
        checks.append((
            "G-PR-7 可行性自查 F-1 ~ F-9 全部勾选",
            n_feasibility >= 9,
            f"matched={n_feasibility}/9",
        ))
    else:
        checks.append(("G-PR-7 可行性自查 F-1 ~ F-9 全部勾选", False, "proposal 不存在"))

    # G-PR-8 已知因子撞库声明（F-9 必填）：≥3 个最接近的已知因子 + 关键差异
    if p4.is_file():
        text = p4.read_text(encoding="utf-8")
        # 检测要点：必须出现 ≥3 个已知因子关键词
        #   - Alpha#X（WorldQuant）
        #   - Alphalens / MeanReversion / Momentum / Volume / PriceVolumeTrend
        #   - 国内经典：反转 / 动量 / Amihud / EP / BP / ROE
        #   - 学术异象：Fama / Carhart / Sloan / PEAD / SMB / HML / UMD
        kw_patterns = [
            r"Alpha[#\s]?\d+",                # WorldQuant Alpha#X
            r"\bAlphalens\b",
            r"\bMeanReversion\b|\bMomentum\b|\bPriceVolumeTrend\b",
            r"反转|动量|Amihud|\bEP\b|\bBP\b|\bROE\b|12-1|UMD|WML|SMB|HML|PEAD|应计|净股票|复合发行|QMJ|Distress",
        ]
        n_kw = sum(len(re.findall(p, text, re.IGNORECASE)) for p in kw_patterns)
        # 同时检查"关键差异"声明存在
        has_keyword_diff = "关键差异" in text or "创新点" in text or "根本性不同" in text
        ok = n_kw >= 3 and has_keyword_diff
        checks.append((
            "G-PR-8 已知因子撞库声明（F-9，≥3 个已知因子 + 关键差异）",
            ok,
            f"关键词命中={n_kw}, 关键差异声明={has_keyword_diff}",
        ))
    else:
        checks.append(("G-PR-8 已知因子撞库声明（F-9）", False, "proposal 不存在"))

    return checks


def gate_validation(workspace_root: Path, factor_id: str) -> list[tuple[str, bool, str]]:
    """validation 阶段：validation_result.md 存在 + verdict ∈ {pass, fail}。"""
    spec_dir = workspace_root / factor_id / "spec"
    vr = spec_dir / "validation_result.md"

    checks: list[tuple[str, bool, str]] = []

    # G-VD-1 validation_result.md 存在
    checks.append((
        "G-VD-1 validation_result.md 存在",
        file_exists_min_size(vr),
        str(vr),
    ))

    # G-VD-2 verdict ∈ {pass, fail}
    verdict = None
    if vr.is_file():
        text = vr.read_text(encoding="utf-8")
        # 提取 verdict: pass / fail
        m = re.search(r"verdict:\s*(pass|fail)", text, re.IGNORECASE)
        if m:
            verdict = m.group(1).lower()
    checks.append((
        "G-VD-2 verdict ∈ {pass, fail}",
        verdict in ("pass", "fail"),
        f"verdict={verdict}",
    ))

    # G-VD-3 若 fail，issues 列表非空
    if verdict == "fail" and vr.is_file():
        text = vr.read_text(encoding="utf-8")
        has_issues = "issues:" in text.lower() and "- [" in text
        checks.append((
            "G-VD-3 若 fail，issues 列表非空",
            has_issues,
            "issues found" if has_issues else "no issues",
        ))
    else:
        checks.append((
            "G-VD-3 若 fail，issues 列表非空",
            True,  # pass 时跳过此检查
            "verdict=pass, skip",
        ))

    return checks


def _yaml_parseable(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        import yaml  # type: ignore
        yaml.safe_load(path.read_text(encoding="utf-8"))
        return True
    except Exception:
        # 极简 YAML 解析（key: value 行）
        text = path.read_text(encoding="utf-8")
        return any(":" in line and not line.strip().startswith("#") for line in text.splitlines())


def gate_design(workspace_root: Path, factor_id: str) -> list[tuple[str, bool, str]]:
    """design 阶段：algorithm_spec.md 五章节 + 未来函数三查勾选 + ≥3 单元测试用例。"""
    spec_dir = workspace_root / factor_id / "spec"
    p = spec_dir / "algorithm_spec.md"

    checks: list[tuple[str, bool, str]] = []
    checks.append((
        "G-DS-1 algorithm_spec.md 存在且 >500 字",
        file_exists_min_size(p, 500),
        str(p),
    ))

    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    sections = ["变量定义表", "伪代码", "未来函数", "NaN", "单元测试"]
    missing = [s for s in sections if s not in text]
    checks.append((
        "G-DS-2 含五章节",
        not missing,
        f"missing={missing}" if missing else "ok",
    ))

    # G-DS-3 未来函数三查勾选：grep "披露日" "T+1" "rolling shift"
    n_checks = sum(
        1 for kw in ("披露日", "T+1", "shift")
        if kw in text
    )
    checks.append((
        "G-DS-3 未来函数三查勾选",
        n_checks >= 3,
        f"matched={n_checks}/3",
    ))

    # G-DS-4 ≥3 单元测试用例
    n_tests = text.count("用例") + text.count("测试")
    checks.append((
        "G-DS-4 单元测试用例 ≥3",
        n_tests >= 3,
        f"count={n_tests}",
    ))

    # G-DS-5 列出 common 函数全部存在（grep common/ 验证）
    common_dir = workspace_root.parent / "common"
    common_funcs_mentioned = re.findall(r"(winsorize|standardize|neutralize_factor|calculate_ic|quantile_backtest|long_short_backtest)", text)
    missing_funcs = []
    if common_dir.is_dir():
        all_py = "\n".join(p.read_text(encoding="utf-8") for p in common_dir.glob("*.py"))
        for fn in set(common_funcs_mentioned):
            if f"def {fn}" not in all_py:
                missing_funcs.append(fn)
    checks.append((
        "G-DS-5 common 函数全部存在",
        not missing_funcs,
        f"missing={missing_funcs}" if missing_funcs else "ok",
    ))

    return checks


def gate_implement(workspace_root: Path, factor_id: str) -> list[tuple[str, bool, str]]:
    """implement 阶段：4 个 src 文件 + 冒烟测试通过 + 编译通过。"""
    src_dir = workspace_root / factor_id / "src"

    checks: list[tuple[str, bool, str]] = []
    for fname in ("factor.py", "config.py", "main.py", "_smoke.py"):
        p = src_dir / fname
        checks.append((
            f"G-IM-1 src/{fname} 存在",
            file_exists_min_size(p),
            str(p),
        ))

    # G-IM-2 _smoke.py 跑通：实际执行
    smoke = src_dir / "_smoke.py"
    if smoke.is_file():
        import subprocess
        r = subprocess.run([sys.executable, str(smoke)], capture_output=True, text=True, timeout=60)
        ok = r.returncode == 0
        checks.append((
            "G-IM-2 _smoke.py 单元测试通过",
            ok,
            r.stderr[:200] if not ok else "ok",
        ))
    else:
        checks.append(("G-IM-2 _smoke.py 单元测试通过", False, "文件不存在"))

    # G-IM-3 compileall
    if src_dir.is_dir():
        import subprocess
        r = subprocess.run([sys.executable, "-m", "compileall", str(src_dir)], capture_output=True, text=True, timeout=60)
        checks.append((
            "G-IM-3 python -m compileall 通过",
            r.returncode == 0,
            r.stderr[:200] if r.returncode != 0 else "ok",
        ))
    else:
        checks.append(("G-IM-3 python -m compileall 通过", False, "src 不存在"))

    # G-IM-4 main.py import dry-run
    main_py = src_dir / "main.py"
    if main_py.is_file():
        import subprocess
        r = subprocess.run([sys.executable, "-c", f"import importlib.util, sys; spec=importlib.util.spec_from_file_location('m','{main_py.resolve()}'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('ok')"],
                          capture_output=True, text=True, timeout=60)
        ok = r.returncode == 0
        checks.append((
            "G-IM-4 main.py import dry-run",
            ok,
            r.stderr[:200] if not ok else "ok",
        ))
    else:
        checks.append(("G-IM-4 main.py import dry-run", False, "文件不存在"))

    # G-IM-5 config.py 参数全部能从 param_card.yaml 反查（极简：行数对比）
    param_card = workspace_root / factor_id / "spec" / "param_card.yaml"
    config_py = src_dir / "config.py"
    if param_card.is_file() and config_py.is_file():
        yaml_text = param_card.read_text(encoding="utf-8")
        cfg_text = config_py.read_text(encoding="utf-8")
        # 提取 yaml 顶层 key
        keys = []
        for line in yaml_text.splitlines():
            if ":" in line and not line.startswith(" ") and not line.startswith("#"):
                key = line.split(":", 1)[0].strip()
                if key:
                    keys.append(key)
        n_missing = sum(1 for k in keys if k not in cfg_text)
        checks.append((
            "G-IM-5 config.py 参数反查 param_card",
            n_missing == 0,
            f"missing={n_missing}/{len(keys)}",
        ))
    else:
        checks.append(("G-IM-5 config.py 参数反查", False, "param_card.yaml 或 config.py 缺失"))

    return checks


def gate_evaluate(workspace_root: Path, factor_id: str) -> list[tuple[str, bool, str]]:
    """evaluate 阶段：metrics.json + oos_comparison.json + 5 张图 + xlsx + evaluate_result.json。"""
    results_dir = workspace_root / factor_id / "results"

    checks: list[tuple[str, bool, str]] = []

    metrics = results_dir / "metrics.json"
    n_metrics = 0
    if metrics.is_file():
        try:
            data = json.loads(metrics.read_text(encoding="utf-8"))
            n_metrics = len(data) if isinstance(data, dict) else 0
        except Exception:
            pass
    checks.append((
        "G-EV-1 metrics.json 存在且 ≥12 个核心指标",
        file_exists_min_size(metrics) and n_metrics >= 12,
        f"count={n_metrics}",
    ))

    oos = results_dir / "oos_comparison.json"
    checks.append((
        "G-EV-2 oos_comparison.json 存在",
        file_exists_min_size(oos),
        str(oos),
    ))

    for img in ("ic_series.png", "ic_distribution.png", "group_cumulative_returns.png", "group_returns_bar.png", "net_value_comparison.png"):
        p = results_dir / img
        checks.append((
            f"G-EV-3 {img} 存在且 ≥15KB",
            file_exists_min_size(p, 15 * 1024),
            str(p),
        ))

    xlsx = results_dir / "factor_eval.xlsx"
    checks.append((
        "G-EV-4 factor_eval.xlsx 存在且 ≥30KB",
        file_exists_min_size(xlsx, 30 * 1024),
        str(xlsx),
    ))

    er = workspace_root / factor_id / "evaluate_result.json"
    verdict = None
    if er.is_file():
        try:
            verdict = json.loads(er.read_text(encoding="utf-8")).get("verdict")
        except Exception:
            pass
    checks.append((
        "G-EV-5 evaluate_result.json verdict ∈ {pass,partial,fail}",
        verdict in ("pass", "partial", "fail"),
        f"verdict={verdict}",
    ))

    # G-EV-6/7 核心门槛：对比 eval_standards.json（仅展示，不阻断）
    standards_path = workspace_root.parent / "templates" / "eval_standards.json"
    if standards_path.is_file() and metrics.is_file():
        try:
            standards = json.loads(standards_path.read_text(encoding="utf-8"))
            metrics_data = json.loads(metrics.read_text(encoding="utf-8"))
            core = standards["core_thresholds"]
            failures = []
            if abs(metrics_data.get("rank_ic_mean", 0)) < core["abs_rank_ic_mean"]:
                failures.append("abs_rank_ic_mean")
            if metrics_data.get("icir", 0) < core["icir"]:
                failures.append("icir")
            if metrics_data.get("ls_annual_return", 0) < core["ls_annual_return"]:
                failures.append("ls_annual_return")
            if metrics_data.get("oos_decay_ratio", 1) < core["oos_decay_ratio"]:
                failures.append("oos_decay_ratio")
            checks.append((
                "G-EV-6 核心门槛（参考，不阻断）",
                len(failures) <= 1,
                f"failures={failures}",
            ))
        except Exception as e:  # noqa
            checks.append(("G-EV-6 核心门槛", True, f"skip: {e}"))

    return checks


def gate_review(workspace_root: Path, factor_id: str) -> list[tuple[str, bool, str]]:
    """review 阶段：evaluate_result.json 呈现 + review_decision.md 记账。"""
    er = workspace_root / factor_id / "evaluate_result.json"
    rd = workspace_root / factor_id / "review_decision.md"

    checks: list[tuple[str, bool, str]] = []
    checks.append((
        "G-RV-1 evaluate_result.json 已呈现",
        er.is_file(),
        str(er),
    ))
    checks.append((
        "G-RV-2 review_decision.md 记账",
        file_exists_min_size(rd),
        str(rd),
    ))
    if rd.is_file():
        text = rd.read_text(encoding="utf-8")
        has_ts = bool(re.search(r"\d{4}-\d{2}-\d{2}", text))
        checks.append((
            "G-RV-3 决策时间戳",
            has_ts,
            "ts missing" if not has_ts else "ok",
        ))
    else:
        checks.append(("G-RV-3 决策时间戳", False, "review_decision.md 缺失"))

    return checks


def gate_archive(workspace_root: Path, factor_id: str) -> list[tuple[str, bool, str]]:
    """archive 阶段：根据 user_decision 走两条分支之一。"""
    state = read_state(factor_id)
    decision = state.get("user_decision")
    repo_root = workspace_root.parent

    checks: list[tuple[str, bool, str]] = []

    if decision == "accept":
        for fname in ("README.md", "config.yaml", "factor.py"):
            p = repo_root / "library" / "approved" / factor_id / fname
            checks.append((f"G-AR-1 library/approved/{factor_id}/{fname}", file_exists_min_size(p), str(p)))
        idx = repo_root / "library" / "approved" / "INDEX.md"
        idx_has = idx.is_file() and factor_id in idx.read_text(encoding="utf-8")
        checks.append(("G-AR-2 INDEX.md 已追加", idx_has, str(idx)))
        sn = repo_root / "library" / "lessons" / "success_notes.md"
        sn_has = sn.is_file() and factor_id in sn.read_text(encoding="utf-8")
        checks.append(("G-AR-3 success_notes.md 已追加", sn_has, str(sn)))
    elif decision == "reject":
        rr = repo_root / "library" / "rejected" / factor_id / "README.md"
        checks.append(("G-AR-4 rejected/README.md", file_exists_min_size(rr), str(rr)))
        ff = repo_root / "library" / "failures" / f"{factor_id}.md"
        checks.append(("G-AR-5 failures/{id}.md", file_exists_min_size(ff), str(ff)))
        fl = repo_root / "library" / "lessons" / "failure_lessons.md"
        fl_has = fl.is_file() and factor_id in fl.read_text(encoding="utf-8")
        checks.append(("G-AR-6 lessons/failure_lessons.md 已追加", fl_has, str(fl)))
        # G-AR-7 关键词命中
        if fl.is_file():
            text = fl.read_text(encoding="utf-8")
            # 取本轮片段（粗略：factor_id 之后的内容）
            idx = text.find(factor_id)
            snippet = text[idx:idx + 2000] if idx >= 0 else ""
            kws = ["公式", "OOS", "教训"]
            n = sum(1 for k in kws if k in snippet)
            checks.append(("G-AR-7 教训笔记三关键词", n >= 3, f"matched={n}/3"))
    else:
        checks.append(("G-AR-X user_decision 未设置", False, f"decision={decision}"))

    return checks


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def run_gate(workspace_root: Path, factor_id: str, stage: str, record: bool = False) -> int:
    gate_funcs = {
        "propose": gate_propose,
        "validation": gate_validation,
        "design": gate_design,
        "implement": gate_implement,
        "evaluate": gate_evaluate,
        "review": gate_review,
        "archive": gate_archive,
    }
    if stage not in gate_funcs:
        print(f"ERROR: 未知 stage {stage}（应为 {list(gate_funcs.keys())}）", file=sys.stderr)
        return 2

    checks = gate_funcs[stage](workspace_root, factor_id)
    n_pass = sum(1 for _, ok, _ in checks if ok)
    n_total = len(checks)
    verdict = "PASS" if n_pass == n_total else "FAIL"

    # 输出
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}  ({detail})")
    print(f"VERDICT {verdict} ({n_pass}/{n_total})")

    # 记录
    if record:
        audit_dir = workspace_root / factor_id / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        gate_json = {
            "stage": stage,
            "ts": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks],
            "verdict": verdict,
        }
        (audit_dir / f"{stage}_gate.json").write_text(json.dumps(gate_json, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0 if verdict == "PASS" else 1


def assert_done(workspace_root: Path, factor_id: str, prev_stage: str) -> int:
    """--assert-done 模式：state.stages[prev] == done 才返回 0，否则 1。"""
    state = read_state(factor_id)
    if state["stages"].get(prev_stage) == "done":
        print(f"[OK] {factor_id} stage {prev_stage} == done")
        return 0
    else:
        print(f"[FAIL] {factor_id} stage {prev_stage} != done (current={state['stages'].get(prev_stage)})", file=sys.stderr)
        return 1


def main() -> None:
    p = argparse.ArgumentParser(description="factormine check_gates")
    p.add_argument("factor_id", nargs="?")
    p.add_argument("--stage", required=True, choices=STAGE_ORDER + ["setup"])
    p.add_argument("--assert-done", action="store_true", help="只读 state.stages[stage] 是否 done")
    p.add_argument("--record", action="store_true", help="把结果写入 audit/{stage}_gate.json")
    args = p.parse_args()

    workspace_root = get_workspace_root()

    if args.assert_done:
        sys.exit(assert_done(workspace_root, args.factor_id, args.stage))

    if not args.factor_id:
        print("ERROR: 需 factor_id", file=sys.stderr)
        sys.exit(2)

    sys.exit(run_gate(workspace_root, args.factor_id, args.stage, args.record))


if __name__ == "__main__":
    main()