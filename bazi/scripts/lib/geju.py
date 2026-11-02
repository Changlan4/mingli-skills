# -*- coding: utf-8 -*-
"""
格局分析（陆致极《基础教程》第六章「十神和格局」、第七章「格局述要」）

书中要点（p118-123）：
  * 格局共十种：伤官、食神、正财、偏财、正官、七杀、正印、偏印、建禄、劫刃。
  * 取格不是看月令一个字了事，而是「比较八字结构中存在的各种势力，
    从中选取最能影响此结构的主导力量，以此（十神）为格局」。
  * 日主在月支为临官（禄）→ 建禄格；为帝旺（刃）→ 劫刃格。
    这两格不以月令藏干取格。

本模块给出的是**候选与依据**，不是判决。书中用连线图法（操作-1）人工研判，
那是视觉化的势力权衡；这里用可复现的计数近似，逐条列出证据，
让解读层（模型）在证据上做最终取舍。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bazi_const import GAN, ZHI, CANG_GAN, GAN_WUXING, GAN_YINYANG, shishen
from strength import changsheng

GE_NAMES = ["伤官", "食神", "正财", "偏财", "正官", "七杀", "正印", "偏印"]

# 天干五合：合则两干皆受牵制，成格能力受损。
# 命例甲正是「乙木偏财遭月干庚金劫财合克」，故偏财不能成格（原书 p215）。
HE_PAIRS = [("甲", "己"), ("乙", "庚"), ("丙", "辛"), ("丁", "壬"), ("戊", "癸")]


def detect_gan_he(gans):
    """返回 [(i, j, 干i, 干j)]，i/j 为四柱位置"""
    res = []
    for i in range(4):
        for j in range(i + 1, 4):
            for a, b in HE_PAIRS:
                if {gans[i], gans[j]} == {a, b}:
                    res.append((i, j, gans[i], gans[j]))
    return res


def shishen_weights(pillars, day_gan):
    """
    各十神的力量计数。
    权重口径：天干透出记 1.2（透干力量大），地支本气 1.0，中气 0.5，余气 0.3。
    日主自身不计。
    """
    w = {name: 0.0 for name in GE_NAMES}
    w["比肩"] = 0.0
    w["劫财"] = 0.0
    for i, (g, z) in enumerate(pillars):
        if i != 2:
            w[shishen(day_gan, g)] += 1.2
        hides = CANG_GAN[z]
        for j, h in enumerate(hides):
            val = [1.0, 0.5, 0.3][j] if j < 3 else 0.3
            w[shishen(day_gan, h)] += val
    return w


def geju(pillars, day_gan):
    month_zhi = pillars[1][1]
    gans = [g for g, z in pillars]
    hides = CANG_GAN[month_zhi]
    day_cs = changsheng(day_gan, month_zhi)

    he_list = detect_gan_he(gans)
    he_gans = set()
    he_note = []
    for i, j, a, b in he_list:
        he_gans.add(a); he_gans.add(b)
        he_note.append(f"{['年','月','日','时'][i]}{a} 与 {['年','月','日','时'][j]}{b} 相合")

    roles = ["本气", "中气", "余气"]
    month_info = []
    for j, h in enumerate(hides):
        month_info.append({
            "干": h, "十神": shishen(day_gan, h),
            "位置": roles[j] if j < 3 else "余气",
            "透干": h in gans,
            "被合": h in he_gans,
        })

    weights = shishen_weights(pillars, day_gan)

    # ---- 候选格：月令藏干里能成格的
    candidates = []
    for item in month_info:
        if item["十神"] not in GE_NAMES:
            continue
        if item["透干"] and not item["被合"]:
            candidates.append((item["十神"] + "格", 0,
                               f"月支{month_zhi}藏{item['干']}（{item['位置']}）透干且未被合克"))
        elif item["透干"] and item["被合"]:
            candidates.append((item["十神"] + "格", 2,
                               f"月支{month_zhi}藏{item['干']}（{item['位置']}）虽透干，"
                               f"但与其他天干相合被牵制，成格可疑"))
        else:
            candidates.append((item["十神"] + "格", 1,
                               f"月支{month_zhi}藏{item['干']}（{item['位置']}）未透干，力量不足"))

    # ---- 建禄 / 劫刃（优先于月令藏干）
    if day_cs == "临官":
        main_ge = "建禄格"
        reason = f"日主{day_gan}在月支{month_zhi}为临官（禄），成建禄格，不以月令藏干取格。"
    elif day_cs == "帝旺" and GAN_YINYANG[day_gan] == "阳":
        # 原书表7.4：只有甲、丙、庚、壬四个阳干才有阳刃（阴干无羊刃）。
        main_ge = "劫刃格"
        reason = f"日主{day_gan}为阳干，在月支{month_zhi}为帝旺（阳刃），成劫刃格。"
        if day_gan == "戊":
            reason += ("　注：戊土午月虽亦为刃，但午中藏丁火、己土，火生土、"
                       "印星减了劫刃性质，原书指出「不少命理学家就把戊土生于午月"
                       "排斥在阳刃格之外」，此处从宽判入，需向用户说明此分歧。")
    else:
        # 按传统次序：本气透且未受制 → 中气透 → 余气透 → 退取本气
        main_ge, reason = None, ""
        for item in month_info:
            if item["十神"] in GE_NAMES and item["透干"] and not item["被合"]:
                main_ge = item["十神"] + "格"
                reason = (f"月支{month_zhi}藏{item['干']}（{item['位置']}，{item['十神']}）"
                          f"透干且未被合克，按透干取格。")
                break
        if main_ge is None:
            # 月令透干的全被合克 → 转看全局透出的十神，但必须排除已被合克的那些。
            # 命例甲即此路：乙木偏财被庚合，退取壬水伤官为格（原书 p215）。
            blocked_names = {it["十神"] for it in month_info if it["透干"] and it["被合"]}
            best_global = [(k, v) for k, v in weights.items()
                           if k in GE_NAMES and v > 0 and k not in blocked_names]
            best_global.sort(key=lambda x: -x[1])
            blocked = [it for it in month_info if it["透干"] and it["被合"]]
            if blocked and best_global:
                k, v = best_global[0]
                main_ge = k + "格"
                reason = ("月令所透之" + "、".join(f"{it['十神']}（{it['干']}）" for it in blocked)
                          + f"皆被合克，不能成格；转而取全局力量最强的{k}（{v:.1f}）为格。")
            else:
                for item in month_info:
                    if item["十神"] in GE_NAMES:
                        main_ge = item["十神"] + "格"
                        reason = (f"月支{month_zhi}藏干皆不透，退取{item['位置']}之"
                                  f"{item['干']}（{item['十神']}）为格。")
                        break
        if main_ge is None:
            main_ge = "未定"
            reason = "月令所藏十神均为比劫，且非建禄劫刃，需人工研判。"

    top = sorted(((k, v) for k, v in weights.items() if v > 0),
                 key=lambda x: -x[1])[:4]

    return {
        "月令": month_zhi,
        "日主在月令": day_cs,
        "月令藏干": month_info,
        "天干相合": he_note,
        "候选格": [{"格": n, "优先级": p, "理由": r} for n, p, r in candidates],
        "取格": main_ge,
        "取格依据": reason,
        "十神力量": {k: round(v, 1) for k, v in sorted(weights.items(), key=lambda x: -x[1]) if v > 0},
        "最强势十神": [{"十神": k, "力量": round(v, 1)} for k, v in top],
        "提示": ("取格是候选，不是定论。书中用连线图比较各势力强弱，"
                 "若「最强势十神」与「取格」不一致，务必在解读时说明并请用户确认。"),
    }


def render_geju(g):
    L = []
    a = L.append
    a(f"月令 {g['月令']}，日主在月令为「{g['日主在月令']}」")
    a("月令藏干：" + "　".join(
        f"{x['干']}（{x['位置']}·{x['十神']}{'·透干' if x['透干'] else ''}）"
        for x in g["月令藏干"]))
    a(f"【取格】{g['取格']}")
    a(f"　依据：{g['取格依据']}")
    a("十神力量：" + "　".join(f"{k}{v}" for k, v in g["十神力量"].items()))
    if g["最强势十神"]:
        a("最强势：" + "　".join(f"{x['十神']}{x['力量']}" for x in g["最强势十神"]))
    a(f"⚠ {g['提示']}")
    return "\n".join(L)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    # 书载命例 9：癸巳 甲子 丁酉 甲辰（丁火日主）
    mzd = [("癸", "巳"), ("甲", "子"), ("丁", "酉"), ("甲", "辰")]
    print("命例9 癸巳 甲子 丁酉 甲辰")
    print(render_geju(geju(mzd, "丁")))
    print()
    # 命例甲 乙亥 庚辰 辛未 壬辰，书中明言「伤官格」
    liao = [("乙", "亥"), ("庚", "辰"), ("辛", "未"), ("壬", "辰")]
    print("命例甲 乙亥 庚辰 辛未 壬辰（书中明言伤官格）")
    print(render_geju(geju(liao, "辛")))
