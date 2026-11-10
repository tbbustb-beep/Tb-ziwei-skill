# Tb-ziwei-skill

紫微斗数排盘与解读 Agent Skill。GitHub：https://github.com/tbbustb-beep/Tb-ziwei-skill

> 项目/仓库名为 `Tb-ziwei-skill`；本地技能目录与调用名仍是 `ziwei-skill`，保证已有命令与存档路径不变。

把紫微斗数排盘、命盘存档与对话式解读，打包成一个可执行、可复用、可存档的 Agent Skill。

不是“会说紫微”的提示词壳子，而是“先算准，再讲清”的完整链路。适用于 DSH、Claude Code、OpenClaw 等支持读取 `SKILL.md` 并执行本地命令的 Agent 框架。

---

## 1. 设计思路

大模型手排紫微盘，最容易错在三处：农历换算、命宫身宫、五行局起紫微。一步错，后面十四主星、四化、大限全盘皆错。

Tb-ziwei-skill 因此把工作拆成三层：

- **计算层（Python）**：农历/公历换算、真太阳时、命身宫、五行局、十四主星、六吉六煞、禄存天马、红鸾天喜、大限、小限；四化、杂曜、十二神、流年由本地规则模块补齐。
- **结构层（JSON）**：脚本输出完整的十二宫、星曜庙旺、四化落宫、大限流年，Agent 不需要也不允许自己补星。
- **解读层（Agent）**：`SKILL.md` 约束解读框架——命身格局、三方四正、四化叠宫、大限流年、趋吉避凶，不灌鸡汤、不编星曜。

## 2. 功能

- **公历 / 农历输入**：农历闰月可指定；公历可做真太阳时校正。
- **完整本命盘**：命宫、身宫、五行局、命主身主、十二宫干支。
- **星曜**：十四主星（含七级庙旺）、六吉六煞、禄存、天马、红鸾天喜，加三十余颗杂曜（天刑、天姚、三台八座、恩光天贵、龙池凤阁、天哭天虚、孤辰寡宿、华盖、咸池、天德月德、截空旬空、天伤天使等）。
- **四化**：生年四化、大限四化、流年四化，均给出落宫与冲宫参考。
- **运限**：十二大限（虚岁）、小限年龄表、流年十二宫与流年禄羊陀。
- **十二神**：长生十二神、博士十二神、将前十二神、岁前十二神。
- **终端盘面**：十二宫格直出，支持颜色、逐宫明细。
- **本地存档**：按 slug 保存、读取、列出、删除命盘。

## 3. 安装

```powershell
$SKILL_DIR = "$env:USERPROFILE\.dsh\skills\ziwei-skill"
python -m venv "$SKILL_DIR\.venv"        # Python 3.11–3.14
& "$SKILL_DIR\.venv\Scripts\python.exe" -m pip install -r "$SKILL_DIR\requirements.txt" -i https://pypi.org/simple
& "$SKILL_DIR\.venv\Scripts\python.exe" "$SKILL_DIR\selfcheck.py"
```

> `ziwei` 与 `celestial-calendar` 目前不在清华镜像，必须走官方 PyPI。
> Python 3.11–3.14；Windows amd64 有预编译 wheel。

## 4. 使用

```powershell
$SKILL_DIR = "$env:USERPROFILE\.dsh\skills\ziwei-skill"
$PY = "$SKILL_DIR\.venv\Scripts\python.exe"

# 终端命盘
'{"year":2000,"month":8,"day":16,"hour":2,"minute":30,"gender":"女","birth_place":"四川成都"}' |
  & $PY "$SKILL_DIR\calculate_ziwei.py" --pretty --color never

# 带流年
'{"year":2000,"month":8,"day":16,"hour":2,"minute":30,"gender":"女","target_year":2026}' |
  & $PY "$SKILL_DIR\calculate_ziwei.py" --pretty --detail

# 结构化 JSON
'{"year":2000,"month":8,"day":16,"hour":2,"minute":30,"gender":"女"}' |
  & $PY "$SKILL_DIR\calculate_ziwei.py" --json
```

存档：

```powershell
$params | & $PY "$SKILL_DIR\calculate_ziwei.py" --json |
  & $PY "$SKILL_DIR\store_ziwei.py" save --name "张三" --slug "zhangsan" --memo "朋友"
& $PY "$SKILL_DIR\store_ziwei.py" list
& $PY "$SKILL_DIR\store_ziwei.py" load --slug zhangsan
```

## 5. 口径

默认取通行（《紫微斗数全书》）口径：

| 项目 | 默认 | 可切换 |
|---|---|---|
| 换年 | 农历正月初一 | 立春（1972 年后） |
| 闰月 | 上半月归本月、下半月归下月 | 全月归本月 / 全月归下月 |
| 晚子时 | 归次日 | 早晚子时同日 |
| 四化 | 通行《全书》表 | 中州派（同时切换杂曜与命主取法） |
| 天马 | 年支 | 月支 |
| 大限 | 五行局起限，虚岁，阳男阴女顺行 | — |
| 亮度 | 《全书》卷二固定录文 | — |
| 真太阳时 | 关闭 | 开启（需经度、1972 年后） |

## 6. 验证

- `selfcheck.py` 内置 10 张参照盘（普通盘、晚子时、闰二月、1955 年早盘），覆盖命身宫、五行局、命主身主、全部星曜、四化、十二神、大限、小限。
- 开发期另以 iztro 2.6.5 随机交叉核对了 500 张普通盘、40 张晚子时盘、40 张闰月盘，星位与十二神零差异；立春口径仅“立春当日交节前后”因“按时刻”与“按日期”口径不同而有意保留差异。
- `cities.py` 的经度是常用值（约 0.05° 精度），只影响真太阳时的时辰边界；需要精确值时直接传 `longitude`。

## 7. 目录

```
Tb-ziwei-skill/
├─ SKILL.md               # 给 Agent 的完整操作与解读规范
├─ calculate_ziwei.py     # 排盘 CLI
├─ store_ziwei.py         # 命盘存档
├─ ziwei_rules.py         # 四化 / 杂曜 / 十二神 / 流年规则
├─ ziwei_render.py        # 终端十二宫盘
├─ cities.py              # 城市经度表
├─ selfcheck.py           # 自检
├─ references/charts.json # 参照盘
└─ requirements.txt
```

## 8. 同类项目

发布后检索到几个更早的同类项目。如果只是想直接用现成的，可以先看这些：

- [dzcmemory-web/bazi-ziwei-skills](https://github.com/dzcmemory-web/bazi-ziwei-skills)：八字 + 紫微综合印证，支持 HTML 命盘海报，社区热度最高
- [mingze21/bazi-ziwei-skill](https://github.com/mingze21/bazi-ziwei-skill)：同一路线的另一份实现
- [shanrichard/ziwei-skill](https://github.com/shanrichard/ziwei-skill)：Claude Code / OpenClaw 的紫微 Skill

本项目的差异：运行时纯 Python，不依赖 Node/iztro；排盘口径显式可选；自带终端十二宫盘与 10 张参照盘自检；并用 iztro 做过 580 张盘的交叉验证。

## 9. 致谢与许可

- 农历与核心安星：[ziwei](https://github.com/0xf3cd/ziwei)（MIT），历法依赖 [celestial-calendar](https://github.com/0xf3cd/celestial-calendar)。
- 杂曜与十二神公式对照：[iztro](https://github.com/SylarLong/iztro)（MIT）。
- 规则依据：《紫微斗数全书》《紫微斗数全集》及通行安星诀。

本项目仅供传统命理研究、AI 工程实践与娱乐参考。命由己造，盘只是参照系。
