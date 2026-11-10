"""紫微斗数补遗规则：四化、杂曜、十二神、命主身主、流年宫位。

核心安星（命身宫、五行局、十四主星、六吉六煞、禄存天马、红鸾天喜、大限、小限）
由第三方库 ``ziwei`` 计算；本模块只补它没有覆盖的部分，所有公式都是纯函数。

规则依据《紫微斗数全书》与通行安星诀，并与 iztro 2.6.5（MIT）逐盘核对。
默认口径取通行派：四化用「全书」表、杂曜用通行三十八杂曜（含红鸾天喜）、十二神按阳男阴女顺行。
"""

from __future__ import annotations

from typing import Iterable

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

# ---------------------------------------------------------------- 基本工具


def gan_index(gan: str) -> int:
    return GAN.index(gan)


def zhi_index(zhi: str) -> int:
    return ZHI.index(zhi)


def shift(zhi: str, offset: int) -> str:
    """地支顺移 offset 宫（负数为逆）。"""
    return ZHI[(ZHI.index(zhi) + offset) % 12]


def is_forward(year_gan: str, gender: str) -> bool:
    """阳男阴女顺行，阴男阳女逆行。"""
    yang = GAN.index(year_gan) % 2 == 0
    male = gender == "男"
    return yang == male


# ---------------------------------------------------------------- 星曜分类

MAJOR_STARS = (
    "紫微", "天机", "太阳", "武曲", "天同", "廉贞",
    "天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军",
)
SOFT_STARS = ("左辅", "右弼", "文昌", "文曲", "天魁", "天钺")
TOUGH_STARS = ("擎羊", "陀罗", "火星", "铃星", "地空", "地劫")
FLOWER_STARS = ("红鸾", "天喜")

STAR_CATEGORY = {
    **{name: "major" for name in MAJOR_STARS},
    **{name: "soft" for name in SOFT_STARS},
    **{name: "tough" for name in TOUGH_STARS},
    "禄存": "lucun",
    "天马": "tianma",
    **{name: "flower" for name in FLOWER_STARS},
}

# ---------------------------------------------------------------- 四化

# 通行本（《紫微斗数全书》一系，iztro 默认）：禄、权、科、忌
SIHUA_QUANSHU = {
    "甲": ("廉贞", "破军", "武曲", "太阳"),
    "乙": ("天机", "天梁", "紫微", "太阴"),
    "丙": ("天同", "天机", "文昌", "廉贞"),
    "丁": ("太阴", "天同", "天机", "巨门"),
    "戊": ("贪狼", "太阴", "右弼", "天机"),
    "己": ("武曲", "贪狼", "天梁", "文曲"),
    "庚": ("太阳", "武曲", "太阴", "天同"),
    "辛": ("巨门", "太阳", "文曲", "文昌"),
    "壬": ("天梁", "紫微", "左辅", "武曲"),
    "癸": ("破军", "巨门", "太阴", "贪狼"),
}

# 中州派（王亭之讲义）异文：戊、庚、壬三干与通行本不同
SIHUA_ZHONGZHOU = {
    **SIHUA_QUANSHU,
    "戊": ("贪狼", "太阴", "太阳", "天机"),
    "庚": ("太阳", "武曲", "天府", "天同"),
    "壬": ("天梁", "紫微", "天府", "武曲"),
}

SIHUA_TABLES = {"quanshu": SIHUA_QUANSHU, "zhongzhou": SIHUA_ZHONGZHOU}
SIHUA_LABELS = ("禄", "权", "科", "忌")

# 禄存按年干（甲寅、乙卯、丙戊巳、丁己午、庚申、辛酉、壬亥、癸子）
LUCUN_BY_STEM = {
    "甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
    "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子",
}


def sihua(stem: str, variant: str = "quanshu") -> dict[str, str]:
    """返回某天干的生年／大限／流年四化：{禄:星, 权:星, 科:星, 忌:星}。"""
    table = SIHUA_TABLES[variant]
    return dict(zip(SIHUA_LABELS, table[stem]))


# ---------------------------------------------------------------- 命主身主

SOUL_STAR = {
    "子": "贪狼", "丑": "巨门", "寅": "禄存", "卯": "文曲",
    "辰": "廉贞", "巳": "武曲", "午": "破军", "未": "武曲",
    "申": "廉贞", "酉": "文曲", "戌": "禄存", "亥": "巨门",
}
BODY_STAR = {
    "子": "火星", "丑": "天相", "寅": "天梁", "卯": "天同",
    "辰": "文昌", "巳": "天机", "午": "火星", "未": "天相",
    "申": "天梁", "酉": "天同", "戌": "文昌", "亥": "天机",
}

