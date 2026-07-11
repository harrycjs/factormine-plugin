"""
state.py — 状态写入口（factormine-plugin 唯一）

本文件是 workspace/{id}/state.json 的**唯一写入口**。主会话专用，子 agent 一律不读写 state.json。

STAGE_ORDER（写死，不得改名）：
    propose → validation → design → implement → evaluate → review → archive

factor_id 格式：`fNNN_<slug>`（三位顺序号 + 语义短名），由 `next-id` 自动分配。
状态机的 status 字段：running / paused_blocked / awaiting_review / done / done_rejected
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# STAGE_ORDER（写死）
# ---------------------------------------------------------------------------
STAGE_ORDER = ["propose", "validation", "design", "implement", "evaluate", "review", "archive"]

# 编号格式
ID_PATTERN = re.compile(r"^f(\d{3})_(.+)$")
ID_SHORT = re.compile(r"^(?:f?(\d{1,3})|(\d+))$")  # 缩写：f3 / 003 / 3


def get_workspace_root() -> Path:
    """解析 workspace 根目录（cwd 优先，回退到脚本所在仓库根）。"""
    if (Path.cwd() / "workspace").is_dir():
        return Path.cwd() / "workspace"
    # 兜底：本文件所在上两级
    return Path(__file__).resolve().parent.parent / "workspace"


def get_state_path(factor_id: str) -> Path:
    return get_workspace_root() / factor_id / "state.json"


# ---------------------------------------------------------------------------
# state.json 模式（参考，但非强制 schema）
# ---------------------------------------------------------------------------
DEFAULT_STATE: dict[str, Any] = {
    "factor_id": None,
    "direction": None,
    "slug": None,
    "status": "running",          # running / paused_blocked / awaiting_review / done / done_rejected
    "stages": {s: "pending" for s in STAGE_ORDER},  # pending / running / done / skipped
    "stage_attempts": {s: 0 for s in STAGE_ORDER},
    "current_stage": None,
    "verdict": None,              # pass / partial / fail（evaluate 阶段产出）
    "user_decision": None,        # accept / reject / iterate（review 阶段用户决策）
    "user_decision_reason": None,
    "decision_time": None,
    "pending_question": None,
    "events": [],                 # 时间戳事件流
    "created_at": None,
    "updated_at": None,
    "iteration_count": 0,         # 同一方向下本轮数（达到 max_iterations 自动停下）
    "max_iterations": 3,          # 迭代轮数上限（从 .mine.json 读，0=不自动迭代）
}


# ---------------------------------------------------------------------------
# 读写底层
# ---------------------------------------------------------------------------
def read_state(factor_id: str) -> dict[str, Any]:
    path = get_state_path(factor_id)
    if not path.is_file():
        raise FileNotFoundError(f"state.json 不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(factor_id: str, state: dict[str, Any]) -> None:
    path = get_state_path(factor_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    # 整文件覆盖（无锁；主会话单线程派发，严禁同批并行）
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# 子命令：init
# ---------------------------------------------------------------------------
def cmd_init(args: argparse.Namespace) -> None:
    factor_id = args.factor_id
    if not ID_PATTERN.match(factor_id):
        raise ValueError(f"factor_id 格式错误：{factor_id}（要求 fNNN_slug）")

    state = dict(DEFAULT_STATE)
    state["factor_id"] = factor_id
    state["slug"] = factor_id.split("_", 1)[1]
    state["direction"] = args.direction
    state["status"] = "running"
    state["current_stage"] = "propose"
    state["stages"]["propose"] = "running"
    state["created_at"] = datetime.now().isoformat(timespec="seconds")
    state["events"].append({"ts": state["created_at"], "type": "init", "direction": args.direction})

    write_state(factor_id, state)
    print(f"[OK] init {factor_id} (direction={args.direction}), current_stage=propose")


# ---------------------------------------------------------------------------
# 子命令：next-id
# ---------------------------------------------------------------------------
def cmd_next_id(args: argparse.Namespace) -> None:
    workspace = get_workspace_root()
    workspace.mkdir(parents=True, exist_ok=True)

    # 扫现有 id，取最大编号
    max_n = 0
    for child in workspace.iterdir():
        if not child.is_dir():
            continue
        m = ID_PATTERN.match(child.name)
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n

    new_n = max_n + 1
    slug = args.slug or "factor"
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", slug).strip("_").lower()
    factor_id = f"f{new_n:03d}_{slug}"
    print(factor_id)


# ---------------------------------------------------------------------------
# 子命令：resolve（缩写 / 前缀解析）
# ---------------------------------------------------------------------------
def cmd_resolve(args: argparse.Namespace) -> None:
    workspace = get_workspace_root()
    if not workspace.is_dir():
        print("ERROR: workspace 不存在", file=sys.stderr)
        sys.exit(1)

    candidates = sorted(p.name for p in workspace.iterdir() if p.is_dir() and ID_PATTERN.match(p.name))

    query = args.query
    matches: list[str] = []

    # 1. 完整 id 命中
    if query in candidates:
        matches = [query]
    else:
        # 2. 缩写：f3 / 003 / 3
        m_short = ID_SHORT.match(query)
        if m_short:
            n_str = m_short.group(1) or m_short.group(2)
            n = int(n_str)
            for cid in candidates:
                cm = ID_PATTERN.match(cid)
                if int(cm.group(1)) == n:
                    matches.append(cid)
                    break
        # 3. 唯一前缀
        if not matches:
            prefix_matches = [c for c in candidates if c.startswith(query)]
            matches = prefix_matches

    if len(matches) == 1:
        print(matches[0])
    elif len(matches) > 1:
        print(f"ERROR: 匹配到多个 {query}: {matches}", file=sys.stderr)
        sys.exit(2)
    else:
        print(f"ERROR: 未找到 {query}", file=sys.stderr)
        sys.exit(3)


# ---------------------------------------------------------------------------
# 子命令：show
# ---------------------------------------------------------------------------
def cmd_show(args: argparse.Namespace) -> None:
    factor_id = args.factor_id
    state = read_state(factor_id)
    print(json.dumps(state, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# 子命令：set-stage
# ---------------------------------------------------------------------------
def cmd_set_stage(args: argparse.Namespace) -> None:
    factor_id = args.factor_id
    stage = args.stage
    new_status = args.status  # running / done / skipped

    if stage not in STAGE_ORDER:
        raise ValueError(f"未知 stage: {stage}（应为 {STAGE_ORDER} 之一）")

    state = read_state(factor_id)
    state["stages"][stage] = new_status
    if new_status == "running":
        state["stage_attempts"][stage] = state["stage_attempts"].get(stage, 0) + 1
        state["current_stage"] = stage
    elif new_status == "done":
        # 推进到下一未完成的 stage
        idx = STAGE_ORDER.index(stage)
        for next_s in STAGE_ORDER[idx + 1:]:
            if state["stages"][next_s] in ("pending", None):
                state["current_stage"] = next_s
                state["stages"][next_s] = "running"
                break
        else:
            state["current_stage"] = None
    state["events"].append({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "type": "set_stage",
        "stage": stage,
        "status": new_status,
    })

    write_state(factor_id, state)
    print(f"[OK] {factor_id} stage {stage} -> {new_status}")


# ---------------------------------------------------------------------------
# 子命令：set（通用字段）
# ---------------------------------------------------------------------------
def cmd_set(args: argparse.Namespace) -> None:
    factor_id = args.factor_id
    field = args.field
    value = args.value

    state = read_state(factor_id)
    # 类型推断（极简）
    if value.lower() in ("true", "false"):
        typed: Any = value.lower() == "true"
    elif value.lower() in ("null", "none"):
        typed = None
    else:
        try:
            typed = int(value)
        except ValueError:
            try:
                typed = float(value)
            except ValueError:
                typed = value

    state[field] = typed
    state["events"].append({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "type": "set",
        "field": field,
        "value": str(typed),
    })
    write_state(factor_id, state)
    print(f"[OK] {factor_id} {field} = {typed!r}")


# ---------------------------------------------------------------------------
# 子命令：record-event
# ---------------------------------------------------------------------------
def cmd_record_event(args: argparse.Namespace) -> None:
    factor_id = args.factor_id
    event_type = args.event_type
    payload = json.loads(args.json) if args.json else {}

    state = read_state(factor_id)
    state["events"].append({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "type": event_type,
        **payload,
    })
    write_state(factor_id, state)
    print(f"[OK] {factor_id} recorded event {event_type}")


# ---------------------------------------------------------------------------
# 子命令：next-iteration（reject 后判断是否自动开新轮）
# ---------------------------------------------------------------------------
def cmd_next_iteration(args: argparse.Namespace) -> None:
    """reject 后检查 iteration budget：
    - 若 iteration_count < max_iterations：自动分配新 fNNN，方向沿用旧轮，count +1
    - 若已达上限：返回 "exhausted"，主会话停下汇报
    """
    old_id = args.factor_id
    old_state = read_state(old_id)

    # 读 .mine.json 的 max_iterations（若缺省 3）
    mine_json = Path.cwd() / ".mine.json"
    if mine_json.is_file():
        try:
            mine = json.loads(mine_json.read_text(encoding="utf-8"))
            max_iter = int(mine.get("max_iterations", 3))
        except (json.JSONDecodeError, OSError, ValueError):
            max_iter = 3
    else:
        max_iter = 3

    current = old_state.get("iteration_count", 0)
    direction = old_state.get("direction", "未指定方向")

    if current + 1 >= max_iter and max_iter > 0:
        # 已达上限，停下
        print(f"EXHAUSTED|已用完 {max_iter} 轮迭代（{old_id} 是第 {current + 1} 轮）")
        print(f"DIRECTION|{direction}")
        sys.exit(10)
    elif max_iter == 0:
        # 用户设了 0 轮 → 完全不自动迭代
        print(f"NO_AUTO|用户配置 max_iterations=0，每轮 reject 后停下")
        print(f"DIRECTION|{direction}")
        sys.exit(11)

    # 分配新 id
    workspace = get_workspace_root()
    max_n = 0
    for child in workspace.iterdir():
        if not child.is_dir():
            continue
        m = ID_PATTERN.match(child.name)
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    new_n = max_n + 1

    # 沿用旧轮的 slug 后缀 + 方向，或主会话传新 slug
    new_slug = args.slug or f"{old_state.get('slug', 'iter')}_iter{current + 2}"
    new_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", new_slug).strip("_").lower()
    new_id = f"f{new_n:03d}_{new_slug}"

    # 初始化新 state
    new_state = dict(DEFAULT_STATE)
    new_state["factor_id"] = new_id
    new_state["slug"] = new_slug
    new_state["direction"] = direction
    new_state["status"] = "running"
    new_state["current_stage"] = "propose"
    new_state["stages"]["propose"] = "running"
    new_state["iteration_count"] = current + 1
    new_state["max_iterations"] = max_iter
    new_state["created_at"] = datetime.now().isoformat(timespec="seconds")
    new_state["events"].append({
        "ts": new_state["created_at"],
        "type": "init_via_iteration",
        "from_factor": old_id,
        "reason": "auto-iteration after reject",
    })

    write_state(new_id, new_state)
    print(f"NEXT|{new_id}|{current + 2}/{max_iter}|{direction}")


# ---------------------------------------------------------------------------
# 子命令：list
# ---------------------------------------------------------------------------
def cmd_list(_: argparse.Namespace) -> None:
    workspace = get_workspace_root()
    if not workspace.is_dir():
        print("(空)")
        return
    ids = sorted(p.name for p in workspace.iterdir() if p.is_dir() and ID_PATTERN.match(p.name))
    for cid in ids:
        try:
            st = read_state(cid)
            print(f"{cid}\t{st['status']}\t{st.get('current_stage')}\t{st.get('direction', '')}")
        except Exception as e:  # noqa
            print(f"{cid}\tERROR\t{e}")


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="factormine state manager")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="初始化一轮新挖因子")
    p_init.add_argument("factor_id")
    p_init.add_argument("--direction", required=True, help="用户方向")
    p_init.set_defaults(func=cmd_init)

    p_next = sub.add_parser("next-id", help="分配下一个 fNNN_slug")
    p_next.add_argument("--slug", required=False, default=None)
    p_next.set_defaults(func=cmd_next_id)

    p_resolve = sub.add_parser("resolve", help="解析 id 缩写/前缀")
    p_resolve.add_argument("query")
    p_resolve.set_defaults(func=cmd_resolve)

    p_show = sub.add_parser("show", help="查看 state.json")
    p_show.add_argument("factor_id")
    p_show.set_defaults(func=cmd_show)

    p_ss = sub.add_parser("set-stage", help="更新 stage 状态")
    p_ss.add_argument("factor_id")
    p_ss.add_argument("stage")
    p_ss.add_argument("status", choices=["running", "done", "skipped"])
    p_ss.set_defaults(func=cmd_set_stage)

    p_set = sub.add_parser("set", help="通用字段更新")
    p_set.add_argument("factor_id")
    p_set.add_argument("field")
    p_set.add_argument("value")
    p_set.set_defaults(func=cmd_set)

    p_re = sub.add_parser("record-event", help="记录事件")
    p_re.add_argument("factor_id")
    p_re.add_argument("event_type")
    p_re.add_argument("--json", default="{}")
    p_re.set_defaults(func=cmd_record_event)

    p_list = sub.add_parser("list", help="列出全部 factor_id")
    p_list.set_defaults(func=cmd_list)

    p_ni = sub.add_parser("next-iteration", help="reject 后判断是否自动开新轮")
    p_ni.add_argument("factor_id")
    p_ni.add_argument("--slug", default=None, help="新轮 slug（缺省沿用旧+iterN）")
    p_ni.set_defaults(func=cmd_next_iteration)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()