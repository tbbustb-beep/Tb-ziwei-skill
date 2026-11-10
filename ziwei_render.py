"""终端命盘渲染：十二宫格、四化、大限、流年摘要。

只读 calculate_ziwei.build_chart 产出的结果字典，不重新排盘。颜色可用 --color never 关闭。
"""

from __future__ import annotations

from unicodedata import east_asian_width

WIDTH = 22
GRID = (
    ("巳", "午", "未", "申"),
    ("辰", None, None, "酉"),
    ("卯", None, None, "戌"),
    ("寅", "丑", "子", "亥"),
)

STYLE = {
    "major": "1;33",
    "soft": "32",
    "tough": "31",
    "lucun": "36",
    "tianma": "36",
    "flower": "35",
    "minor": "90",
    "name": "1;37",
    "ganzhi": "37",
    "shen": "1;35",
    "flow": "1;34",
    "dim": "2;37",
    "title": "1;36",
    "mark_lu": "1;32",
    "mark_quan": "1;34",
    "mark_ke": "1;36",
    "mark_ji": "1;31",
}
MARK_STYLE = {"禄": "mark_lu", "权": "mark_quan", "科": "mark_ke", "忌": "mark_ji"}


def _width(text: str) -> int:
    return sum(2 if east_asian_width(char) in ("W", "F") else 1 for char in text)


def _paint(text: str, style: str | None, color: bool) -> str:
    if not color or not style:
        return text
    return f"\033[{STYLE[style]}m{text}\033[0m"


def _line(*segments: tuple[str, str | None]) -> list[tuple[str, str | None]]:
    return [(text, style) for text, style in segments if text]


def _join(items: list[tuple[str, str | None]], sep: str = " ") -> list[tuple[str, str | None]]:
    out: list[tuple[str, str | None]] = []
    for index, item in enumerate(items):
        if index:
            out.append((sep, None))
        out.append(item)
    return out


def _wrap(items: list[tuple[str, str | None]], limit: int = WIDTH - 2) -> list[list[tuple[str, str | None]]]:
    """把星名按可视宽度折行，返回若干行。"""
    lines: list[list[tuple[str, str | None]]] = []
    current: list[tuple[str, str | None]] = []
    current_width = 0
    for item in items:
        piece_width = _width(item[0])
        extra = piece_width + (1 if current else 0)
        if current and current_width + extra > limit:
            lines.append(current)
            current = [item]
            current_width = piece_width
        else:
            if current:
                current.append((" ", None))
                current_width += 1
            current.append(item)
            current_width += piece_width
    if current:
        lines.append(current)
    return lines


def _build_cell(palace: dict, liunian: dict | None, color: bool) -> list[list[tuple[str, str | None]]]:
    lines: list[list[tuple[str, str | None]]] = []

    head = [(palace["name"], "name"), (" ", None), (palace["ganzhi"], "ganzhi")]
    if palace.get("is_shengong"):
        head += [(" ", None), ("身", "shen")]
    if liunian and liunian["minggong"] == palace["dizhi"]:
        head += [(" ", None), ("流", "flow")]
    lines.append(head)

    majors = [s for s in palace["stars"] if s["category"] == "major"]
    if not majors:
        lines.append([("空宫", "dim")])
    for star in majors:
        text = star["name"] + (f"[{star['sihua']}]" if star.get("sihua") else "")
        seg: list[tuple[str, str | None]] = [(text, "major")]
        if star.get("brightness"):
            seg += [(" ", None), (star["brightness"], "dim")]
        lines.append(seg)

    others = [s for s in palace["stars"] if s["category"] in ("soft", "tough", "lucun", "tianma", "flower")]
    if others:
        segments: list[tuple[str, str | None]] = []
        for star in others:
            text = star["name"] + (f"[{star['sihua']}]" if star.get("sihua") else "")
            style = star["category"] if star["category"] in STYLE else "minor"
            segments.append((text, style))
        lines.extend(_wrap(_join(segments)))

    minors = [s for s in palace["stars"] if s["category"] == "minor"]
    if minors:
        segments = [(star["name"], "minor") for star in minors]
        lines.extend(_wrap(_join(segments)))

    decade = palace["decade"]
    tail: list[tuple[str, str | None]] = [
        (f"大限 {decade['start_age']}-{decade['end_age']}", "dim"),
    ]
    if palace.get("is_current_decade"):
        tail = [("▶ ", "flow")] + tail
    lines.append(tail)
    return lines


def _grid(palaces: dict[str, dict], liunian: dict | None, color: bool) -> str:
    cells = {branch: _build_cell(palaces[branch], liunian, color) for branch in palaces}
    height = max(len(cell) for cell in cells.values())
    for cell in cells.values():
        while len(cell) < height:
            cell.append([])

    def border(left: str, mid: str, right: str) -> str:
        return left + mid.join("─" * WIDTH for _ in range(4)) + right

    out = [border("┌", "┬", "┐")]
    for row in GRID:
        for index in range(height):
            parts = []
            for branch in row:
                if branch is None:
                    parts.append(" " * WIDTH)
                    continue
                line = cells[branch][index]
                plain = "".join(text for text, _ in line)
                padding = WIDTH - 2 - _width(plain)
                painted = "".join(_paint(text, style, color) for text, style in line)
                parts.append(" " + painted + " " * max(padding, 0) + " ")
            out.append("│" + "│".join(parts) + "│")
        if row is GRID[-1]:
            out.append(border("└", "┴", "┘"))
        else:
            out.append(border("├", "┼", "┤"))
    return "\n".join(out)


