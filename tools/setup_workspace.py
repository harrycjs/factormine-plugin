"""
setup_workspace.py — 首次使用配置向导（幂等可重跑）

按 `skills/mine/stages/setup.md` 执行：落地 `.mine.json` + 目录树 + 数据可用性自检。

使用：
    uv run python tools/setup_workspace.py \
        --target . \
        --data-root "D:\\local_data" \
        --pool 全A \
        --year-start 2016 \
        --year-end 2025 \
        --default-direction 混合 \
        --max-iterations 3
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup(
    target: Path,
    data_root: str,
    pool: str,
    year_start: int,
    year_end: int,
    default_direction: str,
    max_iterations: int = 3,
) -> None:
    target = target.resolve()

    # 1. 落地 .mine.json
    config = {
        "plugin_root": str(target),
        "data_root": data_root,
        "stock_pool": pool,
        "year_start": year_start,
        "year_end": year_end,
        "default_direction": default_direction,
        "max_iterations": max_iterations,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    (target / ".mine.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 落地 .mine.json -> {target / '.mine.json'}")
    print(f"     max_iterations = {max_iterations}（每方向自动迭代上限）")

    # 2. 目录树
    for sub in [
        "library/approved",
        "library/rejected",
        "library/failures",
        "library/lessons",
        "workspace",
        "templates",
        "common",
    ]:
        (target / sub).mkdir(parents=True, exist_ok=True)
    print(f"[OK] 目录树已建")

    # 3. 拷贝模板（如缺）
    src_templates = Path(__file__).resolve().parent.parent / "templates"
    dst_templates = target / "templates"
    if src_templates.is_dir():
        for f in src_templates.rglob("*"):
            if f.is_file():
                rel = f.relative_to(src_templates)
                dst = dst_templates / rel
                if not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dst)
        print(f"[OK] templates 已就绪 -> {dst_templates}")

    # 4. 拷贝 common 种子（如缺）
    src_common = Path(__file__).resolve().parent.parent / "common"
    dst_common = target / "common"
    if src_common.is_dir():
        for f in src_common.rglob("*"):
            if f.is_file() and f.suffix == ".py":
                rel = f.relative_to(src_common)
                dst = dst_common / rel
                if not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dst)
        print(f"[OK] common 已就绪 -> {dst_common}")

    # 5. 落地空骨架文件
    fl = target / "library" / "lessons" / "failure_lessons.md"
    if not fl.exists():
        fl.write_text(
            "# 失败教训笔记（failure_lessons）\n\n"
            "> 每次 `/mine reject` 由 factor-archivist **追加**（append）一节。不得覆盖。\n"
            "> 格式见 templates/failure_lessons_schema.md。\n\n"
            "## 种子条目（seed）\n\n"
            "本节由本插件自带，作为首轮 propose 的失败教训摘要：\n\n"
            "1. **未来函数**：用 `end_date` 而非 `info_publ_date` 对齐财务数据；样本内完美，OOS 完全失效。\n"
            "2. **未中性化的市值伪 alpha**：IC 极高但扣市值后归零。\n"
            "3. **未做 OOS 检验**：参数在样本内调优，OOS 反转。\n"
            "4. **换手未扣费**：毛收益 30% 年化，扣费后归零。\n"
            "5. **同类因子重复入库**：未与 INDEX.md 比对，相关性 > 0.9 仍入库。\n\n"
            "---\n\n",
            encoding="utf-8",
        )
        print(f"[OK] 落地空骨架 -> {fl}")

    sn = target / "library" / "lessons" / "success_notes.md"
    if not sn.exists():
        sn.write_text(
            "# 成功经验笔记（success_notes）\n\n"
            "> 每次 `/mine accept` 由 factor-archivist **追加**一节。\n\n"
            "## 种子条目（seed）\n\n"
            "（首次 accept 后填入）\n\n",
            encoding="utf-8",
        )

    idx = target / "library" / "approved" / "INDEX.md"
    if not idx.exists():
        idx.write_text(
            "# 因子库索引（approved）\n\n"
            "| factor_id | 方向 | 类别 | 关键指标 | 入库日期 |\n"
            "|-----------|------|------|----------|----------|\n"
            "（首次 accept 后追加）\n",
            encoding="utf-8",
        )

    # 6. 数据可用性自检
    data_root_path = Path(data_root).expanduser()
    if not data_root_path.is_dir():
        print(f"[WARN] 数据根目录不存在：{data_root_path}（请确认路径）")
        return

    parquet_files = sorted(p.name for p in data_root_path.glob("*.parquet"))
    if not parquet_files:
        print(f"[WARN] {data_root_path} 下无 parquet 文件")
        return

    print(f"\n[INFO] 数据根目录：{data_root_path}")
    print(f"[INFO] 发现 {len(parquet_files)} 个 parquet 文件：")
    stock_keywords = ("share_stock", "ashare_stock")
    has_stock_data = any(
        any(kw in name for kw in stock_keywords) and "price" in name or "trade" in name
        for name in parquet_files
    )
    for name in parquet_files:
        marker = "[*]" if any(kw in name for kw in stock_keywords) else "   "
        print(f"  {marker} {name}")

    if not has_stock_data:
        print("\n[WARN] 未发现个股行情/交易数据，请确认 data_root 是否正确")

    # 更新 data_catalog.md 的本机文件清单
    catalog = dst_templates / "data_catalog.md"
    if catalog.exists():
        text = catalog.read_text(encoding="utf-8")
        # 在 "本机实际文件清单" 段后追加
        section_marker = "## 本机实际文件清单"
        if section_marker in text:
            pre, post = text.split(section_marker, 1)
            new_section = section_marker + "\n\n"
            new_section += f"> 由 setup 自动扫描于 {datetime.now().isoformat(timespec='seconds')}\n\n"
            new_section += "```\n" + "\n".join(parquet_files) + "\n```\n"
            catalog.write_text(pre + new_section + post, encoding="utf-8")
            print(f"[OK] data_catalog.md 已更新本机文件清单")

    print("\n[OK] setup 完成")


def main() -> None:
    p = argparse.ArgumentParser(description="factormine setup_workspace")
    p.add_argument("--target", default=".", help="目标目录（默认 cwd）")
    p.add_argument("--data-root", required=True, help="本地 parquet 数据根目录")
    p.add_argument("--pool", default="全A", choices=["全A", "HS300", "ZZ500", "ZZ1000"])
    p.add_argument("--year-start", type=int, required=True)
    p.add_argument("--year-end", type=int, required=True)
    p.add_argument("--default-direction", default="混合", choices=["行情", "财务", "混合"])
    p.add_argument("--max-iterations", type=int, default=3, help="每方向自动迭代上限（0=不自动迭代；>0=达到上限自动停下）")
    args = p.parse_args()

    setup(
        target=Path(args.target),
        data_root=args.data_root,
        pool=args.pool,
        year_start=args.year_start,
        year_end=args.year_end,
        default_direction=args.default_direction,
        max_iterations=args.max_iterations,
    )


if __name__ == "__main__":
    main()