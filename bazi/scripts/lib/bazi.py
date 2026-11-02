# -*- coding: utf-8 -*-
"""
八字排盘主引擎

对外主函数：
    paipan(year, month, day, hour, minute=0, gender=1, city=None, longitude=None,
           calendar="solar", use_true_solar=True, school="sect2",
           dayun_count=10, liunian_range=(start, end)) -> dict

关键约定（改代码前务必读）：
  * 年柱、月柱：以【北京时间 + 节气精确时刻】判定。节气是全国同一瞬间的天文事件，
    跟出生地经度无关，用真太阳时去比节气会把边界搞错。
  * 日柱、时柱：以【真太阳时】判定。日界与时辰本来就是当地太阳位置决定的。
  * 两者交叉处（出生恰在节气交接前后、或真太阳时跨日时）会写入 warnings。
  * 晚子时（23:00-23:59）：school="sect1" 日柱算次日，sect2 算当日；
    时干一律按次日日干起五鼠遁。
"""
import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bazi_const import (
    GAN, ZHI, GAN_WUXING, GAN_YINYANG, ZHI_WUXING, ZHI_YINYANG, CANG_GAN,
    SHENG, KE, WUSHU, CHANGSHENG_START, CHANGSHENG_NAMES, NAYIN,
    shishen, shensha, true_solar_time, resolve_longitude, CITY_LONGITUDE,
)
from strength import strength as analyze_strength, render_strength
from tiaohou import tiaohou_yongshen, check_against_chart, MONTH_NAME, temp_score
from geju import geju as analyze_geju, render_geju
from ganzhi_level import four_levels as analyze_levels, render_levels
from relations import analyze as analyze_relations, render as render_relations


def _gz(gan, zhi):
    return gan + zhi


def _xunkong(gan_index, zhi_index):
    """
    求某一柱的旬空。
    原理：六十甲子按旬分组，每旬 10 个干支，天干轮完而地支余 2 个未用，
    这 2 个未用的地支就是该旬的"空亡"。
    起始地支序号 = (支序 - 干序 + 10) % 12。
    验算：甲子(0,0)→戌亥；辛未(7,7)→戌亥；壬辰(8,4)→午未；癸亥(9,11)→子丑。
    """
    v = (zhi_index - gan_index + 10) % 12
    return ZHI[v] + ZHI[(v + 1) % 12]


def _zhi_index(z):
    return ZHI.index(z)


def _gan_index(g):
    return GAN.index(g)


def changsheng(day_gan, zhi):
    """十二长生：阳干顺行，阴干逆行"""
    start = CHANGSHENG_START[day_gan]
    offset = (_zhi_index(zhi) - _zhi_index(start)) % 12
    if GAN_YINYANG[day_gan] == "阴":
        offset = (-offset) % 12
    return CHANGSHENG_NAMES[offset]


def five_element_stats(pillars, day_gan):
    """
    客观五行力量统计（只做数据，不做强弱结论）。
    权重：天干 1.0；地支藏干 本气1.0 / 中气0.5 / 余气0.3。
    另外给出"同类(比劫+印) vs 异类(官杀+财+食伤)"的原始计数，
    供解读层按书里的强弱图解流程使用。
    """
    weights = {"木": 0.0, "火": 0.0, "土": 0.0, "金": 0.0, "水": 0.0}
    detail = {"木": [], "火": [], "土": [], "金": [], "水": []}
    for g, z in pillars:
        weights[GAN_WUXING[g]] += 1.0
        detail[GAN_WUXING[g]].append(f"干{g}1.0")
        hides = CANG_GAN[z]
        w = [1.0, 0.5, 0.3]
        for i, h in enumerate(hides):
            val = w[i] if i < len(w) else 0.3
            weights[GAN_WUXING[h]] += val
            detail[GAN_WUXING[h]].append(f"支{z}藏{h}{val}")

    me = GAN_WUXING[day_gan]
    tong = {"木": 0.0, "火": 0.0, "土": 0.0, "金": 0.0, "水": 0.0}
    # 同类：同我五行 + 生我五行
    sheng_me = [k for k, v in SHENG.items() if v == me][0]
    tong[me] = weights[me]
    tong[sheng_me] = weights[sheng_me]
    yi = sum(weights.values()) - sum(tong.values())
    return {
        "五行权重": {k: round(v, 1) for k, v in weights.items()},
        "明细": detail,
        "日主五行": me,
        "同类(比劫+印)": round(sum(tong.values()), 1),
        "异类(官杀+财+食伤)": round(yi, 1),
    }


