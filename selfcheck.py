#!/usr/bin/env python
"""自检：用 references/charts.json 核对排盘结果。

参照盘由 iztro 2.6.5（MIT）按同一通行口径生成，覆盖普通盘、晚子时、闰二月与 1955 年早盘。
运行：python selfcheck.py [-v]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import calculate_ziwei as C

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "references" / "charts.json"


def _groups(palace: dict) -> tuple[set[str], set[str], set[str]]:
    g = palace["star_groups"]
    major = set(g["major"])
    minor = set(g["soft"] + g["tough"] + g["lucun"] + g["tianma"])
    adj = set(g["flower"] + g["minor"])
    return major, minor, adj


def check_one(case: dict, verbose: bool) -> list[str]:
    problems: list[str] = []
    result = C.build_chart(C.parse_params(case["input"]))
    chart = result["chart"]
    expect = case["expect"]

    for key, mine in (
        ("minggong", chart["minggong"]),
        ("shengong", chart["shengong"]),
        ("bureau", chart["bureau"]),
        ("soul", chart["soul"]),
        ("body", chart["body"]),
    ):
        if mine != expect[key]:
            problems.append(f"{key}: 得到 {mine}，应为 {expect[key]}")

    if chart["sihua"] != expect["sihua"]:
        problems.append(f"四化：得到 {chart['sihua']}，应为 {expect['sihua']}")

    palaces = {p["dizhi"]: p for p in chart["palaces"]}
    for branch, want in expect["palaces"].items():
        mine = palaces[branch]
        major, minor, adj = _groups(mine)
        if major != set(want["major"]):
            problems.append(f"{branch} 主星：{sorted(major)} ≠ {sorted(want['major'])}")
        if minor != set(want["minor"]):
            problems.append(f"{branch} 辅煞：{sorted(minor)} ≠ {sorted(want['minor'])}")
        if adj != set(want["adj"]):
            problems.append(
                f"{branch} 杂曜：多 {sorted(adj - set(want['adj']))}，少 {sorted(set(want['adj']) - adj)}"
            )
        for field, want_key in (
            ("changsheng12", "changsheng12"),
            ("boshi12", "boshi12"),
            ("jiangqian12", "jiangqian12"),
            ("suiqian12", "suiqian12"),
        ):
            if mine[field] != want[want_key]:
                problems.append(f"{branch} {field}：{mine[field]} ≠ {want[want_key]}")
        got_range = [mine["decade"]["start_age"], mine["decade"]["end_age"]]
        if got_range != list(want["decade"]):
            problems.append(f"{branch} 大限：{got_range} ≠ {want['decade']}")
        if mine["xiaoxian_ages"][:3] != list(want["ages"]):
            problems.append(f"{branch} 小限：{mine['xiaoxian_ages'][:3]} ≠ {want['ages']}")

    if verbose:
        print(f"  {chart['minggong']}宫 {chart['bureau']} 命主{chart['soul']} 身主{chart['body']}")
    return problems


def main(argv: list[str] | None = None) -> int:
    verbose = "-v" in (argv or sys.argv[1:])
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    failures = 0
    for index, case in enumerate(cases, 1):
        title = case.get("title", "")
        try:
            problems = check_one(case, verbose)
        except Exception as exc:  # noqa: BLE001 - 自检需要报告所有失败
            problems = [f"运行失败：{type(exc).__name__}: {exc}"]
        if problems:
            failures += 1
            print(f"[FAIL] {index}. {title}")
            for problem in problems[:12]:
                print("   -", problem)
            if len(problems) > 12:
                print(f"   …共 {len(problems)} 处差异")
        else:
            print(f"[ OK ] {index}. {title}")
    print(f"\n{len(cases) - failures}/{len(cases)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
