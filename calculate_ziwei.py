#!/usr/bin/env python
"""紫微斗数排盘：从 stdin 读 JSON 参数，输出完整命盘 JSON 或终端命盘。

核心安星（农历、命身宫、五行局、十四主星、六吉六煞、禄存天马、大限、小限）
调用 ``ziwei`` 库；四化、杂曜、十二神、命主身主、流年宫位由 ``ziwei_rules`` 补齐。

用法：
    '{"year":2000,"month":8,"day":16,"hour":2,"minute":30,"gender":"女","birth_place":"四川成都"}' |
        python calculate_ziwei.py --json

注意：Windows PowerShell 下 JSON 必须走 stdin，不要拼成命令行参数。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, time, timedelta
from importlib.metadata import version as pkg_version

from ziwei.birth import Gender, GregorianBirthRecord, LunarBirthRecord, TimePrecision
from ziwei.brightness import BrightnessTable, star_brightness
from ziwei.chart import create_chart
from ziwei.config import ChartConfig, DayRollover, LeapMonthPolicy, TianmaRule, YearBoundary
from ziwei.ganzhi import Dizhi, year_ganzhi
from ziwei.palaces import effective_month
from ziwei.sihua import SihuaVariant
from ziwei.timezone import FixedOffset, IanaTimezone

import ziwei_rules as R
from cities import DEFAULT_TIMEZONE, lookup_city

SCHEMA = "ziwei-skill/chart/v1"

GENDER_MAP = {
    "男": "男", "m": "男", "male": "男", "乾": "男", "1": "男",
    "女": "女", "f": "女", "female": "女", "坤": "女", "0": "女",
}
CALENDAR_MAP = {
    "gregorian": "gregorian", "solar": "gregorian", "公历": "gregorian", "阳历": "gregorian",
    "lunar": "lunar", "农历": "lunar", "阴历": "lunar",
}
SIHUA_MAP = {
    "quanshu": "quanshu", "全书": "quanshu", "通行": "quanshu", "默认": "quanshu",
    "zhongzhou": "zhongzhou", "中州": "zhongzhou", "中州派": "zhongzhou", "王亭之": "zhongzhou",
}

LEAP_MAP = {
    "split": LeapMonthPolicy.SPLIT_MONTH, "split_month": LeapMonthPolicy.SPLIT_MONTH,
    "前半归本月后半归下月": LeapMonthPolicy.SPLIT_MONTH,
    "current": LeapMonthPolicy.CURRENT_MONTH, "current_month": LeapMonthPolicy.CURRENT_MONTH,
    "本月": LeapMonthPolicy.CURRENT_MONTH,
    "next": LeapMonthPolicy.NEXT_MONTH, "next_month": LeapMonthPolicy.NEXT_MONTH,
    "下月": LeapMonthPolicy.NEXT_MONTH,
}
ROLLOVER_MAP = {
    "forward": DayRollover.LATE_ZI_NEXT_DAY, "next_day": DayRollover.LATE_ZI_NEXT_DAY,
    "晚子归次日": DayRollover.LATE_ZI_NEXT_DAY,
    "current": DayRollover.SAME_CIVIL_DAY, "same_day": DayRollover.SAME_CIVIL_DAY,
    "早晚子同日": DayRollover.SAME_CIVIL_DAY,
}
YEAR_MAP = {
    "lunar_new_year": YearBoundary.LUNAR_NEW_YEAR, "lunar": YearBoundary.LUNAR_NEW_YEAR,
    "正月初一": YearBoundary.LUNAR_NEW_YEAR,
    "lichun": YearBoundary.LICHUN, "立春": YearBoundary.LICHUN,
}
TIANMA_MAP = {
    "year": TianmaRule.YEAR_BRANCH, "年支": TianmaRule.YEAR_BRANCH,
    "month": TianmaRule.MONTH_BRANCH, "月支": TianmaRule.MONTH_BRANCH,
}

ZHI = R.ZHI
SHICHEN_MIDPOINT = {
    "子": 0, "丑": 2, "寅": 4, "卯": 6, "辰": 8, "巳": 10,
    "午": 12, "未": 14, "申": 16, "酉": 18, "戌": 20, "亥": 22,
}
SHICHEN_RANGE = {
    "子": "23:00-01:00", "丑": "01:00-03:00", "寅": "03:00-05:00",
    "卯": "05:00-07:00", "辰": "07:00-09:00", "巳": "09:00-11:00",
    "午": "11:00-13:00", "未": "13:00-15:00", "申": "15:00-17:00",
    "酉": "17:00-19:00", "戌": "19:00-21:00", "亥": "21:00-23:00",
}
ZODIAC = dict(zip(ZHI, "鼠牛虎兔龙蛇马羊猴鸡狗猪"))
BRIGHT_SHORT = {
    "庙": "庙", "旺": "旺", "得地": "得", "利益": "利",
    "平和": "平", "不得地": "不", "落陷": "陷",
}
PALACE_NAME_MODERN = {"妻妾": "夫妻", "奴仆": "仆役"}

CN_DIGITS = "一二三四五六七八九十"
CN_MONTH = {
    1: "正月", 2: "二月", 3: "三月", 4: "四月", 5: "五月", 6: "六月",
    7: "七月", 8: "八月", 9: "九月", 10: "十月", 11: "十一月", 12: "十二月",
}


# ------------------------------------------------------------------ 小工具


def cn_day(day: int) -> str:
    if day <= 10:
        return "初" + CN_DIGITS[day - 1]
    if day < 20:
        return "十" + CN_DIGITS[day - 11]
    if day == 20:
        return "二十"
    if day < 30:
        return "廿" + CN_DIGITS[day - 21]
    return "三十"


def gz_text(gan: str, zhi: str) -> str:
    return gan + zhi


def normalize_shichen(value) -> str:
    if isinstance(value, int) and 0 <= value <= 11:
        return ZHI[value]
    text = str(value).strip()
    text = text.replace("时", "").replace("時", "")
    aliases = {"子": "子", "丑": "丑", "寅": "寅", "卯": "卯", "辰": "辰", "巳": "巳",
               "午": "午", "未": "未", "申": "申", "酉": "酉", "戌": "戌", "亥": "亥"}
    if text in aliases:
        return aliases[text]
    if text.isdigit() and 0 <= int(text) <= 11:
        return ZHI[int(text)]
    raise ValueError(f"无法识别的时辰：{value!r}（可用 子丑寅卯辰巳午未申酉戌亥 或 0-11）")


def normalize_gender(value) -> str:
    key = str(value).strip().lower()
    if key in GENDER_MAP:
        return GENDER_MAP[key]
    raise ValueError(f"无法识别的性别：{value!r}（可用 男/女 或 M/F）")


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "1", "yes", "y", "是", "真", "开启", "on"):
            return True
        if text in ("false", "0", "no", "n", "否", "假", "关闭", "off", ""):
            return False
    raise ValueError(f"无法识别的布尔值：{value!r}")


def as_int(raw: dict, key: str, *, required: bool = True, default=None,
           lo: int | None = None, hi: int | None = None) -> int | None:
    if key not in raw or raw[key] is None or raw[key] == "":
        if required and default is None:
            raise ValueError(f"缺少必填字段：{key}")
        return default
    value = raw[key]
    if isinstance(value, bool):
        raise ValueError(f"{key} 必须是整数")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} 必须是整数，收到 {value!r}") from exc
    if lo is not None and number < lo:
        raise ValueError(f"{key} 不能小于 {lo}")
    if hi is not None and number > hi:
        raise ValueError(f"{key} 不能大于 {hi}")
    return number


def make_timezone(text: str):
    text = text.strip()
    if text.upper().startswith("UTC") or text.startswith("+") or text.startswith("-"):
        raw = text.upper().replace("UTC", "").replace("GMT", "").strip()
        sign = -1 if raw.startswith("-") else 1
        raw = raw.lstrip("+-")
        if not raw:
            raise ValueError(f"无法识别的时区：{text!r}")
        parts = raw.split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        return FixedOffset(timedelta(minutes=sign * (hours * 60 + minutes)))
    return IanaTimezone(text)


def lunar_text(year_gan: str, year_zhi: str, month: int, day: int, leap: bool, shichen: str) -> str:
    leap_text = "闰" if leap else ""
    return f"{year_gan}{year_zhi}年{leap_text}{CN_MONTH[month]}{cn_day(day)} {shichen}时"


def constellation(month: int, day: int) -> str:
    starts = (
        (1, 20, "水瓶"), (2, 19, "双鱼"), (3, 21, "白羊"), (4, 20, "金牛"),
        (5, 21, "双子"), (6, 22, "巨蟹"), (7, 23, "狮子"), (8, 23, "处女"),
        (9, 23, "天秤"), (10, 24, "天蝎"), (11, 23, "射手"), (12, 22, "摩羯"),
    )
    for m, d, name in reversed(starts):
        if (month, day) >= (m, d):
            return name
    return "摩羯"


# ------------------------------------------------------------------ 参数解析


def parse_params(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("stdin 必须是 JSON 对象")

    calendar = CALENDAR_MAP.get(str(raw.get("calendar_type", "gregorian")).strip().lower())
    if calendar is None:
        raise ValueError("calendar_type 只支持 gregorian / lunar")

    gender = normalize_gender(raw.get("gender"))
    year = as_int(raw, "year", lo=1600, hi=2199)
    month = as_int(raw, "month", lo=1, hi=12)
    day = as_int(raw, "day", lo=1, hi=31)

    hour_raw = raw.get("hour")
    shichen_raw = raw.get("shichen")

    hour: int | None = None
    minute = 0
    if hour_raw not in (None, ""):
        hour = as_int(raw, "hour", lo=0, hi=23)
        minute = as_int(raw, "minute", required=False, default=0, lo=0, hi=59)

    given_shichen = None
    if shichen_raw not in (None, ""):
        given_shichen = normalize_shichen(shichen_raw)

    if hour is not None:
        shichen = ZHI[((hour + 1) // 2) % 12]
        if given_shichen and given_shichen != shichen:
            raise ValueError(
                f"shichen={given_shichen} 与 hour={hour} 不在同一时辰，请只提供其中一个"
            )
    elif given_shichen:
        shichen = given_shichen
        hour = SHICHEN_MIDPOINT[shichen]
        minute = 30
    else:
        raise ValueError("紫微斗数排盘必须知道出生时辰：请提供 hour/minute，或直接给 shichen")

    place = str(raw.get("birth_place") or raw.get("place") or "").strip()
    true_solar = as_bool(raw.get("true_solar_time", False))
    is_leap = as_bool(raw.get("is_leap_month", False))

    longitude = raw.get("longitude")
    if longitude is not None and longitude != "":
        longitude = float(longitude)
        if not -180 <= longitude <= 180:
            raise ValueError("longitude 须在 -180 到 180 之间（东经为正）")

    timezone_text = str(raw.get("timezone") or "").strip()
    city_name = None
    city_lon = None
    city_tz = None
    if place:
        hit = lookup_city(place)
        if hit:
            city_name, city_lon, city_tz = hit
            if longitude is None:
                longitude = city_lon
        elif true_solar and longitude is None:
            try:
                from geopy.geocoders import Nominatim  # type: ignore

                geo = Nominatim(user_agent="Tb-ziwei-skill/1.0")
                location = geo.geocode(place, timeout=8)
                if location is None:
                    raise LookupError(place)
                longitude = float(location.longitude)
                city_name = place
                city_lon = longitude
            except Exception as exc:  # noqa: BLE001 - 网络失败时给出可操作提示
                raise ValueError(
                    f"无法解析出生地「{place}」的经度：内置城市表未收录，"
                    "联网解析也不可用。请改传 longitude（东经为正），"
                    "或关闭 true_solar_time。"
                ) from exc

    if timezone_text:
        tz = make_timezone(timezone_text)
        tz_text = timezone_text
    elif city_tz:
        tz = make_timezone(city_tz)
        tz_text = city_tz
    else:
        tz = make_timezone(DEFAULT_TIMEZONE)
        tz_text = DEFAULT_TIMEZONE

    if true_solar:
        if calendar == "lunar":
            raise ValueError("农历输入无法做真太阳时校正；请改用公历日期 + 时分，或关闭 true_solar_time")
        if longitude is None:
            raise ValueError("true_solar_time 需要出生地经度：请提供 birth_place 或 longitude")

    school = SIHUA_MAP.get(
        str(raw.get("school") or raw.get("sihua") or "quanshu").strip().lower()
    )
    if school is None:
        raise ValueError("school 只支持 quanshu（通行/全书）或 zhongzhou（中州派）")
    leap_policy = LEAP_MAP.get(str(raw.get("leap_month_policy", "split")).strip().lower())
    if leap_policy is None:
        raise ValueError("leap_month_policy 只支持 split / current / next")
    rollover = ROLLOVER_MAP.get(str(raw.get("day_rollover", "forward")).strip().lower())
    if rollover is None:
        raise ValueError("day_rollover 只支持 forward / current")
    year_boundary = YEAR_MAP.get(str(raw.get("year_boundary", "lunar_new_year")).strip().lower())
    if year_boundary is None:
        raise ValueError("year_boundary 只支持 lunar_new_year / lichun")
    tianma = TIANMA_MAP.get(str(raw.get("tianma", "year")).strip().lower())
    if tianma is None:
        raise ValueError("tianma 只支持 year / month")

    target_year = as_int(raw, "target_year", required=False, default=None, lo=1600, hi=2199)

    return {
        "name": str(raw.get("name") or "").strip(),
        "calendar": calendar,
        "year": year,
        "month": month,
        "day": day,
        "hour": hour,
        "minute": minute,
        "shichen": shichen,
        "gender": gender,
        "place": place,
        "city_name": city_name,
        "longitude": longitude,
        "city_longitude": city_lon,
        "timezone": tz,
        "timezone_text": tz_text,
        "true_solar_time": true_solar,
        "is_leap_month": is_leap,
        "school": school,
        "leap_policy": leap_policy,
        "rollover": rollover,
        "year_boundary": year_boundary,
        "tianma": tianma,
        "target_year": target_year,
    }


# ------------------------------------------------------------------ 排盘


def build_chart(params: dict) -> dict:
    if params["calendar"] == "gregorian":
        try:
            birth_date = date(params["year"], params["month"], params["day"])
        except ValueError as exc:
            raise ValueError(
                f"公历日期不存在：{params['year']}-{params['month']}-{params['day']}，请检查年月日"
            ) from exc
        birth_time = time(params["hour"], params["minute"])
        precision = TimePrecision.分 if params["minute"] else TimePrecision.时
        longitude = params["longitude"] if params["true_solar_time"] else None
        record = GregorianBirthRecord(
            birth_date=birth_date,
            birth_time=birth_time,
            time_precision=precision,
            timezone=params["timezone"],
            gender=Gender(params["gender"]),
            longitude_deg=longitude,
            place=params["place"] or None,
        )
    else:
        record = LunarBirthRecord(
            year=params["year"],
            month=params["month"],
            day=params["day"],
            is_leap_month=params["is_leap_month"],
            shichen=Dizhi(params["shichen"]),
            gender=Gender(params["gender"]),
            place=params["place"] or None,
        )

    config = ChartConfig(
        leap_month_policy=params["leap_policy"],
        day_rollover=params["rollover"],
        year_boundary=params["year_boundary"],
        tianma_rule=params["tianma"],
    )
    # 库内四化表只用于满足构造器校验；对外四化统一走 ziwei_rules 的表，
    # 因此这里固定选一套，不随用户口径变化。
    try:
        chart = create_chart(record, config, sihua_variant=SihuaVariant.排命盘口诀转录)
    except ValueError as exc:
        if "1972" in str(exc):
            raise ValueError(
                "该年份早于 1972 年：真太阳时与立春换年需要现代时标。"
                "请关闭 true_solar_time，并将 year_boundary 设为 lunar_new_year（农历正月初一）。"
            ) from exc
        raise
    calc = chart.calculation

    year_gan = calc.year_ganzhi.tiangan.value
    year_zhi = calc.year_ganzhi.dizhi.value
    minggong = chart.palaces[0].dizhi.value
    shengong = chart.shengong.value
    shichen = calc.shichen.value
    month_eff = effective_month(calc.month, calc.day, calc.is_leap_month, params["leap_policy"])

    sihua = R.sihua(year_gan, params["school"])
    star_pos = {p.star.value: p.dizhi.value for p in chart.stars}
    brightness = {}
    for p in chart.stars:
        if p.star.value in R.MAJOR_STARS:
            reading = star_brightness(p.star, p.dizhi, table=BrightnessTable.全书卷二录文)
            brightness[p.star.value] = BRIGHT_SHORT[reading.level.value]

    minor = R.minor_stars(
        year_gan, year_zhi, month_eff, calc.day, shichen,
        minggong, shengong, params["gender"], params["school"],
    )
    minor_by_branch: dict[str, list[str]] = {z: [] for z in ZHI}
    for name, branch in minor:
        minor_by_branch[branch].append(name)

    gods = R.twelve_gods(
        year_gan, year_zhi, params["gender"], chart.bureau.value,
        star_pos["禄存"], params["school"],
    )

    xiaoxian_start = {
        "寅午戌": "辰", "申子辰": "戌", "巳酉丑": "未", "亥卯未": "丑",
    }[next(g for g in ("寅午戌", "申子辰", "巳酉丑", "亥卯未") if year_zhi in g)]
    xx_step = 1 if params["gender"] == "男" else -1

    def xiaoxian_branch(age: int) -> str:
        return R.shift(xiaoxian_start, xx_step * (age - 1))

    def xiaoxian_ages(branch: str) -> list[int]:
        base = (R.zhi_index(branch) - R.zhi_index(xiaoxian_start)) * xx_step % 12
        return [base + 1 + 12 * k for k in range(10) if base + 1 + 12 * k <= 120]

    decades = {d.dizhi.value: d for d in chart.decades}
    sihua_positions = {
        label: {"star": star, "dizhi": star_pos[star], "palace": None}
        for label, star in sihua.items()
    }

    palaces = []
    for palace in chart.palaces:
        branch = palace.dizhi.value
        name = PALACE_NAME_MODERN.get(palace.name.value, palace.name.value)
        decade = decades[branch]
        decade_sihua = R.sihua(palace.tiangan.value, params["school"])
        stars = []
        for p in chart.stars:
            if p.dizhi.value != branch:
                continue
            label = None
            for key, star in sihua.items():
                if star == p.star.value:
                    label = key
            stars.append({
                "name": p.star.value,
                "category": R.STAR_CATEGORY.get(p.star.value, "minor"),
                "brightness": brightness.get(p.star.value),
                "sihua": label,
            })
        for star_name in minor_by_branch[branch]:
            stars.append({"name": star_name, "category": "minor", "brightness": None, "sihua": None})
        sihua_positions_here = {label: star for label, star in sihua.items() if star_pos[star] == branch}
        palaces.append({
            "name": name,
            "dizhi": branch,
            "ganzhi": palace.ganzhi.tiangan.value + branch,
            "is_minggong": palace.name.value == "命宫",
            "is_shengong": branch == shengong,
            "stars": stars,
            "star_groups": {
                "major": [s["name"] for s in stars if s["category"] == "major"],
                "soft": [s["name"] for s in stars if s["category"] == "soft"],
                "tough": [s["name"] for s in stars if s["category"] == "tough"],
                "lucun": [s["name"] for s in stars if s["category"] == "lucun"],
                "tianma": [s["name"] for s in stars if s["category"] == "tianma"],
                "flower": [s["name"] for s in stars if s["category"] == "flower"],
                "minor": [s["name"] for s in stars if s["category"] == "minor"],
            },
            "sihua": sihua_positions_here,
            "changsheng12": gods["changsheng"][branch],
            "boshi12": gods["boshi"][branch],
            "jiangqian12": gods["jiangqian"][branch],
            "suiqian12": gods["suiqian"][branch],
            "sanfang_sizheng": list(R.sanfang_sizheng(branch)),
            "opposite": R.opposite(branch),
            "decade": {
                "start_age": decade.start_age,
                "end_age": decade.end_age,
                "ganzhi": palace.ganzhi.tiangan.value + branch,
                "sihua": decade_sihua,
            },
            "xiaoxian_ages": xiaoxian_ages(branch),
        })

    for info in sihua_positions.values():
        info["palace"] = next(p["name"] for p in palaces if p["dizhi"] == info["dizhi"])
        info["opposite_dizhi"] = R.opposite(info["dizhi"])
        info["opposite_palace"] = next(
            p["name"] for p in palaces if p["dizhi"] == info["opposite_dizhi"]
        )

    # 公历/农历对照
    if params["calendar"] == "gregorian":
        solar_date = date(params["year"], params["month"], params["day"])
        lunar_year, lunar_month, lunar_day, lunar_leap = (
            calc.lunar_year, calc.month, calc.day, calc.is_leap_month,
        )
    else:
        from ziwei.calendar import LunarAlgorithm, lunar_to_gregorian

        solar_date = lunar_to_gregorian(
            LunarAlgorithm.ALGO3, params["year"], params["month"], params["day"],
            params["is_leap_month"],
        )
        lunar_year, lunar_month, lunar_day, lunar_leap = (
            params["year"], params["month"], params["day"], params["is_leap_month"],
        )

    lunar_gz = year_ganzhi(lunar_year)
    birth = {
        "name": params["name"] or None,
        "gender": params["gender"],
        "solar": solar_date.isoformat() + f" {params['hour']:02d}:{params['minute']:02d}",
        "solar_date": solar_date.isoformat(),
        "lunar": lunar_text(
            lunar_gz.tiangan.value, lunar_gz.dizhi.value,
            lunar_month, lunar_day, lunar_leap, shichen,
        ),
        "lunar_date": f"{lunar_gz.tiangan.value}{lunar_gz.dizhi.value}年"
        f"{'闰' if lunar_leap else ''}{CN_MONTH[lunar_month]}{cn_day(lunar_day)}",
        "lunar_year": lunar_year,
        "lunar_month": lunar_month,
        "lunar_day": lunar_day,
        "is_leap_month": lunar_leap,
        "shichen": shichen,
        "shichen_range": SHICHEN_RANGE[shichen],
        "zodiac": ZODIAC[lunar_gz.dizhi.value],
        "constellation": constellation(solar_date.month, solar_date.day),
        "birth_place": params["place"] or None,
        "city": params["city_name"],
        "longitude": params["longitude"],
        "timezone": params["timezone_text"],
        "true_solar_time": params["true_solar_time"],
        "day_rolled": calc.day_rolled,
    }

    daxian_direction = "顺行" if R.is_forward(year_gan, params["gender"]) else "逆行"
    chart_out = {
        "minggong": minggong,
        "shengong": shengong,
        "bureau": chart.bureau.value,
        "soul": R.SOUL_STAR[year_zhi if params["school"] == "zhongzhou" else minggong],
        "body": R.BODY_STAR[year_zhi],
        "yin_yang": ("阳" if R.gan_index(year_gan) % 2 == 0 else "阴") + params["gender"],
        "direction": daxian_direction,
        "first_decade_age": chart.bureau.number,
        "year_ganzhi": year_gan + year_zhi,
        "month_for_stars": month_eff,
        "sihua": sihua,
        "sihua_positions": sihua_positions,
        "palaces": palaces,
        "decades": [
            {
                "index": i + 1,
                "start_age": d.start_age,
                "end_age": d.end_age,
                "dizhi": d.dizhi.value,
                "palace": next(
                    p["name"] for p in palaces if p["dizhi"] == d.dizhi.value
                ),
                "ganzhi": next(
                    p["ganzhi"] for p in palaces if p["dizhi"] == d.dizhi.value
                ),
                "sihua": R.sihua(
                    next(p["ganzhi"][0] for p in palaces if p["dizhi"] == d.dizhi.value),
                    params["school"],
                ),
            }
            for i, d in enumerate(chart.decades)
        ],
    }

    result = {
        "schema": SCHEMA,
        "input": {
            "calendar_type": params["calendar"],
            "year": params["year"],
            "month": params["month"],
            "day": params["day"],
            "hour": params["hour"],
            "minute": params["minute"],
            "shichen": shichen,
            "gender": params["gender"],
            "birth_place": params["place"] or None,
            "longitude": params["longitude"],
            "true_solar_time": params["true_solar_time"],
            "is_leap_month": params["is_leap_month"],
            "school": params["school"],
            "leap_month_policy": params["leap_policy"].value,
            "day_rollover": params["rollover"].value,
            "year_boundary": params["year_boundary"].value,
            "tianma": params["tianma"].value,
            "target_year": params["target_year"],
        },
        "meta": {
            "engine": f"ziwei {pkg_version('ziwei')} + ziwei-skill rules",
            "zodiac_system": "紫微斗数（三合派通行安星）",
            "conventions": {
                "school": "通行（全书）" if params["school"] == "quanshu" else "中州派（王亭之）",
                "year_boundary": params["year_boundary"].value,
                "leap_month": params["leap_policy"].value,
                "day_rollover": params["rollover"].value,
                "sihua_table": "通行本《全书》" if params["school"] == "quanshu" else "中州派（王亭之）",
                "minor_stars": "通行三十八杂曜" if params["school"] == "quanshu" else "中州派杂曜（含截空、龙德、劫煞、大耗）",
                "soul_star": "命宫地支" if params["school"] == "quanshu" else "年支（中州派取法）",
                "tianma": params["tianma"].value,
                "brightness": "《紫微斗数全书》卷二固定录文，七级缩写为庙旺得利平不陷",
                "decade": "五行局起限、虚岁、阳男阴女顺行",
                "xiaoxian": "年支三合组起一岁，男顺女逆",
            },
        },
        "birth": birth,
        "chart": chart_out,
        "liunian": None,
    }

    target_year = params["target_year"]
    if target_year:
        result["liunian"] = build_liunian(
            target_year, calc, chart, palaces, params, star_pos, xiaoxian_branch,
        )
        # 标记当前大限
        age = result["liunian"]["age"]
        for palace in palaces:
            decade = palace["decade"]
            palace["is_current_decade"] = decade["start_age"] <= age <= decade["end_age"]

    return result


def build_liunian(target_year, calc, chart, palaces, params, star_pos, xiaoxian_branch) -> dict:
    from ziwei.ganzhi import year_ganzhi

    gz = year_ganzhi(target_year)
    gan, zhi = gz.tiangan.value, gz.dizhi.value
    age = target_year - calc.lunar_year + 1
    if age < 1:
        raise ValueError(f"target_year {target_year} 早于出生农历年 {calc.lunar_year}，无法推流年")
    if age > 125:
        raise ValueError(f"target_year {target_year} 对应虚岁 {age}，超出本盘 120 年大限范围")
    sihua = R.sihua(gan, params["school"])

    liunian_palaces = R.liunian_palaces(zhi)
    decade = next(
        (d for d in chart.decades if d.start_age <= age <= d.end_age), None
    )
    decade_branch = decade.dizhi.value if decade else None
    decade_palace = next((p for p in palaces if p["dizhi"] == decade_branch), None)
    decade_sihua = R.sihua(decade_palace["ganzhi"][0], params["school"]) if decade_palace else None

    liunian_lucun = R.LUCUN_BY_STEM[gan]
    liunian_gods = R.liunian_gods(zhi)
    xiaoxian = xiaoxian_branch(age)

    positions = []
    for label, star in sihua.items():
        branch = star_pos[star]
        opposite_branch = R.opposite(branch)
        positions.append({
            "label": label,
            "star": star,
            "dizhi": branch,
            "natal_palace": next(p["name"] for p in palaces if p["dizhi"] == branch),
            "liunian_palace": liunian_palaces[branch],
            "opposite_dizhi": opposite_branch,
            "opposite_palace": next(p["name"] for p in palaces if p["dizhi"] == opposite_branch),
        })

    return {
        "year": target_year,
        "ganzhi": gan + zhi,
        "age": age,
        "minggong": zhi,
        "minggong_natal_palace": next(p["name"] for p in palaces if p["dizhi"] == zhi),
        "sihua": sihua,
        "sihua_positions": positions,
        "palaces": [
            {
                "name": name,
                "dizhi": branch,
                "natal_palace": next(p["name"] for p in palaces if p["dizhi"] == branch),
            }
            for branch, name in liunian_palaces.items()
        ],
        "daxian": None if decade is None else {
            "start_age": decade.start_age,
            "end_age": decade.end_age,
            "dizhi": decade_branch,
            "ganzhi": decade_palace["ganzhi"],
            "palace": decade_palace["name"],
            "sihua": decade_sihua,
        },
        "xiaoxian": xiaoxian,
        "xiaoxian_natal_palace": next(p["name"] for p in palaces if p["dizhi"] == xiaoxian),
        "lucun": liunian_lucun,
        "qingyang": R.shift(liunian_lucun, 1),
        "tuoluo": R.shift(liunian_lucun, -1),
        "jiangqian": liunian_gods["jiangqian"],
        "suiqian": liunian_gods["suiqian"],
    }


# ------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="calculate_ziwei.py",
        description="紫微斗数排盘：从 stdin 读取 JSON 出生信息。",
    )
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--pretty", action="store_true", help="输出终端命盘（默认）")
    parser.add_argument("--detail", action="store_true", help="终端命盘后附逐宫明细")
    parser.add_argument("--color", choices=("auto", "always", "never"), default="auto")
    parser.add_argument("--year", type=int, default=None, help="流年公历年/干支年，如 2026")
    parser.add_argument("--name", default=None, help="命主称呼，仅用于显示")
    args = parser.parse_args(argv)

    try:
        payload = sys.stdin.read()
        if not payload.strip():
            raise ValueError("stdin 为空：请把包含出生信息的 JSON 通过管道传入")
        raw = json.loads(payload)
        if args.year is not None:
            raw["target_year"] = args.year
        if args.name:
            raw["name"] = args.name
        params = parse_params(raw)
        result = build_chart(params)
    except Exception as exc:  # noqa: BLE001 - CLI 统一转成结构化错误
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False),
              file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    from ziwei_render import render_chart

    use_color = args.color == "always" or (args.color == "auto" and sys.stdout.isatty())
    print(render_chart(result, color=use_color, detail=args.detail), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
