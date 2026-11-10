#!/usr/bin/env python
"""紫微命盘本地存档：保存、读取、列出、删除。

存盘位置：``%USERPROFILE%\\.ziwei_skill\\profiles\\<slug>.json``。
保存的内容是 calculate_ziwei.py --json 的完整对象，读取后可直接渲染或继续解读。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

PROFILE_DIR = Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".ziwei_skill" / "profiles"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _read_stdin() -> str:
    return sys.stdin.read()


def _profile_path(slug: str) -> Path:
    if not SLUG_RE.match(slug):
        raise ValueError("slug 只能用小写字母、数字、下划线和短横线，且以字母或数字开头")
    return PROFILE_DIR / f"{slug}.json"


def _load_profile(slug: str) -> dict:
    path = _profile_path(slug)
    if not path.exists():
        raise FileNotFoundError(f"未找到命盘：{slug}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def cmd_save(args: argparse.Namespace) -> int:
    if args.data_file:
        with open(args.data_file, encoding="utf-8-sig") as handle:
            payload = handle.read()
    else:
        payload = _read_stdin()
    if not payload.strip():
        raise ValueError("没有收到命盘数据：请把 calculate_ziwei.py --json 的输出管道传入，或用 --data-file")
    data = json.loads(payload)
    if not isinstance(data, dict) or "chart" not in data or "birth" not in data:
        raise ValueError("命盘数据缺少 chart/birth 字段，确认是 calculate_ziwei.py 的输出")
    path = _profile_path(args.slug)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "slug": args.slug,
        "name": args.name,
        "memo": args.memo or "",
        "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "chart": data,
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
    print(f"已保存：{args.name}（{args.slug}） -> {path}")
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    record = _load_profile(args.slug)
    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    from ziwei_render import render_chart

    print(f"# {record['name']}　{record.get('memo') or ''}".rstrip())
    print(f"# 存档时间 {record['saved_at']}")
    color = args.color == "always" or (args.color == "auto" and sys.stdout.isatty())
    print(render_chart(record["chart"], color=color, detail=False), end="")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    if not PROFILE_DIR.exists():
        print("（暂无存档）")
        return 0
    rows = []
    for path in sorted(PROFILE_DIR.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        chart = record.get("chart", {})
        birth = chart.get("birth", {})
        info = chart.get("chart", {})
        rows.append((
            record.get("slug", path.stem),
            record.get("name", ""),
            birth.get("gender", ""),
            birth.get("solar", ""),
            birth.get("lunar", ""),
            info.get("bureau", ""),
            record.get("saved_at", ""),
        ))
    if not rows:
        print("（暂无存档）")
        return 0
    headers = ("slug", "姓名", "性别", "公历", "农历", "五行局", "存档时间")
    widths = [max(len(str(row[i])) for row in rows + [headers]) for i in range(len(headers))]
    print("  ".join(headers[i].ljust(widths[i]) for i in range(len(headers))))
    for row in rows:
        print("  ".join(str(row[i]).ljust(widths[i]) for i in range(len(headers))))
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    path = _profile_path(args.slug)
    if not path.exists():
        raise FileNotFoundError(f"未找到命盘：{args.slug}")
    if not args.yes:
        answer = input(f"确认删除 {args.slug}（{path}）？输入 yes 继续：").strip().lower()
        if answer != "yes":
            print("已取消")
            return 1
    path.unlink()
    print(f"已删除：{args.slug}")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(prog="store_ziwei.py", description="紫微命盘本地存档")
    sub = parser.add_subparsers(dest="command", required=True)

    save = sub.add_parser("save", help="保存命盘")
    save.add_argument("--name", required=True, help="命主称呼")
    save.add_argument("--slug", required=True, help="唯一标识（小写拼音/字母数字）")
    save.add_argument("--memo", default="", help="备注")
    save.add_argument("--data-file", default=None, help="从 UTF-8 文件读取命盘 JSON")
    save.set_defaults(func=cmd_save)

    load = sub.add_parser("load", help="读取命盘")
    load.add_argument("--slug", required=True)
    load.add_argument("--json", action="store_true", help="输出原始 JSON")
    load.add_argument("--color", choices=("auto", "always", "never"), default="auto")
    load.set_defaults(func=cmd_load)

    listing = sub.add_parser("list", help="列出全部命盘")
    listing.set_defaults(func=cmd_list)

    delete = sub.add_parser("delete", help="删除命盘")
    delete.add_argument("--slug", required=True)
    delete.add_argument("--yes", action="store_true", help="跳过确认")
    delete.set_defaults(func=cmd_delete)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 - CLI 统一错误输出
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