# ---------------------------------------------------------------- 杂曜

# 年支三合组：寅午戌 / 申子辰 / 巳酉丑 / 亥卯未
_SANHE = ("寅午戌", "申子辰", "巳酉丑", "亥卯未")


def _sanhe_group(branch: str) -> str:
    for group in _SANHE:
        if branch in group:
            return group
    raise ValueError(f"非法地支：{branch}")


def minor_stars(
    year_gan: str,
    year_zhi: str,
    month: int,
    day: int,
    shichen: str,
    minggong: str,
    shengong: str,
    gender: str,
    variant: str = "quanshu",
) -> list[tuple[str, str]]:
    """按通行安星诀计算杂曜，返回 [(星名, 地支), ...]。

    month 是安星用的有效农历月（闰月已按所定口径折算），day 是农历日。
    天伤／天使在通行派恒居奴仆、疾厄；中州派阴男阳女互换。
    """
    out: list[tuple[str, str]] = []
    mi = zhi_index(year_zhi)
    month_idx = month - 1
    day_idx = day - 1
    hour_idx = zhi_index(shichen)

    # 年系
    out.append(("华盖", {"寅午戌": "戌", "申子辰": "辰", "巳酉丑": "丑", "亥卯未": "未"}[_sanhe_group(year_zhi)]))
    out.append(("咸池", {"寅午戌": "卯", "申子辰": "酉", "巳酉丑": "午", "亥卯未": "子"}[_sanhe_group(year_zhi)]))
    guchen, guasu = {
        "寅卯辰": ("巳", "丑"),
        "巳午未": ("申", "辰"),
        "申酉戌": ("亥", "未"),
        "亥子丑": ("寅", "戌"),
    }[next(g for g in ("寅卯辰", "巳午未", "申酉戌", "亥子丑") if year_zhi in g)]
    out += [("孤辰", guchen), ("寡宿", guasu)]
    out.append(("天才", shift(minggong, mi)))
    out.append(("天寿", shift(shengong, mi)))
    out.append(("龙池", shift("辰", mi)))
    out.append(("凤阁", shift("戌", -mi)))
    out.append(("天哭", shift("午", -mi)))
    out.append(("天虚", shift("午", mi)))
    out.append(("天德", shift("酉", mi)))
    out.append(("月德", shift("巳", mi)))
    out.append(("天空", shift(year_zhi, 1)))
    out.append(("年解", ZHI[(zhi_index("戌") - mi) % 12]))

    posui = ("巳", "丑", "酉")[mi % 3]
    out.append(("破碎", posui))
    out.append(("蜚廉", ("申", "酉", "戌", "巳", "午", "未", "寅", "卯", "辰", "亥", "子", "丑")[mi]))

    # 年干系
    gi = gan_index(year_gan)
    out.append(("天厨", ("巳", "午", "子", "巳", "午", "申", "寅", "午", "酉", "亥")[gi]))
    out.append(("天官", ("未", "辰", "巳", "寅", "卯", "酉", "亥", "酉", "戌", "午")[gi]))
    out.append(("天福", ("酉", "申", "子", "亥", "卯", "寅", "午", "巳", "午", "巳")[gi]))
    jielu = ("申", "午", "辰", "寅", "子")[gi % 5]
    kongwang = ("酉", "未", "巳", "卯", "丑")[gi % 5]
    if variant == "zhongzhou":
        # 中州派只有一颗截空：阳干取截路，阴干取空亡；另补龙德、劫煞、大耗三颗杂曜
        out.append(("截空", jielu if gi % 2 == 0 else kongwang))
        out.append(("龙德", shift(year_zhi, 7)))
        out.append(("劫煞", {"申子辰": "巳", "亥卯未": "申", "寅午戌": "亥", "巳酉丑": "寅"}[_sanhe_group(year_zhi)]))
        out.append(("大耗", ("未", "午", "酉", "申", "亥", "戌", "丑", "子", "卯", "寅", "巳", "辰")[mi]))
    else:
        out.append(("截路", jielu))
        out.append(("空亡", kongwang))

    # 旬空：以年支起，逆推至旬首，再补足阴阳
    xun = (mi + (gan_index("癸") - gi) + 1) % 12
    if xun % 2 != mi % 2:
        xun = (xun + 1) % 12
    out.append(("旬空", ZHI[xun]))

    # 月系
    out.append(("天刑", shift("酉", month_idx)))
    out.append(("天姚", shift("丑", month_idx)))
    out.append(("解神", ("申", "戌", "子", "寅", "辰", "午")[month_idx // 2]))
    out.append(("阴煞", ("寅", "子", "戌", "申", "午", "辰")[month_idx % 6]))
    out.append(("天月", ("戌", "巳", "辰", "寅", "未", "卯", "亥", "未", "寅", "午", "戌", "寅")[month_idx]))
    out.append(("天巫", ("巳", "申", "寅", "亥")[month_idx % 4]))

    # 日系：三台由左辅起初一顺行，八座由右弼起初一逆行，恩光天贵由昌曲起初一顺行再退一位
    zuo = shift("辰", month_idx)
    you = shift("戌", -month_idx)
    chang = shift("戌", -hour_idx)
    qu = shift("辰", hour_idx)
    out.append(("三台", shift(zuo, day_idx)))
    out.append(("八座", shift(you, -day_idx)))
    out.append(("恩光", shift(chang, day_idx - 1)))
    out.append(("天贵", shift(qu, day_idx - 1)))

    # 时系
    out.append(("台辅", shift("午", hour_idx)))
    out.append(("封诰", shift("寅", hour_idx)))

    # 天伤天使：通行派恒在奴仆、疾厄；中州派阴男阳女互换
    shang = shift(minggong, 5)
    shi = shift(minggong, 7)
    if variant == "zhongzhou" and not is_forward(year_gan, gender):
        shang, shi = shi, shang
    out += [("天伤", shang), ("天使", shi)]

    return out


# ---------------------------------------------------------------- 十二神

CHANGSHENG_12 = ("长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养")
BOSHI_12 = ("博士", "力士", "青龙", "小耗", "将军", "奏书", "飞廉", "喜神", "病符", "大耗", "伏兵", "官府")
JIANGQIAN_12 = ("将星", "攀鞍", "岁驿", "息神", "华盖", "劫煞", "灾煞", "天煞", "指背", "咸池", "月煞", "亡神")
SUIQIAN_12 = ("岁建", "晦气", "丧门", "贯索", "官符", "小耗", "大耗", "龙德", "白虎", "天德", "吊客", "病符")
SUIQIAN_12_ZHONGZHOU = ("岁建", "晦气", "丧门", "贯索", "官符", "小耗", "岁破", "龙德", "白虎", "天德", "吊客", "病符")

CHANGSHENG_START = {
    "水二局": "申",
    "木三局": "亥",
    "金四局": "巳",
    "土五局": "申",
    "火六局": "寅",
}


def _place_series(start: str, names: Iterable[str], forward: bool) -> dict[str, str]:
    step = 1 if forward else -1
    return {shift(start, step * i): name for i, name in enumerate(names)}


def twelve_gods(
    year_gan: str,
    year_zhi: str,
    gender: str,
    bureau: str,
    lucun: str,
    variant: str = "quanshu",
) -> dict[str, dict[str, str]]:
    """返回四组十二神：{长生成: {地支: 神名}, 博士: ..., 将前: ..., 岁前: ...}。"""
    forward = is_forward(year_gan, gender)
    jiang_start = {"寅午戌": "午", "申子辰": "子", "巳酉丑": "酉", "亥卯未": "卯"}[_sanhe_group(year_zhi)]
    suiqian = SUIQIAN_12_ZHONGZHOU if variant == "zhongzhou" else SUIQIAN_12
    return {
        "changsheng": _place_series(CHANGSHENG_START[bureau], CHANGSHENG_12, forward),
        "boshi": _place_series(lucun, BOSHI_12, forward),
        "jiangqian": _place_series(jiang_start, JIANGQIAN_12, True),
        "suiqian": _place_series(year_zhi, suiqian, True),
    }


# ---------------------------------------------------------------- 流年


def liunian_palaces(year_zhi: str) -> dict[str, str]:
    """流年十二宫：以流年支为流年命宫，逆布；返回 {地支: 流年宫名}。"""
    names = ("命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄",
             "迁移", "仆役", "官禄", "田宅", "福德", "父母")
    return {shift(year_zhi, -i): name for i, name in enumerate(names)}


def liunian_gods(year_zhi: str) -> dict[str, str]:
    """流年将前十二神与岁前十二神。"""
    jiang_start = {"寅午戌": "午", "申子辰": "子", "巳酉丑": "酉", "亥卯未": "卯"}[_sanhe_group(year_zhi)]
    return {
        "jiangqian": _place_series(jiang_start, JIANGQIAN_12, True),
        "suiqian": _place_series(year_zhi, SUIQIAN_12, True),
    }


def sanfang_sizheng(dizhi: str) -> tuple[str, str, str, str]:
    """本宫、两个三合宫、对宫。"""
    return dizhi, shift(dizhi, 4), shift(dizhi, 8), shift(dizhi, 6)


def opposite(dizhi: str) -> str:
    return shift(dizhi, 6)
