"""
factor_archiver.py — 沉淀辅助（accept / reject）

主会话禁止手工 cp / 写 md。所有归档走本工具：
    uv run python tools/factor_archiver.py approve <factor_id> --decision-time <ts>
    uv run python tools/factor_archiver.py reject  <factor_id> --reason "<r>" --decision-time <ts>

行为：
- approve：拷贝 workspace/{id}/src/ 与 spec/ 到 library/approved/{id}/ + 更新 INDEX.md + 追加 success_notes.md
- reject：拷贝 workspace/{id}/spec/README 摘要到 library/rejected/{id}/ + 写 library/failures/{id}.md + **追加** library/lessons/failure_lessons.md（绝不允许覆盖）
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from tools.state import read_state, write_state


def _repo_root() -> Path:
    return Path.cwd()


def _resolve_factor_id(query: str) -> str:
    """简化版 resolve（直接调 state.resolve 更复杂，这里靠主会话先 resolve）。"""
    return query


def _read_metrics(repo_root: Path, factor_id: str) -> dict:
    metrics_path = repo_root / "workspace" / factor_id / "results" / "metrics.json"
    if not metrics_path.is_file():
        return {}
    try:
        return json.loads(metrics_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_evaluate(repo_root: Path, factor_id: str) -> dict:
    p = repo_root / "workspace" / factor_id / "evaluate_result.json"
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_proposal(repo_root: Path, factor_id: str) -> str:
    p = repo_root / "workspace" / factor_id / "spec" / "factor_proposal.md"
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def cmd_approve(args: argparse.Namespace) -> None:
    repo_root = _repo_root()
    factor_id = _resolve_factor_id(args.factor_id)
    decision_time = args.decision_time or datetime.now().isoformat(timespec="seconds")

    state = read_state(factor_id)
    state["user_decision"] = "accept"
    state["decision_time"] = decision_time

    # 1. 创建 approved/{id}/
    approved_dir = repo_root / "library" / "approved" / factor_id
    approved_dir.mkdir(parents=True, exist_ok=True)

    # 2. 拷贝 src + spec
    workspace_dir = repo_root / "workspace" / factor_id
    src_dir = workspace_dir / "src"
    spec_dir = workspace_dir / "spec"

    if src_dir.is_dir():
        for f in src_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, approved_dir / f.name)

    # 3. 写 README.md
    metrics = _read_metrics(repo_root, factor_id)
    evaluate = _read_evaluate(repo_root, factor_id)
    proposal = _read_proposal(repo_root, factor_id)

    readme = approved_dir / "README.md"
    readme.write_text(
        f"# {factor_id}\n\n"
        f"- **入库时间**：{decision_time}\n"
        f"- **方向**：{state.get('direction', '')}\n"
        f"- **评估 verdict**：{evaluate.get('verdict', '')}\n"
        f"- **关键指标**：\n"
        f"  - RankIC 均值：{metrics.get('rank_ic_mean', 'n/a')}\n"
        f"  - ICIR：{metrics.get('icir', 'n/a')}\n"
        f"  - 多空年化：{metrics.get('ls_annual_return', 'n/a')}\n"
        f"  - OOS 衰减比：{metrics.get('oos_decay_ratio', 'n/a')}\n\n"
        f"## 因子定义\n\n"
        f"{proposal[:1500]}\n",
        encoding="utf-8",
    )

    # 4. 更新 INDEX.md（追加一行）
    idx_path = repo_root / "library" / "approved" / "INDEX.md"
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    if not idx_path.exists():
        idx_path.write_text(
            "# 因子库索引（approved）\n\n"
            "| factor_id | 方向 | 类别 | 关键指标 | 入库日期 |\n"
            "|-----------|------|------|----------|----------|\n",
            encoding="utf-8",
        )
    with idx_path.open("a", encoding="utf-8") as f:
        f.write(
            f"| {factor_id} | {state.get('direction', '')} | "
            f"{evaluate.get('category', '')} | "
            f"IC={metrics.get('rank_ic_mean', 'n/a')} "
            f"ICIR={metrics.get('icir', 'n/a')} "
            f"多空={metrics.get('ls_annual_return', 'n/a')} | "
            f"{decision_time[:10]} |\n"
        )

    # 5. 追加 success_notes.md
    sn_path = repo_root / "library" / "lessons" / "success_notes.md"
    sn_path.parent.mkdir(parents=True, exist_ok=True)
    if not sn_path.exists():
        sn_path.write_text("# 成功经验笔记（success_notes）\n\n", encoding="utf-8")
    with sn_path.open("a", encoding="utf-8") as f:
        f.write(
            f"\n---\n\n## {factor_id} · {state.get('direction', '')} · {decision_time[:10]}\n\n"
            f"- **类目**：{evaluate.get('category', '')}\n"
            f"- **关键指标**：IC={metrics.get('rank_ic_mean', 'n/a')} "
            f"ICIR={metrics.get('icir', 'n/a')} 多空={metrics.get('ls_annual_return', 'n/a')}\n"
            f"- **成功经验**：成功通过人工审查入库（自动登记，建议人工补充类目归纳）\n\n"
        )

    write_state(factor_id, state)
    print(f"[OK] approve {factor_id} -> {approved_dir}")


def cmd_reject(args: argparse.Namespace) -> None:
    repo_root = _repo_root()
    factor_id = _resolve_factor_id(args.factor_id)
    decision_time = args.decision_time or datetime.now().isoformat(timespec="seconds")
    reason = args.reason or "(无明确理由)"

    state = read_state(factor_id)
    state["user_decision"] = "reject"
    state["user_decision_reason"] = reason
    state["decision_time"] = decision_time

    metrics = _read_metrics(repo_root, factor_id)
    evaluate = _read_evaluate(repo_root, factor_id)
    proposal = _read_proposal(repo_root, factor_id)
    verdict = evaluate.get("verdict", "fail")

    # 1. rejected/{id}/README.md
    rejected_dir = repo_root / "library" / "rejected" / factor_id
    rejected_dir.mkdir(parents=True, exist_ok=True)
    (rejected_dir / "README.md").write_text(
        f"# {factor_id}（已拒收）\n\n"
        f"- **决策时间**：{decision_time}\n"
        f"- **方向**：{state.get('direction', '')}\n"
        f"- **评估 verdict**：{verdict}\n"
        f"- **拒绝理由**：{reason}\n\n"
        f"## 关键指标\n\n"
        f"- RankIC 均值：{metrics.get('rank_ic_mean', 'n/a')}\n"
        f"- ICIR：{metrics.get('icir', 'n/a')}\n"
        f"- 多空年化：{metrics.get('ls_annual_return', 'n/a')}\n"
        f"- OOS 衰减比：{metrics.get('oos_decay_ratio', 'n/a')}\n",
        encoding="utf-8",
    )

    # 2. failures/{id}.md（按 failure_lessons_schema）
    failures_dir = repo_root / "library" / "failures"
    failures_dir.mkdir(parents=True, exist_ok=True)
    (failures_dir / f"{factor_id}.md").write_text(
        f"---\n"
        f"factor_id: {factor_id}\n"
        f"direction: {state.get('direction', '')}\n"
        f"verdict: {verdict}\n"
        f"decision_time: {decision_time}\n"
        f"---\n\n"
        f"# {factor_id} · 失败档案\n\n"
        f"## 因子公式\n\n"
        f"{proposal[:800]}\n\n"
        f"## 拒绝理由\n\n"
        f"> {reason}\n\n"
        f"## 样本内指标\n\n"
        f"- RankIC 均值：{metrics.get('rank_ic_mean', 'n/a')}\n"
        f"- ICIR：{metrics.get('icir', 'n/a')}\n"
        f"- 多空年化：{metrics.get('ls_annual_return', 'n/a')}\n"
        f"- 多空夏普：{metrics.get('ls_sharpe', 'n/a')}\n"
        f"- 多空最大回撤：{metrics.get('ls_max_drawdown', 'n/a')}\n"
        f"- 月均换手：{metrics.get('monthly_turnover', 'n/a')}\n\n"
        f"## OOS 指标\n\n"
        f"- OOS RankIC：{metrics.get('oos_rank_ic', 'n/a')}\n"
        f"- OOS 衰减比：{metrics.get('oos_decay_ratio', 'n/a')}\n\n"
        f"## 失败模式标签\n\n"
        f"（由 factor-archivist 或人工补充）\n\n"
        f"## 教训要点\n\n"
        f"（由 factor-archivist 或人工补充）\n\n"
        f"## 回避建议\n\n"
        f"（由 factor-archivist 或人工补充）\n",
        encoding="utf-8",
    )

    # 3. **追加** failure_lessons.md（绝不覆盖）
    fl_path = repo_root / "library" / "lessons" / "failure_lessons.md"
    fl_path.parent.mkdir(parents=True, exist_ok=True)
    if not fl_path.exists():
        fl_path.write_text("# 失败教训笔记\n\n", encoding="utf-8")

    # 追加（append 模式，'a'，绝不覆盖）
    with fl_path.open("a", encoding="utf-8") as f:
        f.write(
            f"\n---\n\n## {factor_id} · {state.get('direction', '')} · {decision_time[:10]}\n\n"
            f"- **失败模式**：（待补全）\n"
            f"- **因子公式**：见 failures/{factor_id}.md\n"
            f"- **样本内**：IC={metrics.get('rank_ic_mean', 'n/a')} "
            f"ICIR={metrics.get('icir', 'n/a')} 多空={metrics.get('ls_annual_return', 'n/a')}\n"
            f"- **OOS**：IC={metrics.get('oos_rank_ic', 'n/a')} 衰减={metrics.get('oos_decay_ratio', 'n/a')}\n"
            f"- **拒绝理由**：{reason}\n"
            f"- **教训**：（待补全，建议人工或 factor-archivist 归纳）\n"
            f"- **下次改**：（待补全）\n\n"
        )

    write_state(factor_id, state)
    print(f"[OK] reject {factor_id} ->")
    print(f"     - library/rejected/{factor_id}/")
    print(f"     - library/failures/{factor_id}.md")
    print(f"     - library/lessons/failure_lessons.md (appended)")


def main() -> None:
    p = argparse.ArgumentParser(description="factormine factor_archiver")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_a = sub.add_parser("approve", help="accept 归档")
    p_a.add_argument("factor_id")
    p_a.add_argument("--decision-time", default=None)
    p_a.set_defaults(func=cmd_approve)

    p_r = sub.add_parser("reject", help="reject 归档 + 追加教训")
    p_r.add_argument("factor_id")
    p_r.add_argument("--reason", required=True)
    p_r.add_argument("--decision-time", default=None)
    p_r.set_defaults(func=cmd_reject)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()