def _sihua_text(sihua: dict[str, str], color: bool) -> str:
    order = ("禄", "权", "科", "忌")
    parts = []
    for label in order:
        star = sihua.get(label)
        if star:
            parts.append(f"{star}[{label}]")
    return " ".join(parts)


def _detail(result: dict, color: bool) -> str:
    lines = ["", "【逐宫明细】"]
    for palace in result["chart"]["palaces"]:
        flags = []
        if palace.get("is_shengong"):
            flags.append("身宫")
        if palace.get("is_current_decade"):
            flags.append("当前大限")
        head = f"{palace['name']} {palace['ganzhi']}"
        if flags:
            head += "（" + "、".join(flags) + "）"
        lines.append("")
        lines.append(head)

        majors = [f"{s['name']}（{s.get('brightness') or '—'}）" for s in palace["stars"] if s["category"] == "major"]
        lines.append("  主星：" + ("、".join(majors) if majors else "空宫（借对宫 " + palace["opposite"] + "）"))
        soft = [s["name"] for s in palace["stars"] if s["category"] == "soft"]
        tough = [s["name"] for s in palace["stars"] if s["category"] == "tough"]
        lucky = [s["name"] for s in palace["stars"] if s["category"] in ("lucun", "tianma", "flower")]
        minor = [s["name"] for s in palace["stars"] if s["category"] == "minor"]
        lines.append("  吉星：" + ("、".join(soft) if soft else "—") + "　煞星：" + ("、".join(tough) if tough else "—"))
        lines.append("  禄马桃花：" + ("、".join(lucky) if lucky else "—"))
        lines.append("  杂曜：" + ("、".join(minor) if minor else "—"))
        sihua = palace.get("sihua") or {}
        if sihua:
            lines.append("  四化：" + "、".join(f"{star}[{label}]" for label, star in sihua.items()))
        lines.append(
            f"  长生：{palace['changsheng12']}　博士：{palace['boshi12']}"
            f"　将前：{palace['jiangqian12']}　岁前：{palace['suiqian12']}"
        )
        decade = palace["decade"]
        lines.append(f"  大限：{decade['start_age']}-{decade['end_age']} {decade['ganzhi']}"
                     f"　小限虚岁：{','.join(str(age) for age in palace['xiaoxian_ages'])}")
        lines.append("  三方四正：" + " / ".join(palace["sanfang_sizheng"]))
    return "\n".join(lines)


def _palace_label(name: str) -> str:
    return name if name.endswith("宫") else name + "宫"


def render_chart(result: dict, *, color: bool = False, detail: bool = False) -> str:
    birth = result["birth"]
    chart = result["chart"]
    liunian = result.get("liunian")

    title = "紫微斗数 · 本命盘"
    if liunian:
        title += f" · 流年 {liunian['year']} {liunian['ganzhi']}"
    head = [
        _paint(title, "title", color),
        "",
        f"命主 {chart['soul']}　身主 {chart['body']}　{chart['bureau']}　{chart['yin_yang']}"
        f"　大限{chart['direction']} {chart['first_decade_age']}岁起",
    ]
    name_text = (birth.get("name") + "　") if birth.get("name") else ""
    head.append(
        f"{name_text}{birth['gender']}　公历 {birth['solar']}（{birth['shichen']}时）"
        f"　农历 {birth['lunar']}"
    )
    extra = [f"生肖{birth['zodiac']}", f"{birth['constellation']}座"]
    if birth.get("birth_place"):
        extra.insert(0, birth["birth_place"] + (f"（东经{birth['longitude']:.2f}°）" if birth.get("longitude") else ""))
    extra.append("真太阳时已校正" if birth["true_solar_time"] else "真太阳时未校正")
    head.append("　".join(extra))

    # 宫位按地支索引
    palaces = {palace["dizhi"]: palace for palace in chart["palaces"]}
    body = _grid(palaces, liunian, color)

    foot = ["", "生年四化：" + _sihua_text(chart["sihua"], color)]
    if liunian:
        daxian = liunian.get("daxian")
        if daxian:
            foot.append(
                f"当前大限：{daxian['start_age']}-{daxian['end_age']} {daxian['ganzhi']}"
                f"（本命{_palace_label(daxian['palace'])}）　大限四化：" + _sihua_text(daxian["sihua"], color)
            )
        foot.append(
            f"流年：{liunian['ganzhi']}年 虚岁{liunian['age']}"
            f"　流年命宫 {liunian['minggong']}（本命{_palace_label(liunian['minggong_natal_palace'])}）"
            f"　小限 {liunian['xiaoxian']}（本命{_palace_label(liunian['xiaoxian_natal_palace'])}）"
        )
        foot.append("流年四化：" + _sihua_text(liunian["sihua"], color))
        foot.append(
            "流年禄存：" + liunian["lucun"] + f"　流羊：{liunian['qingyang']}　流陀：{liunian['tuoluo']}"
        )

    text = "\n".join(head) + "\n" + body + "\n" + "\n".join(foot) + "\n"
    if detail:
        text += _detail(result, color) + "\n"
    return text
