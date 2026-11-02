# -*- coding: utf-8 -*-
"""应期引擎：照《古筮真诠》第四十章实现。

与旧 yingqi.py 的区别：
  1. 先判「主应期单位」（时辰/日/月/年），日月按长短事冻结或递进，
     而不是固定扫起卦后 60 天 —— 这是旧实现最硬伤的地方。
  2. 公式按书里 24 条逐条编号，输出时带 F01~F24 编号与原文依据。
  3. 分档扫描：短事日变月不变、常事月变日不变、久远只变太岁、日内按时辰。
"""
import datetime as _dt

ZHI = "子丑寅卯辰巳午未申酉戌亥"
GAN = "甲乙丙丁戊己庚辛壬癸"

CHONG = {"子": "午", "午": "子", "丑": "未", "未": "丑", "寅": "申", "申": "寅",
         "卯": "酉", "酉": "卯", "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳"}
HE = {"子": "丑", "丑": "子", "寅": "亥", "亥": "寅", "卯": "戌", "戌": "卯",
      "辰": "酉", "酉": "辰", "巳": "申", "申": "巳", "午": "未", "未": "午"}

WX_MU = {"木": "未", "火": "戌", "金": "丑", "水": "辰", "土": "辰"}
# 长生十二宫起节点（阳干顺行口径，六爻断应期用五行即可）
CHANGSHENG = {"木": "亥", "火": "寅", "金": "巳", "水": "申", "土": "申"}
JUEDE = {"木": "申", "火": "亥", "金": "寅", "水": "巳", "土": "亥"}

SANHE = [(("申", "子", "辰"), "水"), (("亥", "卯", "未"), "木"),
         (("寅", "午", "戌"), "火"), (("巳", "酉", "丑"), "金")]

BASE_UNIT = {"INTRA_DAY": "HOUR", "SHORT": "DAY", "MEDIUM": "MONTH", "LONG": "YEAR"}
UNIT_CN = {"HOUR": "时辰", "DAY": "日", "MONTH": "月", "YEAR": "年"}

# 地支 → 时辰段（用于 HOUR 扫描时显示）
SHICHEN = {"子": "23-1", "丑": "1-3", "寅": "3-5", "卯": "5-7", "辰": "7-9",
           "巳": "9-11", "午": "11-13", "未": "13-15", "申": "15-17",
           "酉": "17-19", "戌": "19-21", "亥": "21-23"}


# ---------------------------------------------------------------- 档位
def guess_case_kind(question: str = "", span: str = "") -> tuple:
    """判主应期单位。返回 (CASE_KIND, 理由, 是否推断)。

    书里只说「时间跨度在一个月内＝短事，一年内＝常事，一年以上＝长事」，
    但没有给「怎么机器判定跨度」的算法 —— 原文要求结合事理常识人工判。
    这里只做关键词粗判，并明确告知模型这是推断，须复核。
    """
    q = question or ""
    span = span or ""
    s = q + " " + span

    # 判据是「跨度」，不是「哪个月」：书里只有三档阈值——
    # 一个月内＝短事（按日）、一年内＝常事（按月）、一年以上＝久远（按年）。
    # 「这个月」「下个月」跨度都在一个月内，属短事，必须按日扫。
    intra = ("今天", "今日", "几点", "什么时候来电", "一会儿", "一会", "当晚",
             "今天之内", "当日", "这会儿", "今晚", "马上")
    long_ = ("几年", "一生", "这辈子", "长久", "长期", "终身", "晚年", "养老",
             "十年", "未来几年", "这一世")
    medium = ("今年", "明年", "一年", "年内", "半年", "几个月", "未来一年",
              "年底", "开春", "这两年", "一两年")
    short_ = ("这个月", "本月", "下个月", "月内", "这月", "当月",
              "这几天", "本周", "下周", "这周", "最近", "明天", "后天", "日内", "短期内")

    for w in intra:
        if w in s:
            return "INTRA_DAY", "问句含「%s」，属超短期日内之测" % w, True
    for w in long_:
        if w in s:
            return "LONG", "问句含「%s」，跨度在一年以上，属久远之占" % w, True
    for w in short_:
        if w in s:
            return "SHORT", "问句含「%s」，跨度在一个月内，属短事" % w, True
    for w in medium:
        if w in s:
            return "MEDIUM", "问句含「%s」，跨度在一年内，属常事" % w, True
    return "MEDIUM", "问句未给出时间跨度，按「一般的事情」默认取月为主应期单位", False


