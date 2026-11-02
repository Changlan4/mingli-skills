# -*- coding: utf-8 -*-
"""六爻判定引擎：把《古筮真诠》的断卦步骤落成确定性检查。

设计原则（照抄书中第九章的方法论）：
    1. 断卦分两个层面 —— 吉凶判断层面、应期细节层面。同一理论在两层可能得出
       相反结论，任何一条断言都必须带层面标签，不许混用。
    2. 吉凶层面的「完整卦象」只有：日月组合 + 主卦 + 变卦（只写动爻）。
       伏神、六神、星煞、静爻的变卦不属于这一层。
    3. 引擎只输出「事实 + 规则触发 + 结论 + 原文出处」。解读交给模型，
       但模型只能引用这里出现过的断言，不许自创规则。

用法：
    python judge.py --chart chart.json --question "问这个月财运" [--text]
    python judge.py --yao "7 8 9 6 7 8" --datetime "2025-11-01 10:30" --question "..."
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import gua_data as gd          # noqa: E402
import liuyao as ly            # noqa: E402
import yingqi_engine           # noqa: E402

ZHI = "子丑寅卯辰巳午未申酉戌亥"
SHENG = gd.SHENG
KE = gd.KE
WX = gd.ZHI_WUXING
HE = gd.ZHI_LIUHE
CHONG = gd.ZHI_CHONG

# 六亲 → 问事。依 ch11「正确选取代表用神的六亲」，顺序「具体 → 笼统」。
# 书中明示的易混点已单独处理：
#   上司／领导 → 官鬼；公司老板、大股东、靠山 → 父母
#   房产买入 → 父母；房产卖出套现 → 妻财
#   激进投资 → 妻财；保守投资 → 子孙
#   丈夫／男友 → 官鬼；妻子／女友 → 妻财
ASK_RULES = [
    (("考试", "成绩", "录取", "通知书", "文书", "合同", "契约", "签约", "协议",
      "证件", "证照", "执照", "票据", "帐目", "投稿", "投标", "资格"),
     "父母", "考试文书类"),
    (("房子", "房产", "买房", "房屋", "车", "车辆", "土地", "城市", "衣服", "雨具",
      "电话", "床", "柜", "物件", "失物", "找东西", "找车", "快递", "包裹", "信件"),
     "父母", "房车物件类"),
    (("长辈", "父母", "老人", "爸爸", "妈妈", "爸", "妈", "师父", "师傅", "老师",
      "老板", "大股东", "靠山", "学校", "单位", "工程", "项目", "事件"),
     "父母", "长辈靠山类"),
    (("丈夫", "未婚夫", "男友", "男朋友", "老公", "上司", "领导", "贵人"),
     "官鬼", "男性对象或上级"),
    (("工作", "事业", "升职", "晋升", "官职", "职位", "调岗", "跳槽", "求职",
      "面试", "录用", "考编", "公务员", "功名", "荣誉", "成就", "升迁", "提拔",
      "转正", "编制", "上岸"),
     "官鬼", "功名事业类"),
    (("官司", "诉讼", "打官司", "官非", "小人", "病", "疾病", "病情", "灾",
      "贼", "盗", "忧", "担心", "祸"),
     "官鬼", "讼病忧患类"),
    (("财运", "求财", "钱", "收入", "工资", "薪水", "投资", "股票", "基金", "赚",
      "贷款", "回款", "欠款", "讨债", "货款", "利润", "分红", "买卖", "生意",
      "套现", "卖房", "出租", "股权", "奖金", "提成", "佣金", "报酬", "稿费",
      "红包", "收益", "进项", "发财", "中奖", "报销", "补贴", "加薪"),
     "妻财", "求财类"),
    (("妻", "老婆", "女友", "女朋友", "情妇", "员工", "仆", "女人"),
     "妻财", "女性对象或下属"),
    (("孩子", "子女", "儿女", "儿子", "女儿", "怀孕", "孕", "生育", "胎"),
     "子孙", "子女孕产类"),
    (("宠物", "猫", "狗", "医药", "医生", "治疗", "手术", "药效", "平安", "健康",
      "寿元", "僧", "道", "警察", "破案", "娱乐", "游玩", "度假", "辞职", "防范"),
     "子孙", "子孙福德类"),
    (("兄弟", "姐妹", "朋友", "合伙人", "同事", "同学", "同门", "同行", "竞争", "对手"),
     "兄弟", "同辈竞争类"),
    (("婚姻", "结婚", "对象", "相亲", "感情", "恋爱", "另一半"),
     "SELF_SEX", "婚姻类（按性别分取）"),
]


def ask_to_liuqin(question: str, gender: str = "") -> tuple:
    """问题 → (六亲, 命中关键词, 说明)。命中不了返回 (None, '', '')。"""
    q = question or ""
    for words, lq, note in ASK_RULES:
        for w in words:
            if w in q:
                if lq == "SELF_SEX":
                    if gender == "female":
                        return "官鬼", w, note + "：女占婚姻取官鬼"
                    if gender == "male":
                        return "妻财", w, note + "：男占婚姻取妻财"
                    return None, w, note + "：需先问性别才能定用神"
                return lq, w, note
    return None, "", ""


# ---------------------------------------------------------------- 取用神
# 依 ch11 六步次序：世应 → 有动 → 有异 → 唯一 → 日月 → 伏神。
# 关键：书里明确否定「舍衰取旺」——取用层只准以「是否见异」取舍，不准以旺衰取舍。
# 破爻、空爻、墓爻恰恰是可以、且应当优先取为用神的。
def _yao_brief(y):
    b = y.get("bian") or {}
    return {
        "位置": y.get("pos_name", ""),
        "纳甲": y.get("najia", ""),
        "地支": y.get("zhi", ""),
        "五行": y.get("wuxing", ""),
        "六亲": y.get("liuqin", ""),
        "世": bool(y.get("shi")),
        "应": bool(y.get("ying")),
        "动": bool(y.get("dong")),
        "空": bool(y.get("is_kong")),
        "月破": bool(y.get("is_month_po")),
        "日冲": (y.get("day_chong_judge") or "") if y.get("is_day_chong") else "",
        "入墓": bool(y.get("is_ru_mu")),
        "墓由": list(y.get("mu_by") or []),
        "月令": list(y.get("month_rel") or []),
        "日令": list(y.get("day_rel") or []),
        "变出": (b.get("najia", "") + " " + b.get("liuqin", "")) if b.get("najia") else "",
        "化绊": bool(b.get("hua_ban")),
        "化墓": bool(b.get("hua_mu")),
        "回头克": bool(b.get("ke_dong")),
        "进退": (b.get("jin_tui") or "").strip("—"),
    }


def _is_dong_or_an(y):
    """动爻 / 暗动之爻。"""
    if y.get("dong"):
        return True
    return (y.get("day_chong_judge") or "") == "暗动"


def _has_yi(y, month_zhi, day_zhi):
    """有异取异：临月建|临日建|临月合|临日合|临月破|被日冲|旬空被墓。"""
    tags = []
    zhi = y.get("zhi", "")
    if zhi and zhi == month_zhi:
        tags.append("临月建")
    if zhi and zhi == day_zhi:
        tags.append("临日建")
    if zhi and HE.get(zhi) == month_zhi:
        tags.append("临月合")
    if zhi and HE.get(zhi) == day_zhi:
        tags.append("临日合")
    if y.get("is_month_po"):
        tags.append("临月破")
    if y.get("is_day_chong"):
        tags.append("被日冲")
    if y.get("is_kong") and y.get("is_ru_mu"):
        tags.append("旬空被墓")
    return tags


def choose_yongshen(chart: dict, liuqin: str, question: str = "",
                    gender: str = "") -> dict:
    """按三级次序取用神，返回选定结果与完整理由链。"""
    month_zhi = chart.get("月建", "")
    day_zhi = chart.get("日辰", "")
    ask_self = not any(w in (question or "") for w in
                       ("他", "她", "对方", "别人", "合作", "对象", "朋友", "孩子"))

    if not liuqin:
        return {"选定": None, "候选": [], "次第": "未定",
                "依据": ["问事未能对应到六亲，须先核定用神"]}

    gua_yao = [y for y in chart["爻"] if y["liuqin"] == liuqin]
    fu_yao = [f for f in (chart.get("伏神") or []) if f.get("liuqin") == liuqin]

    cand = []
    for y in gua_yao:
        c = _yao_brief(y)
        c["_src"] = "本卦"
        cand.append(c)
    for f in fu_yao:
        cand.append({
            "位置": f.get("pos_name", "") + "（伏神）", "纳甲": f.get("najia", ""),
            "地支": f.get("najia", "")[1:2], "五行": f.get("wuxing", ""),
            "六亲": f.get("liuqin", ""), "世": False, "应": False, "动": False,
            "空": bool(f.get("is_kong")), "月破": bool(f.get("is_month_po")),
            "日冲": "", "入墓": bool(f.get("is_ru_mu")),
            "墓由": list(f.get("mu_by") or []), "月令": [], "日令": [],
            "变出": "", "化绊": False, "化墓": False, "回头克": False, "进退": "",
            "_src": "伏神", "_fushen": True,
        })

    basis = []
    if not cand:
        return {"选定": None, "候选": [], "次第": "用神不上卦",
                "依据": ["卦中与伏神均无「%s」" % liuqin,
                         "依 ch11 第五顺序：先看日令月令上是否有该六亲，"
                         "有则取日月之爻，不再套算伏神"]}

    # ---- 只有一个候选且不在世应：直接取（避免把"唯一"说成"见异"）
    if len(gua_yao) == 1 and not fu_yao and \
            not (gua_yao[0].get("shi") or gua_yao[0].get("ying")):
        y = gua_yao[0]
        basis.append("卦中只有一个「%s」（%s），别无选择，直接取用" % (
            liuqin, y.get("pos_name")))
        basis.append("风险提示：单一用神定位容易，但出现假用神的机会也相应增加，"
                     "须以事态现状对证")
        return {"选定": {**_yao_brief(y), "_src": "本卦"}, "候选": cand,
                "次第": "唯一", "依据": basis}

    # ---- 第一顺序：世应优先（压倒一切动静）
    in_sy = [y for y in gua_yao if y.get("shi") or y.get("ying")]
    if len(in_sy) == 1:
        y = in_sy[0]
        basis.append("第一顺序·世应优先：「%s」现于%s，直接取之" % (
            liuqin, "世爻" if y.get("shi") else "应爻"))
        return {"选定": {**_yao_brief(y), "_src": "本卦"}, "候选": cand,
                "次第": "世应", "依据": basis}

    if len(in_sy) >= 2:
        moving = [y for y in in_sy if _is_dong_or_an(y)]
        if moving:
            y = moving[0]
            basis.append("第一顺序·世应优先：世应俱现「%s」，按有动取动筛选，"
                         "取发动者（%s）" % (liuqin, y.get("pos_name")))
            return {"选定": {**_yao_brief(y), "_src": "本卦"}, "候选": cand,
                    "次第": "世应+动", "依据": basis}
        yi = [(y, _has_yi(y, month_zhi, day_zhi)) for y in in_sy]
        yi = [(y, t) for y, t in yi if t]
        if yi:
            y, t = yi[0]
            basis.append("第一顺序·世应优先：世应俱现且皆静，按有异取异筛选，"
                         "取%s者（%s）" % ("、".join(t), y.get("pos_name")))
            return {"选定": {**_yao_brief(y), "_src": "本卦"}, "候选": cand,
                    "次第": "世应+异", "依据": basis}
        if ask_self:
            y = next((z for z in in_sy if z.get("shi")), in_sy[0])
            why = "所问为自身之事，取世爻"
        else:
            y = next((z for z in in_sy if z.get("ying")), in_sy[0])
            why = "所问涉他人，取应爻"
        basis.append("第一顺序·世应优先：世应俱现、皆静、皆无异，%s"
                     "（ch11：问自身取世，问他人取应）" % why)
        return {"选定": {**_yao_brief(y), "_src": "本卦"}, "候选": cand,
                "次第": "世应+自身/他人", "依据": basis}

    # ---- 第二顺序：有动取动
    moving = [y for y in gua_yao if _is_dong_or_an(y)]
    if moving:
        basis.append("第二顺序·有动取动：世应位置无「%s」，取发动之爻" % liuqin)
        if len(moving) > 1:
            basis.append("多爻皆动（%d 个）且难分彼此 → 全部取为用神，"
                         "结论应为「吉凶并存、事分两半」，不要强行二选一" % len(moving))
        return {"选定": {**_yao_brief(moving[0]), "_src": "本卦"},
                "候选": cand, "次第": "动爻", "依据": basis,
                "多动爻": [_yao_brief(y) for y in moving]}

    # ---- 第三顺序：有异取异（不看旺衰）
    yi = [(y, _has_yi(y, month_zhi, day_zhi)) for y in gua_yao]
    yi = [(y, t) for y, t in yi if t]
    if yi:
        y, t = yi[0]
        basis.append("第三顺序·有异取异：无世应、无动爻，取见异之静爻 —— "
                     "「%s」（%s）" % (y.get("pos_name"), "、".join(t)))
        basis.append("注意：书里明确否定「舍衰取旺」。取用阶段不准以旺衰取舍，"
                     "只准以是否见异取舍；破爻空爻墓爻恰恰该优先取。")
        if len(yi) > 1:
            basis.append("多爻同时见异（%d 个），原文未给优先规则，"
                         "须以事态现状对证取舍" % len(yi))
        return {"选定": {**_yao_brief(y), "_src": "本卦"}, "候选": cand,
                "次第": "静爻见异", "依据": basis}

    # ---- 第四顺序：唯一用神
    if len(gua_yao) == 1:
        y = gua_yao[0]
        basis.append("第四顺序：卦中只有一个「%s」，别无选择，直接取用" % liuqin)
        basis.append("风险提示：单一用神定位容易，但出现假用神的机会也相应增加")
        return {"选定": {**_yao_brief(y), "_src": "本卦"}, "候选": cand,
                "次第": "唯一", "依据": basis}

    # ---- 本卦静爻多个且皆无异常
    if gua_yao:
        y = gua_yao[0]
        basis.append("本卦有多个「%s」静爻且皆不见异，原文未给进一步的优先规则，"
                     "默认取第一位，须以事态现状对证" % liuqin)
        return {"选定": {**_yao_brief(y), "_src": "本卦"}, "候选": cand,
                "次第": "静爻无异常", "依据": basis}

    # ---- 第六顺序：伏神
    f = fu_yao[0]
    basis.append("第六顺序：主卦不见「%s」，套算伏神，得%s伏%s%s" % (
        liuqin, f.get("pos_name", ""), f.get("liuqin", ""), f.get("najia", "")))
    basis.append("依 ch39：伏神不必陷于繁琐飞伏生克，走「卦理定性、卦意预兆、"
                 "心态反映」三路；伏而又空逢破，多是事败之兆")
    return {"选定": cand[-1], "候选": cand, "次第": "伏神", "依据": basis}


# ---------------------------------------------------------------- 层面隔离
def build_jixiong_view(chart: dict) -> dict:
    """吉凶层面的完整卦象：日月 + 主卦 + 变卦（只取动爻的变爻）。

    伏神、六神、静爻的变卦不进这一层。
    """
    dong = [y for y in chart["爻"] if y.get("dong")]
    return {
        "月建": chart.get("月建", ""),
        "日辰": chart.get("日辰", ""),
        "旬空": chart.get("旬空", ""),
        "主卦": chart["本卦"]["name"],
        "变卦": chart["变卦"]["name"] if chart.get("变卦") else None,
        "动爻数": len(dong),
        "动爻": [
            {
                "位": y["pos_name"], "纳甲": y["najia"], "六亲": y["liuqin"],
                "五行": y["wuxing"],
                "变出": (y["bian"]["najia"] + " " + y["bian"]["liuqin"])
                if y.get("bian") else None,
                "回头克": bool(y.get("bian", {}).get("ke_dong")),
                "化绊": bool(y.get("bian", {}).get("hua_ban")),
                "化墓": bool(y.get("bian", {}).get("hua_mu")),
                "进退": (y.get("bian", {}).get("jin_tui") or "").strip("—") or "",
            }
            for y in dong
        ],
        "排除项": "伏神、六神、星煞、静爻的变卦 —— 依第九章，这些不属于吉凶层面的完整卦象",
    }


def build_yingqi_view(chart: dict) -> dict:
    """应期细节层面：全量卦象，含六神、伏神、变卦全爻。"""
    return {
        "月建": chart.get("月建", ""),
        "日辰": chart.get("日辰", ""),
        "旬空": chart.get("旬空", ""),
        "主卦": chart["本卦"]["name"],
        "变卦": chart["变卦"]["name"] if chart.get("变卦") else None,
        "全爻": [
            {"位": y["pos_name"], "六神": y["liushen"], "纳甲": y["najia"],
             "六亲": y["liuqin"], "动静": "动" if y.get("dong") else "静",
             "世应": "世" if y.get("shi") else ("应" if y.get("ying") else "")}
            for y in chart["爻"]
        ],
        "伏神": chart.get("伏神", []),
        "说明": "应期层面放宽：月墓、月绊、空破真假之分都取消；"
                "三刑、相害、半合等在此层可用",
    }


# ---------------------------------------------------------------- 断言
class Assertion:
    """一条判定断言。层面是硬约束，模型不得跨层引用。"""

    def __init__(self, aid, layer, rule, conclusion, basis="", chapter="", effect="info"):
        self.id = aid
        self.layer = layer          # "吉凶" / "应期" / "细节"
        self.rule = rule
        self.conclusion = conclusion
        self.basis = basis
        self.chapter = chapter
        self.effect = effect        # info / 吉 / 凶 / 加成 / 减分

    def to_dict(self):
        return {
            "id": self.id, "层面": self.layer, "规则": self.rule,
            "结论": self.conclusion, "依据": self.basis,
            "出处": self.chapter, "倾向": self.effect,
        }


def _rel(a_wx, b_wx):
    """a 对 b 的五行关系。"""
    if a_wx == b_wx:
        return "比和"
    if SHENG.get(a_wx) == b_wx:
        return "生"
    if KE.get(a_wx) == b_wx:
        return "克"
    if KE.get(b_wx) == a_wx:
        return "被克"
    if SHENG.get(b_wx) == a_wx:
        return "被生"
    return ""


def collect_yongshen_assertions(chart: dict, yh: dict) -> list:
    """用神状态、世爻状态、世用关系 —— 吉凶层面的主线。

    这一段是断卦的落点，缺了它模型只能自己去读原文立论。
    依据：第 16 章（有用动爻）、第 18 章（用神与世爻相互作用）、第 39 章（藏伏）。
    """
    out = []
    x = yh.get("选定")
    if not x:
        return out

    yao_list = chart["爻"]
    shi = next((y for y in yao_list if y.get("shi")), None)
    dong = [y for y in yao_list if y.get("dong")]

    zhi = x.get("地支") or (x.get("纳甲") or "")[1:2]
    wx = x.get("五行") or WX.get(zhi, "")
    is_fu = x.get("_src") == "伏神"
    pos = x.get("位置", "")

    # ---------- 用神自身状态
    if is_fu:
        out.append(Assertion(
            "ys-01", "吉凶", "用神不上卦，取伏神",
            "用神藏伏，事未显、人在暗处。伏神逢空逢破多主事败（「伏居空地，事与心违」）；"
            "伏神只与本位飞神论生克，不与其他动爻直接论生克",
            "%s伏%s" % (pos, x.get("纳甲", "")), "第39章", "info"))
    if x.get("空"):
        out.append(Assertion(
            "ys-02", "吉凶", "用神旬空",
            "吉凶层面须分真空假空：静旺之静爻、动爻、变爻皆属假空，当它不空看；"
            "衰败无根者才是真空",
            pos + " " + (x.get("纳甲") or ""), "第28章", "info"))
    if x.get("月破"):
        out.append(Assertion(
            "ys-03", "吉凶", "用神月破",
            "月破之爻当月无用，出月可复。破爻仍可作为用神，但吉凶层面显衰",
            pos + " " + (x.get("纳甲") or ""), "第26章", "减分"))
    mu_by = x.get("墓由") or []
    if "日墓" in mu_by:
        out.append(Assertion(
            "ys-04", "吉凶", "用神日墓",
            "受困、迟缓、藏而不出。日墓在吉凶层面成立",
            pos + " " + (x.get("纳甲") or ""), "第35章", "减分"))
    elif "月墓" in mu_by:
        # 月墓只存在于应期层面。吉凶层面把它当衰来断，是最常见的跨层错误。
        out.append(Assertion(
            "ys-04b", "吉凶", "用神仅月墓，吉凶层面不成立",
            "此爻所入之墓来自月建。第35章：吉凶层面月令不论墓，只可论休囚。"
            "**不得以「用神入墓」为由判衰**，月墓只在应期层面作冲墓之期用",
            "%s 墓于月建「%s」" % (pos + " " + (x.get("纳甲") or ""),
                                  chart.get("月建", "")),
            "第35章", "info"))
    if x.get("回头克"):
        out.append(Assertion(
            "ys-05", "吉凶", "用神动而化回头克",
            "动爻化出之爻反克本爻，动则自伤，事多不成",
            "%s → %s" % (x.get("纳甲", ""), x.get("变出", "")), "第16章", "凶"))
    if x.get("化绊"):
        out.append(Assertion(
            "ys-06", "吉凶", "用神化绊",
            "动而被合住，若为假绊逢冲即开；若全卦动爻尽绊则为真绊，事多不了了之",
            "%s → %s" % (x.get("纳甲", ""), x.get("变出", "")), "第36章", "info"))
    if x.get("进退") == "进":
        out.append(Assertion("ys-07", "吉凶", "用神化进神", "同五行顺行，势头增强",
                             "%s → %s" % (x.get("纳甲", ""), x.get("变出", "")),
                             "第34章", "加成"))
    if x.get("进退") == "退":
        out.append(Assertion("ys-08", "吉凶", "用神化退神", "同五行逆行，势头衰减",
                             "%s → %s" % (x.get("纳甲", ""), x.get("变出", "")),
                             "第34章", "减分"))

    # ---------- 动爻对用神的作用（伏神不与其他动爻论生克）
    if not is_fu and wx:
        for y in dong:
            yz = y["najia"][1:]
            if yz == zhi:
                continue
            r = _rel(y["wuxing"], wx)
            if r == "克":
                out.append(Assertion(
                    "ys-11", "吉凶", "忌神发动克用神",
                    "动爻克用神，用神受伤；先看此爻是否真能克（有无回头克、化空破、被合绊）",
                    "%s %s 克 用神%s" % (y["pos_name"], y["najia"], x.get("纳甲", "")),
                    "第16章", "凶"))
            elif r == "生":
                out.append(Assertion(
                    "ys-12", "吉凶", "原神发动生用神",
                    "动爻生用神，用神有源；但须先确认此动爻本身有用（不化回头克、不空破）",
                    "%s %s 生 用神%s" % (y["pos_name"], y["najia"], x.get("纳甲", "")),
                    "第16章", "吉"))
            elif r == "被克":
                out.append(Assertion(
                    "ys-13", "吉凶", "用神克动爻",
                    "用神反克动爻，为泄耗之争，看两边旺衰",
                    "%s %s" % (y["pos_name"], y["najia"]), "第16章", "info"))

    # ---------- 世爻状态
    shi_hurt = []
    shi_wx = shi["wuxing"] if shi else ""
    if shi:
        if shi.get("is_month_po"):
            shi_hurt.append("月破")
        if (shi.get("day_chong_judge") or "") == "日破":
            shi_hurt.append("日破")
        for y in dong:
            if y["pos"] == shi["pos"]:
                continue
            if _rel(y["wuxing"], shi_wx) == "克":
                shi_hurt.append("%s %s 克世" % (y["pos_name"], y["najia"]))
        b = shi.get("bian") or {}
        if b.get("ke_dong"):
            shi_hurt.append("世爻动化回头克")

        if shi_hurt:
            out.append(Assertion(
                "sh-01", "吉凶", "世爻受伤",
                "世爻为求测者本身。世爻受伤则事难承受，即使用神旺相也难享其成",
                "；".join(shi_hurt), "第18章", "凶"))
        else:
            out.append(Assertion(
                "sh-02", "吉凶", "世爻未见明显伤克",
                "世爻无月破日破、无动爻克、无回头克。世爻尚能承受，"
                "吉凶主要看用神与世用的生克方向",
                "%s %s" % (shi["pos_name"], shi["najia"]), "第18章", "info"))

    # ---------- 用藏世伤（第39章直判口子）
    if is_fu and shi_hurt:
        out.append(Assertion(
            "sr-00", "吉凶", "用藏世伤",
            "用神藏伏的同时世爻受伤 → 直接判事败，不必再论其他",
            "用神伏藏；" + "；".join(shi_hurt), "第39章", "凶"))

    # ---------- 世用关系
    if shi and wx:
        if shi.get("liuqin") == x.get("六亲") and shi["najia"][1:] == zhi:
            out.append(Assertion(
                "sr-01", "吉凶", "用神持世（世用合一）",
                "吉凶即看此爻旺衰。注意世用合一要成立还需：静卦 + 自占自事 + 用神是六亲 "
                "+ 有根不逢破；动卦中只是分析焦点合一，仍照常看旺衰",
                "%s" % shi["najia"], "第23章", "info"))
        else:
            r = _rel(shi_wx, wx)
            mapping = {
                "生": ("用神生世", "用神生世爻，得利之象，主吉", "吉"),
                "被生": ("世生用神", "世爻生用神，我付出求取，看用神能否受生", "info"),
                "克": ("世克用神", "世爻克用神，我能掌控，但需用神有气可克", "info"),
                "被克": ("用神克世", "用神克世爻，受其所制，多主不利", "凶"),
                "比和": ("世用比和", "世用同气，事我相合，多主顺遂", "info"),
            }
            if r in mapping:
                name, concl, eff = mapping[r]
                out.append(Assertion(
                    "sr-02", "吉凶", name, concl,
                    "世%s（%s） vs 用神%s（%s）" % (
                        shi["najia"], shi_wx, x.get("纳甲", ""), wx),
                    "第18章", eff))
    return out

    def to_dict(self):
        return {
            "id": self.id, "层面": self.layer, "规则": self.rule,
            "结论": self.conclusion, "依据": self.basis,
            "出处": self.chapter, "倾向": self.effect,
        }


# 三合局：申子辰水、亥卯未木、寅午戌火、巳酉丑金（轴心为与局同五行之支）
SANHE_TRIOS = [
    (("申", "子", "辰"), "水", "子"),
    (("亥", "卯", "未"), "木", "卯"),
    (("寅", "午", "戌"), "火", "午"),
    (("巳", "酉", "丑"), "金", "酉"),
]


def detect_sanhe(chart: dict) -> list:
    """吉凶层面的三合局确认。依第 32 章，只有三种情形：

    其一，三爻皆动（含暗动），且都在主卦位置发动，不含变爻；
    其二，三爻皆动（不含暗动），在初爻、三爻位置上动变（含动爻与变爻）→ 内卦三合局；
    其三，三爻皆动（不含暗动），在四爻、六爻位置上动变（含动爻与变爻）→ 外卦三合局。

    变爻若出现在不合条件的位置（如三支齐了、但其中一支在别处的变爻上），不算成局。
    """
    found = []
    seen = set()

    dong_zhi = [y["zhi"] for y in chart["爻"]
                if y.get("dong") or (y.get("day_chong_judge") or "") == "暗动"]
    for trio, wx, axis in SANHE_TRIOS:
        if all(z in dong_zhi for z in trio):
            key = ("主卦三动", trio)
            if key not in seen:
                seen.add(key)
                found.append({"形态": "三爻皆动（主卦）", "三支": "、".join(trio),
                              "局": wx + "局", "轴心": axis})

    for positions, form in (((1, 3), "内卦三合局（初三位动变）"),
                            ((4, 6), "外卦三合局（四六位动变）")):
        zhis = []
        for y in chart["爻"]:
            if y["pos"] in positions and y.get("dong"):
                zhis.append(y["zhi"])
                b = y.get("bian") or {}
                if b.get("zhi"):
                    zhis.append(b["zhi"])
        for trio, wx, axis in SANHE_TRIOS:
            if all(z in zhis for z in trio):
                key = (form, trio)
                if key not in seen:
                    seen.add(key)
                    found.append({"形态": form, "三支": "、".join(trio),
                                  "局": wx + "局", "轴心": axis})
    return found


def collect_chart_assertions(chart: dict, liuqin: str = "") -> list:
    """卦体结构层面的断言（吉凶）。对应第二十九至三十一章。"""
    out = []
    gb = chart.get("卦体", {})
    combo = gb.get("组合", "")
    ben_body, bian_body = gb.get("本卦", ""), gb.get("变卦", "")
    if not combo:
        return out

    ben_c = "六冲" in ben_body
    ben_h = "六合" in ben_body
    bian_c = "六冲" in (bian_body or "")
    bian_h = "六合" in (bian_body or "")

    if ben_c and bian_h:
        out.append(Assertion(
            "gb-03", "吉凶", "六冲变六合",
            "先散后合、先难后成。此二类异向互化带明显祸福预兆，"
            "但须「就事论事对应现状」——现状确曾破败，此象才成立",
            combo, "第31章", "吉"))
    elif ben_h and bian_c:
        out.append(Assertion(
            "gb-04", "吉凶", "六合变六冲",
            "先合后离、先亲后疏、先成后败，得而复失。"
            "例外：占官非、盗贼、结绝事者反为宜，主纠缠终了",
            combo, "第31章", "凶"))
    elif ben_c and bian_c:
        out.append(Assertion(
            "gb-01", "吉凶", "六冲变六冲",
            "冲中再冲。吉凶层面**不是定性关键**，只作对证现状与细节之用；"
            "细节层面冲的程度较一般六冲卦更突出",
            combo, "第31章", "info"))
    elif ben_h and bian_h:
        out.append(Assertion(
            "gb-02", "吉凶", "六合变六合",
            "合中再合。吉凶层面**不是定性关键**，只作对证现状与细节之用；"
            "细节层面缠绵程度更突出，吉兆可延长、凶事也应得慢且缠人",
            combo, "第31章", "info"))
    elif ben_c:
        out.append(Assertion(
            "gb-05", "吉凶", "主卦六冲",
            "主快、主散。卦出六冲本身大多不是吉凶核心信息，"
            "多用于对证现状与细节（近事取快可，久事见冲则散）",
            combo, "第29章", "info"))
    elif ben_h:
        out.append(Assertion(
            "gb-06", "吉凶", "主卦六合",
            "主缓、主聚、主缠绵。本身大多不是吉凶核心信息，"
            "多用于对证现状与细节",
            combo, "第30章", "info"))
    elif bian_c:
        out.append(Assertion(
            "gb-07", "吉凶", "卦变六冲（本卦常卦）",
            "变卦六冲。书云卦变六冲六合大多不是吉凶预兆的核心信息，"
            "宜作趋势与细节看待，吉凶仍以用神世爻生克为主",
            combo, "第31章", "info"))
    elif bian_h:
        out.append(Assertion(
            "gb-08", "吉凶", "卦变六合（本卦常卦）",
            "变卦六合。同样不是吉凶核心信息，多主趋势转缓、转聚",
            combo, "第31章", "info"))
    else:
        out.append(Assertion(
            "gb-00", "吉凶", "卦体无常规定式",
            "本卦与变卦都不是六冲或六合，卦体层面没有一票定性的结构，"
            "吉凶须落到用神与世爻的旺衰生克上判断",
            combo, "第29章/第30章", "info"))

    ban = chart.get("化绊") or {}
    if ban.get("化绊数"):
        n, m = ban.get("化绊数"), ban.get("动爻数")
        if n == m and m > 0:
            out.append(Assertion(
                "gb-21", "吉凶", "全动化绊（真绊）",
                "动爻尽被绊住，有动等于没动；事多不了了之，且了无应期",
                "%d/%d 个动爻化绊" % (n, m), "第36章", "凶"))
        elif n >= 2:
            out.append(Assertion(
                "gb-22", "吉凶", "多爻化绊",
                "须核其中是否有被日辰或他爻冲开者，冲开者为假绊",
                "%d/%d 个动爻化绊" % (n, m), "第36章", "info"))
        else:
            out.append(Assertion(
                "gb-23", "吉凶", "一爻化绊",
                "多为假绊，逢冲即开",
                "%d/%d 个动爻化绊" % (n, m), "第36章", "info"))

    fy = chart.get("反吟") or {}
    if fy.get("has"):
        out.append(Assertion(
            "gb-31", "吉凶", "反吟", "主反复、来回折腾，事不一面倒",
            "、".join(fy.get("pairs", [])), "第37章", "info"))

    # 三合局（第32章）
    for k, j in enumerate(detect_sanhe(chart), 1):
        out.append(Assertion(
            "sj-%02d" % k, "吉凶", j["形态"],
            "%s 合成%s，轴心在%s。三合局坚固持久：吉则久远坚牢，凶则缠绵难解。"
            "须核此局对用神与世爻是生是克——生用则益，克用则伤；"
            "且本局是否成立还要看三爻是否皆动" % (j["三支"], j["局"], j["轴心"]),
            j["三支"], "第32章", "info"))
    return out


def render_text(result: dict) -> str:
    """把判定结果渲染成人类可读的报告。"""
    L = []
    L.append("═" * 60)
    L.append("【判定引擎输出】层面隔离版")
    L.append("═" * 60)

    jx, yq = result["吉凶层面卦象"], result["应期细节层面卦象"]
    L.append("")
    L.append("── 层面一：吉凶判断层面（只看日月 + 主卦 + 动爻变爻）")
    L.append("   月建 %s　日辰 %s　旬空 %s" % (jx["月建"], jx["日辰"], jx["旬空"]))
    L.append("   主卦 %s%s" % (jx["主卦"], (" 之 " + jx["变卦"]) if jx["变卦"] else "（静卦）"))
    if jx["动爻"]:
        for y in jx["动爻"]:
            extra = []
            if y["回头克"]:
                extra.append("回头克")
            if y["化绊"]:
                extra.append("化绊")
            if y["化墓"]:
                extra.append("化墓")
            if y["进退"]:
                extra.append("化" + y["进退"])
            L.append("   · %s %s %s%s　→ %s" % (
                y["位"], y["六亲"], y["纳甲"], y["五行"],
                (y["变出"] or "") + ("（%s）" % "、".join(extra) if extra else "")))
    else:
        L.append("   · 无动爻（静卦）")
    L.append("   注：" + jx["排除项"])

    L.append("")
    L.append("── 层面二：应期细节层面（全量，可放宽）")
    for y in yq["全爻"]:
        L.append("   %s %s %s%s %s%s" % (
            y["位"], y["六神"], y["六亲"], y["纳甲"], y["动静"],
            ("  " + y["世应"]) if y["世应"] else ""))
    if yq["伏神"]:
        L.append("   伏神：" + "；".join(
            "%s伏%s%s" % (f["pos_name"], f["liuqin"], f["najia"]) for f in yq["伏神"]))

    L.append("")
    L.append("── 判定断言（模型只能引用以下条目，不得自创规则）")
    for a in result["断言"]:
        L.append("   [%s][%s] %s" % (a["id"], a["层面"], a["规则"]))
        L.append("        结论：%s" % a["结论"])
        if a["依据"]:
            L.append("        依据：%s（%s）" % (a["依据"], a["出处"]))

    L.append("")
    L.append("── 取用神（按 ch11 六步次序）")
    yh = result.get("取用神") or {}
    if yh.get("问事归类"):
        L.append("   问事归类：%s（命中「%s」）" % (yh["问事归类"], yh.get("问事命中关键词", "")))
    L.append("   取用次第：%s" % yh.get("次第", "?"))
    for b in yh.get("依据", []):
        L.append("   · " + b)
    tid = yh.get("选定")
    if tid:
        L.append("   ★ 用神：%s %s%s（%s）%s%s%s" % (
            tid.get("位置", ""), tid.get("六亲", ""), tid.get("纳甲", ""),
            tid.get("五行", ""),
            "　空" if tid.get("空") else "",
            "　月破" if tid.get("月破") else "",
            ("　" + tid["日冲"]) if tid.get("日冲") else ""))
    cand = yh.get("候选") or []
    if len(cand) > 1:
        L.append("   全部候选：")
        for c in cand:
            L.append("     - %s %s%s %s%s%s%s" % (
                c.get("位置", ""), c.get("六亲", ""), c.get("纳甲", ""),
                "世" if c.get("世") else "", "应" if c.get("应") else "",
                " 动" if c.get("动") else "", " 空" if c.get("空") else ""))

    L.append("")
    L.append("── 应期（按 ch40）")
    yq = result.get("应期") or {}
    if yq:
        L.append("   主应期单位：%s　档位：%s%s" % (
            yq.get("主应期单位", "?"), yq.get("档位", "?"),
            "（推断，须复核）" if yq.get("档位是否推断") else ""))
        L.append("   判档依据：" + yq.get("档位依据", ""))
        if yq.get("适用公式"):
            L.append("   适用公式：")
            for f in yq["适用公式"]:
                L.append("     %s　%s　—　%s" % (f["编号"], "、".join(f["取期"]), f["说明"]))
        if yq.get("候选"):
            L.append("   应期候选（扫描 %s）：" % yq.get("主应期单位"))
            for h in yq["候选"][:12]:
                L.append("     %s　%s ← %s" % (
                    h["时间"], h["支"], "；".join(h["命中公式"])))
        for w in yq.get("无应期风险", []):
            L.append("   ! " + w)

    L.append("")
    L.append("── 下一步该读哪一章")
    for topic, files in result["待查章节"].items():
        L.append("   · %s → %s" % (topic, files))
    return "\n".join(L)


def judge(chart: dict, question: str = "", gender: str = "",
          span: str = "") -> dict:
    result = {
        "所问": question,
        "吉凶层面卦象": build_jixiong_view(chart),
        "应期细节层面卦象": build_yingqi_view(chart),
        "断言": [],
        "取用神": {},
        "应期": {},
        "待查章节": {},
    }
    liuqin, hit, note = ask_to_liuqin(question, gender)

    yh = choose_yongshen(chart, liuqin or "", question, gender)
    yh["问事命中关键词"] = hit
    yh["问事归类"] = note
    result["取用神"] = yh

    # 断言 = 卦体结构 + 用神状态 + 世爻状态 + 世用关系
    asserts = collect_chart_assertions(chart, liuqin or "")
    asserts += collect_yongshen_assertions(chart, yh)
    result["断言"] = [a.to_dict() for a in asserts]

    # ---- 应期：按主应期单位扫描
    base_dt = None
    t = chart.get("起卦时间") or ""
    if t:
        import datetime as _dt
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M"):
            try:
                base_dt = _dt.datetime.strptime(t, fmt)
                break
            except ValueError:
                continue
    result["应期"] = yingqi_engine.calc(
        chart, yh.get("选定"), question, span, base_dt)

    result["待查章节"] = {
        "取用神与世用关系": "ch11.md / ch18.md / ch25.md",
        "吉凶定性": "ch13.md / ch15.md / ch16.md / ch21.md",
        "卦体六冲六合": "ch29.md / ch30.md / ch31.md",
        "应期": "ch40-1.md / ch40-2.md",
    }
    return result


def load_chart(args) -> dict:
    """从 JSON 文件或命令行摇卦参数载入盘面。"""
    if args.get("chart"):
        return json.load(open(args["chart"], encoding="utf-8"))
    if args.get("parsed_text"):
        import parse_chart
        text = open(args["parsed_text"], encoding="utf-8").read()
        chart, _ = parse_chart.parse(text)
        if chart is None:
            raise SystemExit("盘面解析失败，缺少必要信息")
        return chart
    if args.get("yao"):
        import paipan
        import datetime as _dt
        lines = ly.parse_inputs(args["yao"])
        dt = args.get("datetime")
        if dt:
            d = None
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M"):
                try:
                    d = _dt.datetime.strptime(dt, fmt)
                    break
                except ValueError:
                    continue
            if d is None:
                raise SystemExit("起卦时间格式无法识别：" + dt)
        else:
            d = _dt.datetime.now()
        gz = paipan.ganzhi_of_datetime(d)
        chart = ly.build_chart(lines, gz, gz.get("xunkong", ""))
        # 干支与起卦时间必须写进盘面：应期引擎按它们判档位和扫描起点，
        # 缺了会静默兜底到「寅月」，整条应期线全偏。
        chart["干支"] = {"year": gz["year"], "month": gz["month"],
                         "day": gz["day"], "time": gz["time"]}
        chart["起卦时间"] = d.strftime("%Y-%m-%d %H:%M")
        chart["农历"] = gz.get("lunar", "")
        return chart
    raise SystemExit("需要 --chart / --parsed / --yao 之一")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="六爻判定引擎（层面隔离版）")
    ap.add_argument("--chart", help="盘面 JSON（paipan.py 输出）")
    ap.add_argument("--parsed", help="用户粘贴的盘面文本文件，自动解析")
    ap.add_argument("--yao", help='摇卦结果，如 "7 8 9 6 7 8"')
    ap.add_argument("--datetime", help="起卦时间")
    ap.add_argument("--question", default="", help="所问何事")
    ap.add_argument("--gender", default="", choices=["", "male", "female"])
    ap.add_argument("--span", default="", help="事件大致跨度，帮助判短事/常事/久远")
    ap.add_argument("--text", action="store_true", help="输出人类可读报告")
    a = ap.parse_args()
    chart = load_chart({"chart": a.chart, "parsed_text": a.parsed,
                        "yao": a.yao, "datetime": a.datetime})
    res = judge(chart, a.question, a.gender, a.span)
    if a.text:
        print(render_text(res))
    else:
        print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