def paipan(year, month, day, hour, minute=0, gender=1, city=None, longitude=None,
           calendar="solar", use_true_solar=True, school="sect2",
           dayun_count=10, liunian_range=None, is_leap_month=False):
    from lunar_python import Solar, Lunar

    warnings = []
    notes = []

    # ---------- 1. 统一到公历年月日时分 ----------
    if calendar == "lunar":
        lm = -month if is_leap_month else month
        lunar_in = Lunar.fromYmdHms(year, lm, day, hour, minute, 0)
        solar_in = lunar_in.getSolar()
        y, mo, d = solar_in.getYear(), solar_in.getMonth(), solar_in.getDay()
        lunar_desc = f"农历{year}年{'闰' if is_leap_month else ''}{month}月{day}日 {hour:02d}:{minute:02d}"
    else:
        y, mo, d = year, month, day
        lunar_desc = None

    beijing_dt = datetime.datetime(y, mo, d, hour, minute, 0)

    # ---------- 2. 真太阳时 ----------
    lon, lon_src = resolve_longitude(city=city, longitude=longitude)
    if lon is None:
        use_true_solar = False
        notes.append("未提供出生地经度，时辰按北京时间判定。若出生地离东经120°较远"
                     "（如新疆、四川西部、黑龙江），请补充城市或经度后重排。")
    if use_true_solar and lon is not None:
        tsdt, ts_detail = true_solar_time(beijing_dt, lon)
    else:
        tsdt = beijing_dt
        ts_detail = {"经度差(分)": 0.0, "均时差(分)": 0.0, "总校正(分)": 0.0}

    # ---------- 3. 排四柱 ----------
    # 年月柱：北京时间（节气为全局事件）
    l_beijing = Solar.fromYmdHms(y, mo, d, hour, minute, 0).getLunar()
    ec_b = l_beijing.getEightChar()
    year_gz = ec_b.getYear()
    month_gz = ec_b.getMonth()

    # 日时柱：真太阳时
    ty, tmo, td = tsdt.year, tsdt.month, tsdt.day
    th, tmi = tsdt.hour, tsdt.minute
    l_true = Solar.fromYmdHms(ty, tmo, td, th, tmi, 0).getLunar()
    ec_t = l_true.getEightChar()
    ec_t.setSect(1 if school == "sect1" else 2)
    day_gz = ec_t.getDay()
    time_gz = ec_t.getTime()

    # 若真太阳时落在 23:00-23:59，且用 sect2（算当日），时干仍应按次日日干起
    # lunar-python 已按 Exact（次日）算时干，此处仅作记录。
    if th == 23 and school == "sect2":
        notes.append("出生在晚子时（真太阳时 23:00-23:59）。日柱按流派2取当日，"
                     "时干按次日日干起五鼠遁；若你的流派是『子时换日』，用 school=sect1 重排。")

    # 年月柱的两种口径分歧检查（真太阳时 vs 北京时间）
    ec_ts_ym = (ec_t.getYear(), ec_t.getMonth())
    if ec_ts_ym != (year_gz, month_gz):
        warnings.append(
            f"⚠ 节气边界：用北京时间算年月柱为 {year_gz} {month_gz}，"
            f"用真太阳时算为 {ec_ts_ym[0]} {ec_ts_ym[1]}。"
            f"本盘已按『年月柱用北京时间』取 {year_gz} {month_gz}。"
            f"出生时刻离节气交接极近，务必人工复核。")

    # 距节气交接多久
    try:
        prev_jq = l_beijing.getPrevJieQi(True)
        next_jq = l_beijing.getNextJieQi(True)
        pj_solar = prev_jq.getSolar()
        nj_solar = next_jq.getSolar()
        pj_dt = datetime.datetime(pj_solar.getYear(), pj_solar.getMonth(),
                                  pj_solar.getDay(), pj_solar.getHour(), pj_solar.getMinute())
        nj_dt = datetime.datetime(nj_solar.getYear(), nj_solar.getMonth(),
                                  nj_solar.getDay(), nj_solar.getHour(), nj_solar.getMinute())
        gap_prev = (beijing_dt - pj_dt).total_seconds() / 3600.0
        gap_next = (nj_dt - beijing_dt).total_seconds() / 3600.0
        notes.append(f"上一节气 {prev_jq.getName()} {pj_dt:%Y-%m-%d %H:%M}（距今 {gap_prev:.1f} 小时）；"
                     f"下一节气 {next_jq.getName()} {nj_dt:%Y-%m-%d %H:%M}（距今 {gap_next:.1f} 小时）")
        if gap_prev < 2 or gap_next < 2:
            warnings.append("⚠ 出生时刻距节气交接不足 2 小时，年柱/月柱处于极敏感区间，"
                            "不同软件可能给出不同结果，请与用户确认口径。")
    except Exception as e:
        notes.append(f"节气交接时刻获取失败：{e}")

    pillars = [(year_gz[0], year_gz[1]), (month_gz[0], month_gz[1]),
               (day_gz[0], day_gz[1]), (time_gz[0], time_gz[1])]
    day_gan = day_gz[0]
    names = ["年", "月", "日", "时"]
    labels = ["年柱", "月柱", "日柱", "时柱"]

    # ---------- 4. 逐柱信息 ----------
    zhu = {}
    for i, (g, z) in enumerate(pillars):
        hides = CANG_GAN[z]
        hide_info = []
        for j, h in enumerate(hides):
            role = ["本气", "中气", "余气"][j] if j < 3 else "余气"
            hide_info.append({"干": h, "五行": GAN_WUXING[h], "十神": shishen(day_gan, h), "位置": role})
        # 十神（天干）：日干自己标"日主"
        tg = "日主" if i == 2 else shishen(day_gan, g)
        zhu[names[i]] = {
            "柱": labels[i],
            "干": g, "支": z,
            "干支": g + z,
            "干五行": GAN_WUXING[g], "干阴阳": GAN_YINYANG[g],
            "支五行": ZHI_WUXING[z], "支阴阳": ZHI_YINYANG[z],
            "天干十神": tg,
            "藏干": hide_info,
            "纳音": NAYIN.get(g + z, ""),
            "旬空": "",
            "十二长生": changsheng(day_gan, z),
            "自坐": changsheng(g, z),
        }

    # 旬空：每柱按自己的干支求（各柱旬空可以不同），另给"日柱空亡"供命局判断
    for i, n in enumerate(names):
        g, z = pillars[i]
        zhu[n]["旬空"] = _xunkong(_gan_index(g), _zhi_index(z))
    day_xk = zhu["日"]["旬空"]
    # 日柱空亡落点：命局中哪些地支正好是空亡支
    kong_hits = [(names[i], pillars[i][1]) for i in range(4) if pillars[i][1] in day_xk]

    # ---------- 5. 神煞 ----------
    ss = shensha(pillars, day_gan, pillars[0][0], pillars[1][1])

    # ---------- 6. 大运 ----------
    yun = ec_t.getYun(gender)
    start_solar = yun.getStartSolar()
    da_yun = []
    for dy in yun.getDaYun():
        gz = dy.getGanZhi()
        if not gz:
            continue
        da_yun.append({
            "干支": gz,
            "十神": shishen(day_gan, gz[0]),
            "起始年": dy.getStartYear(), "结束年": dy.getEndYear(),
            "起始虚岁": dy.getStartAge(), "结束虚岁": dy.getEndAge(),
            "旬空": dy.getXunKong(),
        })
        if len(da_yun) >= dayun_count:
            break

    dayun_info = {
        "起运": f"{yun.getStartYear()}年{yun.getStartMonth()}个月{yun.getStartDay()}天后",
        "起运日期": f"{start_solar.getYear()}-{start_solar.getMonth():02d}-{start_solar.getDay():02d}",
        "方向": "顺行" if yun.isForward() else "逆行",
        "性别": "男" if gender == 1 else "女",
        "列表": da_yun,
    }

    # ---------- 7. 流年 ----------
    liunian = []
    if liunian_range:
        s_year, e_year = liunian_range
        for yy in range(s_year, e_year + 1):
            sl = Solar.fromYmd(yy, 6, 1)
            gz = sl.getLunar().getYearInGanZhiExact()
            liunian.append({
                "年份": yy,
                "干支": gz,
                "十神": shishen(day_gan, gz[0]),
                "虚岁": yy - y + 1,
            })

    # ---------- 8. 交叉校验（sxtwl） ----------
    cross = []
    try:
        import sxtwl
        sday = sxtwl.fromSolar(ty, tmo, td)
        s_gz = sday.getDayGZ()
        s_day = GAN[s_gz.tg] + ZHI[s_gz.dz]
        if th != 23 or school == "sect1":
            if s_day != day_gz:
                cross.append(f"日柱不一致：lunar-python={day_gz}，sxtwl={s_day}")
        else:
            cross.append(f"sxtwl 日柱={s_day}（晚子时，未参与比对，instrument 归流派差异）")
    except Exception as e:
        cross.append(f"sxtwl 校验不可用：{e}")

    # ---------- 9. 汇总 ----------
    result = {
        "输入": {
            "公历": f"{y}-{mo:02d}-{d:02d} {hour:02d}:{minute:02d}" if calendar == "solar"
                    else f"{y}-{mo:02d}-{d:02d} {hour:02d}:{minute:02d}（由农历转换）",
            "农历": lunar_desc,
            "性别": "男" if gender == 1 else "女",
            "出生地": city or "",
            "经度": lon,
            "经度来源": lon_src,
        },
        "真太阳时": {
            "时刻": tsdt.strftime("%Y-%m-%d %H:%M"),
            "校正": ts_detail,
            "启用": use_true_solar,
            "说明": "日柱、时柱按此判定；年柱、月柱仍按北京时间配节气。",
        },
        "四柱": zhu,
        "八字": " ".join(p[0] + p[1] for p in pillars),
        "日主": {"干": day_gan, "五行": GAN_WUXING[day_gan], "阴阳": GAN_YINYANG[day_gan]},
        "神煞": ss,
        "日柱空亡": day_xk,
        "命局空亡落点": kong_hits,
        "五行统计": five_element_stats(pillars, day_gan),
        "强弱": analyze_strength(pillars, day_gan),
        "调候": {
            "月支": pillars[1][1],
            "月令": MONTH_NAME.get(pillars[1][1], ""),
            "调候用神": tiaohou_yongshen(day_gan, pillars[1][1])[1],
            "落实": [{"干": g, "状态": st} for g, st in check_against_chart(day_gan, pillars[1][1], pillars)[0]],
            "寒暖燥湿": temp_score(pillars),
        },
        "格局": analyze_geju(pillars, day_gan),
        "干支等级": analyze_levels(pillars),
        "刑冲会合": analyze_relations(pillars),
        "大运": dayun_info,
        "流年": liunian,
        "胎元": ec_t.getTaiYuan(),
        "胎息": ec_t.getTaiXi(),
        "命宫": ec_t.getMingGong(),
        "身宫": ec_t.getShenGong(),
        "warnings": warnings,
        "notes": notes,
        "交叉校验": cross,
    }
    return result