# ---------------------------------------------------------------- 干支工具
def ganzhi_of(d: _dt.date) -> str:
    """公历日 → 日柱干支（用 lunar_python，保证与排盘一致）。"""
    try:
        from lunar_python import Solar
        lunar = Solar.fromYmd(d.year, d.month, d.day).getLunar()
        return lunar.getDayInGanZhi()
    except Exception:          # noqa: BLE001
        return ""


def zhi_of_ganzhi(gz: str) -> str:
    return gz[1] if len(gz) >= 2 else ""


def shi_of(day_zhi: str, hour: int) -> str:
    """小时 → 时支。23 点属子时。"""
    idx = ((hour + 1) // 2) % 12
    return ZHI[idx]


# ---------------------------------------------------------------- 扫描
def scan_points(base_dt, base_ganzhi: dict, case_kind: str, count=36, has_date=True):
    """生成候选时点。

    每项：{序号, 单位, 支, 显示, ...}
    依 ch40-1：短事月不转、常事日不转、久远只转太岁、日内只转时辰。
    has_date=False 时（用户的盘只有干支、没有公历），只给「逢某支」不给具体年月日，
    不能在缺少年份的情况下凭当前日期编一个年份出来。
    """
    unit = BASE_UNIT[case_kind]
    y, m, d = base_dt.year, base_dt.month, base_dt.day
    pts = []

    if unit == "DAY":
        cur = _dt.date(y, m, d)
        d0 = base_ganzhi.get("day", "")[1:]
        # 注意：空串 `"" in "子丑寅…"` 在 Python 里是 True，ZHI.index("") 返回 0，
        # 会把起点静默当成「子」。必须先判非空。
        i0 = ZHI.index(d0) if (d0 and d0 in ZHI) else ZHI.index("子")
        for i in range(1, count + 1):
            cur = cur + _dt.timedelta(days=1)
            gz = ganzhi_of(cur) if has_date else ""
            z = zhi_of_ganzhi(gz) if gz else ZHI[(i0 + i) % 12]
            shown = ("%s（%s日）" % (cur.isoformat(), gz)) if has_date \
                else ("起卦后第%d日，逢%s日" % (i, z))
            pts.append({"序号": i, "单位": "日", "支": z, "显示": shown,
                        "日期": cur if has_date else None, "日柱": gz,
                        "说明": "月建冻结于起卦月"})
    elif unit == "MONTH":
        day_zhi = base_ganzhi.get("day", "")[1:] or "未知"
        m0 = base_ganzhi.get("month", "")[1:]
        i0 = ZHI.index(m0) if (m0 and m0 in ZHI) else ZHI.index("寅")
        for i in range(1, count + 1):
            mz = ZHI[(i0 + i) % 12]
            # 月建以节气为界，与公历月份并不对齐；只报「起卦后第几个月」，
            # 不硬换算公历年月，否则会算出「第4个月=X月」却与月建不符。
            shown = "起卦后第%d个月，月建%s（日辰冻结为%s）" % (i, mz, day_zhi)
            pts.append({"序号": i, "单位": "月", "支": mz, "显示": shown,
                        "日支固定": day_zhi,
                        "说明": "日辰冻结于起卦日；月建以节气为界，不折公历月"})
    elif unit == "YEAR":
        yz = base_ganzhi.get("year", "")[1:]
        base_i = ZHI.index(yz) if (yz and yz in ZHI) else 0
        for i in range(0, count + 1):
            z = ZHI[(base_i + i) % 12]
            shown = ("%d年（太岁%s）" % (y + i, z)) if has_date else ("第%d年，逢太岁%s" % (i, z))
            pts.append({"序号": i, "单位": "年", "支": z, "显示": shown,
                        "年": y + i if has_date else None,
                        "说明": "日月皆冻结"})
    else:  # HOUR
        start = base_dt.hour
        for i in range(1, count + 1):
            h = (start + 2 * i) % 24
            z = ZHI[((h + 1) // 2) % 12]
            shown = ("%s %02d时（%s时 %s）" % (base_dt.date().isoformat(), h, z,
                                             SHICHEN.get(z, ""))) \
                if has_date else ("第%d个时辰，逢%s时" % (i, z))
            pts.append({"序号": i, "单位": "时辰", "支": z, "显示": shown,
                        "说明": "日月皆冻结"})
    return pts


# ---------------------------------------------------------------- 取期模式
def target_branches(x: dict) -> dict:
    """算出某爻各取期方式对应哪些地支。"""
    zhi = x.get("zhi") or ""
    wx = x.get("wuxing") or ""
    out = {}
    if zhi:
        out["VALUE"] = {zhi: "逢值（填实）"}
        out["CLASH"] = {CHONG[zhi]: "逢冲"}
        out["COMBINE"] = {HE[zhi]: "逢合（补破）"}
    if wx in WX_MU:
        mu = WX_MU[wx]
        out.setdefault("TOMB", {})[mu] = "入墓"
        out["TOMB_CLASH"] = {CHONG[mu]: "冲墓"}
    if wx in CHANGSHENG:
        out["LONGLIFE"] = {CHANGSHENG[wx]: "逢长生"}
    if wx in JUEDE:
        out["ABSOLUTE"] = {JUEDE[wx]: "逢绝"}
    return out


# ---------------------------------------------------------------- 公式
def match_formulas(x: dict, chart: dict, layer="应期") -> list:
    """给定用神爻，返回可能适用的应期公式编号与取期方式。

    只实现不依赖吉凶定性结论的公式（F01–F13、F16、F17、F23）。
    F14/F15/F18–F22/F24 需吉凶结论或特殊结构，输出为「待人工套用」。
    """
    used = []
    zhi = x.get("zhi") or ""
    if not zhi:
        return used

    is_dong = bool(x.get("dong") or x.get("动"))
    # 应期层面：空破一律视作空破，不再分真假（第九章）
    kong = bool(x.get("is_kong") if "is_kong" in x else x.get("空"))
    month_po = bool(x.get("is_month_po") if "is_month_po" in x else x.get("月破"))
    day_chong = bool(x.get("is_day_chong") if "is_day_chong" in x else x.get("日冲"))
    ru_mu = bool(x.get("is_ru_mu") if "is_ru_mu" in x else x.get("入墓"))
    bian = x.get("bian") or {}
    ke_dong = bian.get("ke_dong") if bian else x.get("回头克")
    sheng_dong = bian.get("sheng_dong") if bian else None
    jin_tui = (bian.get("jin_tui") if bian else None) or x.get("进退") or ""
    bian_najia = bian.get("najia") if bian else (x.get("变出") or "")[:2]

    # F01 静爻逢值逢冲
    if not is_dong:
        used.append(("F01", ["VALUE", "CLASH"], "静爻逢值逢冲"))
    # F02 动爻逢合逢值
    else:
        used.append(("F02", ["COMBINE", "VALUE"], "动爻逢合逢值"))
    # F03 月破
    if month_po:
        used.append(("F03", ["VALUE", "COMBINE"], "月破：填实（实破）或逢合（补破）"))
    # F04 日冲（日破）
    if day_chong:
        used.append(("F04", ["VALUE", "COMBINE"], "日冲：应期层面视为破，逢填实或补破"))
    # F05 旬空
    if kong:
        used.append(("F05", ["VALUE", "CLASH"], "旬空：填实（填空）或逢冲（冲空即实）"))
    # F06 遇合逢冲 / 遇冲逢合
    mz, dz = chart.get("月建", ""), chart.get("日辰", "")
    he_with = []
    for name, b in (("月建", mz), ("日辰", dz)):
        if b and zhi and HE.get(zhi) == b:
            he_with.append(name)
        if b and zhi and CHONG.get(zhi) == b:
            he_with.append(name + "（冲）")
    if he_with:
        used.append(("F06", ["CLASH", "VALUE"],
                     "遇合逢冲、遇冲逢合（%s）" % "、".join(he_with)))
    # F07 动逢月合
    if is_dong and mz and HE.get(mz) == zhi:
        used.append(("F07", ["VALUE"], "动而逢月建合（三绊/月合），数后三个月内"))
    # F09 变爻
    if bian_najia:
        if ke_dong or sheng_dong:
            used.append(("F09", ["VALUE", "COMBINE"],
                         "变爻有回头生克：取变爻逢值或逢合"))
        else:
            used.append(("F09", ["VALUE", "CLASH"],
                         "变爻无回头生克：取变爻逢值或逢冲"))
    # F10 化进神
    if jin_tui == "进":
        used.append(("F10", ["VALUE", "COMBINE"], "化进神：逢值、逢合或化进之期"))
    # F11 化退神
    if jin_tui == "退":
        used.append(("F11", ["CLASH"], "化退神：逢冲（两冲）之期"))
    # F13 入墓
    if ru_mu:
        used.append(("F13", ["TOMB_CLASH", "CLASH"], "入墓：冲墓、冲爻出墓"))
    # F16 伏吟
    if bian_najia and bian_najia[1:] == zhi:
        used.append(("F16", ["VALUE", "CLASH"], "伏吟：取最终目标爻逢值逢冲"))
    # F17 伏神
    if x.get("_fushen"):
        used.append(("F17", ["VALUE", "COMBINE", "CLASH"],
                     "藏伏：露伏（逢值逢合）或冲飞神"))
    return used


def multi_appear_tomb(chart: dict, wuxing: str) -> str:
    """F23 多现多发：日、月、动、变四处≥3 个同类五行 → 取该五行之墓。"""
    cnt = 0
    pos = []
    if chart.get("日辰") and WX_OF.get(chart["日辰"]) == wuxing:
        cnt += 1
        pos.append("日")
    if chart.get("月建") and WX_OF.get(chart["月建"]) == wuxing:
        cnt += 1
        pos.append("月")
    for y in chart["爻"]:
        if y.get("dong"):
            if y.get("wuxing") == wuxing:
                cnt += 1
                pos.append("动")
            b = y.get("bian") or {}
            if b.get("wuxing") == wuxing:
                cnt += 1
                pos.append("变")
    if cnt >= 3:
        return WX_MU.get(wuxing, "")
    return ""


WX_OF = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
         "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"}


# ---------------------------------------------------------------- 主入口
def calc(chart: dict, yongshen: dict, question: str = "", span: str = "",
         base_dt=None, max_points=36) -> dict:
    """算出应期候选。

    yongshen：choose_yongshen 返回的「选定」项，需含 zhi/wuxing/dong 等。
    """
    kind, why, inferred = guess_case_kind(question, span)
    unit = BASE_UNIT[kind]

    if base_dt is None:
        base_dt = _dt.datetime.now()
    gz = chart.get("干支") or {}

    result = {
        "档位": kind,
        "主应期单位": UNIT_CN[unit],
        "档位依据": why,
        "档位是否推断": inferred,
        "说明": "短事日转月不转；常事月转日不转；久远之占日月皆不转、只有太岁动；"
                "日内之测按月日皆冻结、只走时辰（ch40-1）",
        "适用公式": [],
        "候选": [],
        "无应期风险": [],
        "待人工套用": [],
    }

    if not yongshen:
        result["无应期风险"].append("未定用神，无法推应期")
        return result

    x = dict(yongshen)
    # 兼容不同来源的字段名（judge 输出「地支」，排盘原字段是 zhi）
    if not x.get("zhi"):
        x["zhi"] = x.get("地支", "")
        if not x["zhi"] and x.get("纳甲"):
            x["zhi"] = x["纳甲"][1:2]
    if not x.get("wuxing"):
        x["wuxing"] = x.get("五行") or WX_OF.get(x.get("zhi", ""), "")
    if "dong" not in x and "动" in x:
        x["dong"] = bool(x["动"])

    forms = match_formulas(x, chart)
    result["适用公式"] = [{"编号": f, "取期": t, "说明": d} for f, t, d in forms]
    if not forms:
        result["无应期风险"].append("用神不在卦中或无可套用的应期公式，请核对用神")

    # 目标支集合
    tb = target_branches(x)
    want = {}
    for fid, takes, desc in forms:
        if fid == "F06":
            continue          # F06 取期方式特殊，下面单独算
        if fid == "F09":
            # F09 取的是「用神所化变爻」的逢值逢冲，不是用神自己的支
            bz = (x.get("变出") or "")[1:2] or (bian_najia[1:] if bian_najia else "")
            if bz:
                hm = bool(x.get("回头克"))
                bmap = target_branches({"zhi": bz})
                for t in takes:
                    for b, label in bmap.get(t, {}).items():
                        want.setdefault(b, []).append(
                            "F09·变爻%s%s%s" % (bz, label, "（有回头生克）" if hm else ""))
            continue
        for t in takes:
            for b, label in (tb.get(t) or {}).items():
                want.setdefault(b, []).append("%s·%s（%s）" % (fid, label, desc))

    # F06 遇合逢冲 / 遇冲逢合：取「冲开合神」或「合住冲神」之支，不是冲用神本身
    mz, dz = chart.get("月建", ""), chart.get("日辰", "")
    zhi_x = x.get("zhi", "")
    for name, b in (("月建", mz), ("日辰", dz)):
        if not b or not zhi_x:
            continue
        if HE.get(zhi_x) == b:          # 用神被 b 合住
            open_b = CHONG[b]
            want.setdefault(open_b, []).append(
                "F06·冲开%s合神「%s」的解绊之期（%s）" % (name, b, open_b))
        if CHONG.get(zhi_x) == b:       # 用神被 b 冲
            he_b = HE[b]
            want.setdefault(he_b, []).append(
                "F06·合住%s冲神「%s」之期（%s）" % (name, b, he_b))
        # 「二不合一」：相绊两元素逢值亦可
        if HE.get(zhi_x) == b:
            want.setdefault(zhi_x, []).append("F06·二不合一，相绊元素逢值之期（%s）" % zhi_x)
            want.setdefault(b, []).append("F06·二不合一，相绊元素逢值之期（%s）" % b)

    # F23 多现收藏
    mu = multi_appear_tomb(chart, x["wuxing"])
    if mu:
        want.setdefault(mu, []).append("F23·入墓（多现多发，日月动变≥3 处同类五行）")

    has_date = bool(chart.get("起卦时间"))
    if not has_date:
        result["说明"] += "；原盘缺公历起卦时间，只能给「逢某支」的期，不编造具体年月日"
    n_scan = {"SHORT": 60, "MEDIUM": 24, "LONG": 12, "INTRA_DAY": 12}.get(kind, 12)
    pts = scan_points(base_dt, gz, kind, min(n_scan, max_points), has_date=has_date)
    hits = []
    seen = {}
    for p in pts:
        b = p["支"]
        if b not in want:
            continue
        # 同一地支最多保留两次（一轮内重复出现说明是周期性，不必罗列）
        if seen.get(b, 0) >= 2:
            continue
        seen[b] = seen.get(b, 0) + 1
        hits.append({"序号": p["序号"], "时间": p["显示"], "支": b,
                     "命中公式": want[b], "单位": p["单位"]})
        if len(hits) >= max_points:
            break
    result["候选"] = hits
    result["扫描说明"] = "扫描 %d 个%s位；同支最多保留两次；单位由主应期基数决定，非公式内硬编码" % (
        len(pts), UNIT_CN[unit])

    if not hits:
        result["无应期风险"].append("在扫描范围内无命中，可能是用神状态特殊或应期较远；"
                                    "请核对档位（短事/常事/久远）是否判对")

    # 需要吉凶结论或特殊结构的公式
    result["待人工套用"] = [
        {"编号": "F12", "说明": "三合局：吉断喜成、凶断宜破；缺一可补缺成局",
         "条件": "卦中有三合局或三缺一"},
        {"编号": "F14", "说明": "三刑：仅应期层面成立，缺一补全、齐全取临值"},
        {"编号": "F15", "说明": "反吟：取反吟元素逢值之期"},
        {"编号": "F18", "说明": "定性为吉而用神受克：待忌神受冲克之期"},
        {"编号": "F19", "说明": "定性为凶而用神受生：待生旺元素被冲克之期"},
        {"编号": "F20", "说明": "定性为凶：世爻或用神逢冲之期"},
        {"编号": "F21", "说明": "爻过旺：逢墓绝或逢克之期"},
        {"编号": "F22", "说明": "爻过衰：逢长生或逢生旺之期"},
        {"编号": "F24", "说明": "非主流应期：与主流应期对冲之期（极端条件）"},
    ]

    # 取舍原则（ch40-2 六条）
    result["取舍原则"] = [
        "P1 吉断吉应、凶断凶应：先定吉凶方向，再谈时间",
        "P2 应动不应静：七成事实应期落在动变信息里，优先看动爻与用神之变",
        "P3 应众不应寡：多个公式重叠指向同一时点者优先",
        "P4 应早不应迟：同等条件下就近取",
        "P5 应邻不应单：相邻时点可合并成一段给出，不要只报单点",
        "P6 盯面不盯点：输出 2~3 个相连应期，明确说是区间不是精确承诺",
    ]

    # 加速 / 迟缓修正（ch40-2）
    result["节奏修正"] = []
    if any(y.get("dong") and not y.get("is_month_po") for y in chart["爻"]):
        pass
    ben = chart.get("本卦", {}).get("body", "")
    if "六冲" in ben:
        result["节奏修正"].append("主卦六冲、且卦中有暗动或临日令者，应期偏快")
    if "六合" in ben:
        result["节奏修正"].append("主卦六合、卦有三合三绊者，应期偏慢")
    return result
