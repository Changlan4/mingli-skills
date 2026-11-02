# -*- coding: utf-8 -*-
"""
十干调候用神表（《穷通宝鉴》调候用神，经梁湘润编、陆致极《基础教程》表5.3 转录）

来源：陆致极《八字命理学基础教程》第五章 p100 表 5.3「调候用神表」。
     原书说明：「以十干配十二月，察其生旺休囚，以定取用之准则」，共一百二十组。

⚠ 数据说明：
   本表由人工对照原书页图转录。个别单元格原书为两行小字（如「庚丙戊」+「丁己」），
   此处按原书排列顺序合并为一行，顺序即原书从上到下、从左到右。
   若某格结论对本技能输出起决定作用，请回查原书 p100 核对。

用法：
    from tiaohou import tiaohou_yongshen
    tiaohou_yongshen("辛", "辰")   -> ["壬", "甲"]   # 辛金生辰月的调候用神
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bazi_const import GAN, ZHI

# 列顺序：寅 卯 辰 巳 午 未 申 酉 戌 亥 子 丑（正月到十二月）
MONTH_ORDER = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"]
MONTH_NAME = {
    "寅": "正月", "卯": "二月", "辰": "三月", "巳": "四月", "午": "五月", "未": "六月",
    "申": "七月", "酉": "八月", "戌": "九月", "亥": "十月", "子": "十一月", "丑": "十二月",
}

# 每行 12 格，按 MONTH_ORDER 排列。空字符串表示原书该格为空。
_TABLE = {
    "甲": ["丙癸", "庚丙戊丁己", "庚丁壬", "癸丁庚", "癸丁庚", "癸丁庚",
           "庚丁壬", "庚丁丙", "庚甲壬丁癸", "庚丁戊丙", "丁庚丙", "丁庚丙"],
    "乙": ["丙癸", "丙癸", "癸丙戊", "癸", "癸丙", "癸丙",
           "丙癸己", "癸丙丁", "癸辛", "丙戊", "丙", "丙"],
    "丙": ["壬庚", "壬己", "壬甲", "壬庚癸", "壬庚", "壬庚",
           "壬戊", "壬癸", "甲壬", "甲戊庚壬", "壬戊己", "壬甲"],
    "丁": ["甲庚", "庚甲", "甲庚", "甲庚", "壬庚癸", "甲壬庚",
           "甲庚丙戊", "甲庚丙戊", "甲庚戊", "甲庚", "甲庚", "甲庚"],
    "戊": ["丙甲癸", "丙甲癸", "甲丙癸", "甲丙癸", "壬甲丙", "癸丙甲",
           "丙癸甲", "丙癸", "甲丙", "甲丙", "丙甲", "丙甲"],
    "己": ["丙庚甲", "甲癸丙", "丙癸甲", "癸丙", "癸丙", "癸丙",
           "丙癸", "丙癸", "甲丙癸", "丙甲戊", "丙甲戊", "丙甲戊"],
    "庚": ["戊甲丙壬丁", "丁甲丙庚", "甲丁壬癸", "壬戊丙丁", "壬癸", "丁甲",
           "丁甲", "丁甲丙", "甲壬", "丁丙", "丁甲丙", "丙丁甲"],
    "辛": ["己壬庚", "壬甲", "壬甲", "壬甲癸", "壬己癸", "壬庚甲",
           "壬甲戊", "壬甲", "壬甲", "壬丙", "丙戊壬甲", "丙壬戊己"],
    "壬": ["庚丙戊", "戊辛庚", "甲庚", "壬辛庚癸", "癸庚辛", "辛甲",
           "戊丁", "甲庚", "甲丙", "戊丙庚", "戊丙", "丙丁甲"],
    "癸": ["辛丙", "庚辛", "丙辛甲", "辛", "庚壬癸", "庚辛壬癸",
           "丁", "辛丙", "辛甲壬癸", "庚辛戊丁", "丙辛", "丙丁"],
}

TIAOHOU = {}
for day_gan, row in _TABLE.items():
    TIAOHOU[day_gan] = {MONTH_ORDER[i]: row[i] for i in range(12)}


def tiaohou_yongshen(day_gan, month_zhi):
    """
    返回 (用神字符串列表, 原始串)。
    原书每格按重要程度排列，第一个字通常是首要调候用神。
    """
    if day_gan not in TIAOHOU or month_zhi not in TIAOHOU[day_gan]:
        return [], ""
    raw = TIAOHOU[day_gan][month_zhi]
    return list(raw), raw


def check_against_chart(day_gan, month_zhi, pillars):
    """
    调候用神在命局中的落实情况：透干 / 藏支 / 全无。
    pillars: [(干,支)]×4
    """
    from bazi_const import CANG_GAN
    gans = [g for g, z in pillars]
    all_hides = set()
    for g, z in pillars:
        all_hides.update(CANG_GAN[z])
    need, raw = tiaohou_yongshen(day_gan, month_zhi)
    out = []
    for g in need:
        if g in gans:
            out.append((g, "透干"))
        elif g in all_hides:
            out.append((g, "藏支"))
        else:
            out.append((g, "缺"))
    return out, raw


def render_table():
    L = ["日干＼月支　" + "　".join(ZHI_M for ZHI_M in MONTH_ORDER)]
    for g in GAN:
        cells = [TIAOHOU[g][m] or "—" for m in MONTH_ORDER]
        L.append(f"{g}　　　　　" + "　".join(cells))
    return "\n".join(L)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(render_table())
    print()
    print("辛金辰月调候用神：", tiaohou_yongshen("辛", "辰"))
    print("甲木寅月调候用神：", tiaohou_yongshen("甲", "寅"))
    print("丙火午月调候用神：", tiaohou_yongshen("丙", "午"))


# ---------------------------------------------------------------- 寒暖燥湿计分
# 陆致极自创的量化工具（原书 p103 表5.4/5.5/5.6）。
# 暖燥记正值、寒湿记负值。三张表相加得出命局的寒暖燥湿总倾向。

TEMP_GAN = {"甲": 3, "乙": 1, "丙": 6, "丁": 4, "戊": 5,
            "己": -4, "庚": -1, "辛": -3, "壬": -5, "癸": -6}
TEMP_ZHI = {"寅": 3, "卯": 1, "辰": -4, "巳": 5, "午": 6, "未": 3,
            "申": -2, "酉": -3, "戌": 4, "亥": -5, "子": -6, "丑": -4}
TEMP_MONTH = {"寅": 0, "卯": 1, "辰": 2, "巳": 3, "午": 4, "未": 3,
              "申": 0, "酉": -1, "戌": -2, "亥": -3, "子": -4, "丑": -4}


def temp_score(pillars):
    """
    返回寒暖燥湿计分明细。
    校验：王安石 辛酉 庚子 癸未 丙辰 → 天干 -4、地支 -10、月令 -4，合计 -18（与原书标注一致）
    """
    gan = [TEMP_GAN[g] for g, z in pillars]
    zhi = [TEMP_ZHI[z] for g, z in pillars]
    month = TEMP_MONTH[pillars[1][1]]
    total = sum(gan) + sum(zhi) + month
    if total >= 12:
        judge = "暖燥过甚"
    elif total >= 6:
        judge = "偏暖燥"
    elif total > -6:
        judge = "寒暖较中和"
    elif total > -12:
        judge = "偏寒湿"
    else:
        judge = "寒湿过甚"
    return {
        "天干计分": gan, "地支计分": zhi, "月令加分": month,
        "合计": total, "判断": judge,
        "调候方向": ("宜癸水滋润" if total >= 6 else
                     "宜丙火照暖" if total <= -6 else "无需强作调候"),
    }