# ---------------------------------------------------------------- 文本渲染

import unicodedata


def _dw(s):
    """字符串显示宽度：CJK 全角算 2"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _pad(s, w, align="left"):
    gap = w - _dw(s)
    if gap <= 0:
        return s
    if align == "right":
        return " " * gap + s
    if align == "center":
        l = gap // 2
        return " " * l + s + " " * (gap - l)
    return s + " " * gap


def _row(label, cells, widths, aligns=None):
    """label 占固定宽度，cells 按各列宽度对齐"""
    aligns = aligns or ["center"] * len(cells)
    parts = [_pad(str(c), widths[i], aligns[i]) for i, c in enumerate(cells)]
    return _pad(label, 10) + "".join(parts)


def _table(rows):
    """rows: [(label, [4 个单元格])]，列宽按内容自适应"""
    ncol = len(rows[0][1])
    widths = []
    for i in range(ncol):
        w = max(_dw(str(r[1][i])) for r in rows) + 2
        widths.append(max(w, 10))
    return [_row(lab, cells, widths) for lab, cells in rows]


def render(r, show_detail=True):
    L = []
    a = L.append
    a("=" * 50)
    a(f"　{r['八字']}")
    a("=" * 50)
    inp = r["输入"]
    line = f"公历 {inp['公历']}　{inp['性别']}命"
    if inp["出生地"]:
        line += f"　{inp['出生地']}"
    a(line)
    if inp.get("农历"):
        a(f"农历 {inp['农历']}")
    ts = r["真太阳时"]
    if ts["启用"]:
        a(f"真太阳时 {ts['时刻']}（校正 {ts['校正']['总校正(分)']:+.1f} 分 = "
          f"经度差 {ts['校正']['经度差(分)']:+.1f} + 均时差 {ts['校正']['均时差(分)']:+.1f}）")
    else:
        a("真太阳时 未校正（按北京时间判定时辰）")
    a("")

    order = ["年", "月", "日", "时"]
    z = r["四柱"]
    table_rows = [
        ("", [z[k]["柱"] for k in order]),
        ("天干", [f"{z[k]['干']}（{z[k]['天干十神']}）" for k in order]),
        ("地支", [f"{z[k]['支']}（{z[k]['支五行']}）" for k in order]),
        ("藏干", ["/".join(f"{h['干']}·{h['十神']}" for h in z[k]["藏干"]) for k in order]),
        ("纳音", [z[k]["纳音"] for k in order]),
        ("星运", [z[k]["十二长生"] for k in order]),
        ("自坐", [z[k]["自坐"] for k in order]),
        ("神煞", ["、".join(r["神煞"][k]) if r["神煞"][k] else "—" for k in order]),
        ("旬空", [z[k]["旬空"] for k in order]),
    ]
    L.extend(_table(table_rows))
    a("　※ 星运＝日主在各支的十二长生（长生/沐浴/…/死/墓）；"
      "下面强弱里的「旺相休囚死」是五行四时用事，两套体系，不要混看。")
    kong = r.get("命局空亡落点") or []
    if kong:
        a(f"日柱空亡 {r['日柱空亡']}　命局落点：" + "、".join(f"{n}支{z}" for n, z in kong))
    else:
        a(f"日柱空亡 {r['日柱空亡']}　命局无地支落入")
    a("")

    st = r["五行统计"]
    total = sum(st["五行权重"].values()) or 1
    a("五行分布（参考，含藏干加权）　" + "  ".join(f"{k} {v}" for k, v in st["五行权重"].items()))
    a("　　　　　　　　　　　　　　　" + "  ".join(f"{k} {v / total * 100:.0f}%" for k, v in st["五行权重"].items()))
    a("　※ 日主强弱请看下方的图解计数，那是陆氏原书口径，与这里的加权分布不是一套算法。")
    a("")

    d = r["大运"]
    a(f"大运　{d['方向']}　起运 {d['起运']}（{d['起运日期']} 交运）")
    for i in range(0, len(d["列表"]), 5):
        chunk = d["列表"][i:i + 5]
        a("　" + "   ".join(f"{_pad(x['干支'], 4)}{x['十神']}"
                            f"({x['起始虚岁']}-{x['结束虚岁']}岁)" for x in chunk))
    a("")

    if r.get("调候"):
        tc = r["调候"]
        a(f"── 调候（《穷通宝鉴》十干调候用神，原书 p100 表5.3）──")
        a(f"  {r['日主']['干']}{r['日主']['五行']} 生 {tc['月支']}月（{tc['月令']}）→ 调候用神：{tc['调候用神'] or '—'}")
        if tc["落实"]:
            a("  落实：" + "　".join(f"{x['干']}{x['状态']}" for x in tc["落实"]))
        ts = tc.get("寒暖燥湿")
        if ts:
            a(f"  寒暖燥湿计分：天干{sum(ts['天干计分']):+d} 地支{sum(ts['地支计分']):+d} "
              f"月令{ts['月令加分']:+d} → 合计 {ts['合计']:+d}（{ts['判断']}，{ts['调候方向']}）")
        a("")

    if r.get("刑冲会合"):
        a("── 刑冲会合（基础 p78-95 自动检出）──")
        for ln in render_relations(r["刑冲会合"]).splitlines():
            a("  " + ln)
        a("　※ 只检出关系，不判吉凶；合化要看引化之神。与大运流年的关系可另算。")
        a("")

    if r.get("干支等级"):
        a("── 干支优略等级（动态 p293-295，快速判断法）──")
        for ln in render_levels(r["干支等级"]).splitlines():
            a("  " + ln)
        a("")

    if r.get("强弱"):
        a("── 日主强弱（强弱图解分析法）──")
        for ln in render_strength(r["强弱"]).splitlines():
            a("  " + ln)
        a("")


    if r.get("格局"):
        a("── 格局（十神与格局）──")
        for ln in render_geju(r["格局"]).splitlines():
            a("  " + ln)
        a("")

    a(f"胎元 {r['胎元']}　胎息 {r['胎息']}　命宫 {r['命宫']}　身宫 {r['身宫']}"
      "　（仅列出，不作判据：三书未将其作为分析依据）")
    if r["流年"]:
        a("")
        a("流年　" + "  ".join(f"{x['年份']}{x['干支']}({x['十神']})" for x in r["流年"][:24]))
        if len(r["流年"]) > 24:
            a(f"　　　…共 {len(r['流年'])} 年")

    if r["warnings"]:
        a("")
        a("【警告】")
        for w in r["warnings"]:
            a("  " + w)
    if r["notes"]:
        a("")
        a("【提示】")
        for n in r["notes"]:
            a("  " + n)
    if r["交叉校验"]:
        a("")
        a("【交叉校验】")
        for c in r["交叉校验"]:
            a("  " + c)
    return "\n".join(L)
