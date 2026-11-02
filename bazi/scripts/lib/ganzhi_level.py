# -*- coding: utf-8 -*-
"""
干支优略等级（陆致极《动态分析教程》第九章 p293-295）

原书背景：戴先生把六十甲子分成上/中/下三等，给出「三上一下决不是下等命」这类
快速判断法。陆氏指出该书「并没有说明为什么做出这样分级的明确标准」，
于是自己给出了客观依据——按五行生克把干支分成五种基本类型：

  (1) 上生下  甲午、乙巳：天干五行生地支本气
  (2) 下生上  甲子、乙亥：地支本气生天干五行
  (3) 上克下  甲辰、乙丑：天干五行克地支本气（尊制卑）
  (4) 下克上  甲申、乙酉：地支本气克天干五行（卑克尊 → 冒犯）
  (5) 上下同  甲寅、乙卯：天干与地支本气同五行

优劣取向（原书 p294）：
  「(1) 和 (2) 是相生关系；(3) 和 (4) 是相克关系；(5) 是同类关系。
   若要做优劣判断，自然会取相生和同类为「优」，因为相生有情，同类如兄弟，
   有互助之力。」
  依据是沈孝瞻《子平真诠》的两个标准：**有情/无情**、**有力/无力**。

  相克里还要再分：「天干为阳，地支为阴；天干为「尊」，地支为「卑」。
  因此「上克下」是「尊」制「卑」；而「下克上」则是「卑」克「尊」，成了一种
  「冒犯」。因此，类型 (4) 的干支就要放到「下等」层次中去了。」

  另有一类「上下相合」：如戊子（戊与子中癸合）、丁亥、辛巳、壬午，
  「正好上下相合，自然是有情的」。

⚠ 原书明确：这是「快速切入的判断法，但不是绝对可靠的」。
   必须与「五行强弱定喜忌、提出用神、确定格局」结合使用（p293）。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bazi_const import (
    GAN, ZHI, GAN_WUXING, ZHI_WUXING, CANG_GAN, SHENG, KE,
)

# 天干五合
GAN_HE = [("甲", "己"), ("乙", "庚"), ("丙", "辛"), ("丁", "壬"), ("戊", "癸")]

TYPE_DESC = {
    "上生下": "天干生地支（我生）",
    "下生上": "地支生天干（生我）",
    "上克下": "天干克地支（尊制卑）",
    "下克上": "地支克天干（卑克尊·冒犯）",
    "上下同": "干支同类（比和）",
}


def shangxia_he(gan, zhi):
    """
    天干与本柱地支藏干是否相合（例：戊子，戊与子中癸合）。
    返回 (藏干, 说明) 或 (None, None)
    """
    for h in CANG_GAN[zhi]:
        for a, b in GAN_HE:
            if {gan, h} == {a, b}:
                return h
    return None


def ganzhi_type(gan, zhi):
    """五种基本类型"""
    gw = GAN_WUXING[gan]
    zw = ZHI_WUXING[zhi]          # 地支本气五行
    if gw == zw:
        return "上下同"
    if SHENG[gw] == zw:
        return "上生下"
    if SHENG[zw] == gw:
        return "下生上"
    if KE[gw] == zw:
        return "上克下"
    return "下克上"


def ganzhi_level(gan, zhi):
    """
    返回 (等级, 类型, 说明)
    等级：上等 / 中等 / 下等
    """
    gz = gan + zhi
    t = ganzhi_type(gan, zhi)
    he = shangxia_he(gan, zhi)

    if he:
        return "上等", t, f"{gz}：上下相合（{gan}与{zhi}中{he}合），有情，属上等"
    if t in ("上生下", "下生上", "上下同"):
        return "上等", t, f"{gz}：{TYPE_DESC[t]}，有情/同类，属上等"
    if t == "上克下":
        return "中等", t, f"{gz}：{TYPE_DESC[t]}，尊制卑，属中等"
    return "下等", t, f"{gz}：{TYPE_DESC[t]}，卑克尊为冒犯，属{ '下等' }"


def four_levels(pillars):
    """
    pillars: [(干,支)] × 4
    返回逐柱等级与总体判断
    """
    names = ["年", "月", "日", "时"]
    detail = []
    for i, (g, z) in enumerate(pillars):
        lv, tp, desc = ganzhi_level(g, z)
        detail.append({"柱": names[i], "干支": g + z, "等级": lv, "类型": tp, "说明": desc})

    counts = {"上等": 0, "中等": 0, "下等": 0}
    for d in detail:
        counts[d["等级"]] += 1

    day_level = detail[2]["等级"]
    if counts["下等"] == 0 and counts["上等"] >= 3:
        overall = "上等结构"
    elif counts["下等"] >= 3:
        overall = "下等结构"
    elif counts["上等"] >= 2:
        overall = "偏上"
    elif counts["下等"] >= 2:
        overall = "偏下"
    else:
        overall = "中等"

    return {
        "逐柱": detail,
        "统计": counts,
        "日主等级": day_level,
        "总体": overall,
        "提示": ("此为戴氏快速判断法的客观化尝试，原书明确它"
                 "「不是绝对可靠的」，必须结合用神与格局一起看。"),
    }


def render_levels(r):
    L = []
    a = L.append
    a("逐柱：" + "　".join(f"{d['柱']}{d['干支']}={d['等级']}" for d in r["逐柱"]))
    for d in r["逐柱"]:
        a("　" + d["说明"])
    s = r["统计"]
    a(f"统计：上等 {s['上等']}　中等 {s['中等']}　下等 {s['下等']}　"
      f"日主{ r['日主等级']}　→ {r['总体']}")
    a(f"⚠ {r['提示']}")
    return "\n".join(L)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    # 书中的例子：郑先生 己卯 戊辰 戊子 甲寅，书载等级（下）（上）（上）（上）
    zheng = [("己", "卯"), ("戊", "辰"), ("戊", "子"), ("甲", "寅")]
    print("郑先生 己卯 戊辰 戊子 甲寅（原书标注：下·上·上·上）")
    print(render_levels(four_levels(zheng)))
