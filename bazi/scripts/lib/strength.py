# -*- coding: utf-8 -*-
"""
日主强弱分析（陆致极《基础教程》第三章的"强弱图解分析法"）

书中方法（p62-68）分两层，本模块两层都实现：

  第一层 定性三要素（命例 1 命例丙 p62）：
      得令 —— 日主五行在月令处于「旺」或「相」
      得地 —— 日主在四地支中有根（长生/临官/帝旺，或墓库余气）
      得助 —— 有比劫帮身、印星生身（天干透出或地支藏干）
      三项全得 → 最强；逐项递减。

  第二层 定量图解（p65-68「强弱圖解分析法」）：
      操作-1 只数天干与地支本气（每个计 1）
      操作-2 再数地支藏干的中气/余气（每个计 1，记为括号内）
      操作-3 按月令给每种五行标 旺/相/休/囚/死
      操作-4 汇总「日主同方」（同我+生我）与「日主异方」（克我+我克+我生），比大小
      强弱分 9 档：极强 很强 强 稍强 中和 稍弱 弱 很弱 极弱

校验锚点（书中原文结论）：
      命例乙   辛卯 庚子 丁丑 丁未  同方3(2) 异方5(2)  → 弱
      命例丙 戊午 乙卯 甲子 乙亥  同方6(1) 异方2(1)  → 很强（得令得地得助三项全得）
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bazi_const import (
    GAN, ZHI, GAN_WUXING, CANG_GAN, SHENG, KE, CHANGSHENG_START,
    CHANGSHENG_NAMES,
)

TONG = "同方"
YI = "异方"


def changsheng(day_gan, zhi):
    from bazi_const import GAN_YINYANG
    start = CHANGSHENG_START[day_gan]
    offset = (ZHI.index(zhi) - ZHI.index(start)) % 12
    if GAN_YINYANG[day_gan] == "阴":
        offset = (-offset) % 12
    return CHANGSHENG_NAMES[offset]


def sheng_wo(wx):
    """生我者"""
    for k, v in SHENG.items():
        if v == wx:
            return k
    return None


def ke_wo(wx):
    """克我者"""
    for k, v in KE.items():
        if v == wx:
            return k
    return None


def wangxiang_table(month_zhi):
    """
    五行四时用事：当令者旺，令生者相，生令者休，克令者囚，令克者死。
    例：子月（水令）→ 水旺、木相、金休、土囚、火死
    """
    ling = ZHI_WUXING(month_zhi)
    return {
        ling: "旺",
        SHENG[ling]: "相",
        sheng_wo(ling): "休",
        ke_wo(ling): "囚",
        KE[ling]: "死",
    }


def ZHI_WUXING(z):
    return {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
            "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"}[z]


def classify(day_wx, wx):
    """某种五行相对日主属同方还是异方"""
    if wx == day_wx or wx == sheng_wo(day_wx):
        return TONG      # 同我、生我
    return YI            # 克我、我克、我生


def tujie(pillars, day_gan):
    """
    操作-1 / 操作-2：图解计数。
    返回 {五行: {"本气": n, "附气": m}}，其中本气=天干+地支本气（各1），
    附气=地支藏干的中气/余气（各1）。
    """
    day_wx = GAN_WUXING[day_gan]
    stat = {wx: {"本气": 0, "附气": 0} for wx in ["木", "火", "土", "金", "水"]}
    for g, z in pillars:
        stat[GAN_WUXING[g]]["本气"] += 1
        hides = CANG_GAN[z]
        stat[GAN_WUXING[hides[0]]]["本气"] += 1
        for h in hides[1:]:
            stat[GAN_WUXING[h]]["附气"] += 1
    return stat


def strength(pillars, day_gan):
    """
    pillars: [(干,支)] × 4
    返回完整强弱分析结果
    """
    day_wx = GAN_WUXING[day_gan]
    month_zhi = pillars[1][1]
    wx_tab = wangxiang_table(month_zhi)
    stat = tujie(pillars, day_gan)

    # ---- 操作-3：标旺相休囚死
    marked = {}
    for wx, v in stat.items():
        marked[wx] = {"本气": v["本气"], "附气": v["附气"], "状态": wx_tab[wx],
                      "阵营": classify(day_wx, wx)}

    # ---- 操作-4：汇总同方 / 异方
    tong_n = tong_f = yi_n = yi_f = 0
    tong_detail, yi_detail = [], []
    for wx, v in marked.items():
        if v["阵营"] == TONG:
            tong_n += v["本气"]; tong_f += v["附气"]
            tong_detail.append(f"{wx}{v['状态']} {v['本气']}({v['附气']})")
        else:
            yi_n += v["本气"]; yi_f += v["附气"]
            yi_detail.append(f"{wx}{v['状态']} {v['本气']}({v['附气']})")

    # ---- 第一层：得令 / 得地 / 得助
    day_state = wx_tab[day_wx]
    de_ling = day_state in ("旺", "相")

    # 得地：日主在四地支中的十二长生，有强根才算得地（长生/临官/帝旺）。
    # 墓库与冠带单列为"弱根"，不计入得地——书里命例乙就不以丑未为得地。
    roots, weak_roots = [], []
    for i, (g, z) in enumerate(pillars):
        cs = changsheng(day_gan, z)
        if cs in ("长生", "临官", "帝旺"):
            roots.append((["年", "月", "日", "时"][i], z, cs))
        elif cs in ("冠带", "墓"):
            weak_roots.append((["年", "月", "日", "时"][i], z, cs))
    de_di = bool(roots)

    # 得助：比劫（同我）与印（生我）在天干透出或地支藏干
    help_list = []
    for i, (g, z) in enumerate(pillars):
        gw = GAN_WUXING[g]
        if i != 2 and (gw == day_wx or gw == sheng_wo(day_wx)):
            help_list.append(f"干{g}")
        for h in CANG_GAN[z]:
            if GAN_WUXING[h] == day_wx or GAN_WUXING[h] == sheng_wo(day_wx):
                help_list.append(f"支{z}藏{h}")
    de_zhu = len(help_list) >= 3

    gained = sum([de_ling, de_di, de_zhu])

    # ---- 9 档判定
    # 说明：书中给出的锚点是 命例乙(同3异5/得令否) → 弱、命例丙(同6异2/三得) → 很强。
    # 这里先用"同方计数值(含附气) - 异方计数值"作主轴，再用三要素校正，
    # 属于对书中案例的可解释近似，不是书中逐字公式。规则卡里会标注这一点。
    total_tong = tong_n + tong_f
    total_yi = yi_n + yi_f
    diff = total_tong - total_yi
    ratio = total_tong / total_yi if total_yi else 99.0

    # ---- 9 档判定
    # 四个可对照的书载锚点：
    #   命例乙    同3(2) vs 异5(2)，得1/3   → 弱       （基础 p67）
    #   命例丙  同6(1) vs 异2(1)，得3/3   → 很强     （基础 p68）
    #   命例丁  同2(0) vs 异6(6)，得1/3，但时支寅帝旺 → 弱（动态 p26，
    #           原书：「只有时支寅木（帝旺）可以为根，故没有到很弱的地步」）
    #   命例戊  同7 vs 异8，差值 -1，但得3/3 → 很强   （动态 p87，
    #           原书：「丁火生夏季午月当令，天干有甲木正印、丙火劫财，
    #           地支有巳（帝旺）、午（禄），自身显然很强」）
    #
    # 从命例戊这一例可以确定：**三要素全得时，不受数目差值的压制。**
    # 得令+得地+得助本就是传统"身强"的完整标志；数目里异方再多（官杀财重），
    # 也不改变日主自身强这个事实（那正是"身强杀旺"之类格局）。
    if gained == 3:
        level = "极强" if diff >= 8 else "很强"
    elif gained == 2:
        level = "强"
    elif diff >= 4:
        level = "强"
    elif diff >= 2:
        level = "稍强"
    elif diff >= -1:
        level = "中和" if diff >= 0 else "稍弱"
    elif diff >= -3:
        level = "弱"
    elif de_di:
        level = "弱"          # 有长生/临官/帝旺之根：弱而不到很弱
    elif diff >= -6:
        level = "很弱"
    else:
        level = "极弱"

    return {
        "日主": day_gan, "日主五行": day_wx,
        "月令": month_zhi, "月令五行": ZHI_WUXING(month_zhi),
        "日主在月令状态": day_state,
        "旺相休囚死": wx_tab,
        "图解明细": marked,
        "日主同方": {"本气": tong_n, "附气": tong_f, "明细": tong_detail},
        "日主异方": {"本气": yi_n, "附气": yi_f, "明细": yi_detail},
        "同方计": total_tong, "异方计": total_yi, "差值": diff,
        "得令": de_ling, "得地": de_di, "得地之根": roots, "弱根": weak_roots, "得助": de_zhu,
        "得助明细": sorted(set(help_list)),
        "三要素": f"{'得令' if de_ling else '不得令'}、{'得地' if de_di else '不得地'}、"
                  f"{'得助' if de_zhu else '不得助'}（得 {gained}/3）",
        "强弱档位": level,
    }


def render_strength(s):
    L = []
    a = L.append
    a(f"日主 {s['日主']}{s['日主五行']}　月令 {s['月令']}（{s['月令五行']}）→ 日主处于「{s['日主在月令状态']}」")
    a("旺相休囚死：" + "　".join(f"{k}{v}" for k, v in s["旺相休囚死"].items()))
    a("")
    a(f"操作-1/2 图解计数（本气 + 括号内附气）：")
    for wx, v in s["图解明细"].items():
        a(f"　{wx} {v['本气']}（{v['附气']}）　{v['状态']}　{v['阵营']}")
    a("")
    t, y = s["日主同方"], s["日主异方"]
    a(f"日主同方（同我+生我）＝ {t['本气']}（{t['附气']}）　" + "、".join(t["明细"]))
    a(f"日主异方（克我+我克+我生）＝ {y['本气']}（{y['附气']}）　" + "、".join(y["明细"]))
    a(f"　→ 同方计 {s['同方计']}　异方计 {s['异方计']}　差值 {s['差值']:+d}")
    a("")
    a(f"三要素：{s['三要素']}")
    if s["得地之根"]:
        a("　得地之根：" + "、".join(f"{n}支{z}（{cs}）" for n, z, cs in s["得地之根"]))
    if s.get("弱根"):
        a("　弱根（冠带/墓，不计入得地）：" + "、".join(f"{n}支{z}（{cs}）" for n, z, cs in s["弱根"]))
    if s["得助明细"]:
        a("　得助来源：" + "、".join(s["得助明细"]))
    a("")
    a(f"【强弱档位】{s['强弱档位']}　（九档：极强·很强·强·稍强·中和·稍弱·弱·很弱·极弱）")
    return "\n".join(L)
