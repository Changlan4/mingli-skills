# -*- coding: utf-8 -*-
"""
干支刑冲会合检测（陆致极《基础教程》第四章 p78-95）

为什么必须由脚本做：刑冲会合是动态分析的地基，人工看盘极易漏项。
实测时（终端验证）发现旧版引擎只输出十神和神煞、不输出刑冲会合，
导致解读全靠人工判断、零交叉验证——这是全流程最大的风险点，本模块专为此而写。

书中关系（页码为 PDF 页）：
  * 天干五合 p79        甲己、乙庚、丙辛、丁壬、戊癸
  * 天干相冲 p79        甲庚、乙辛、丙壬、丁癸（阳冲阳、阴冲阴，"相冲一般不以吉"）
  * 地支六合 p80        子丑、寅亥、卯戌、辰酉、巳申、午未（各有化气）
  * 地支六冲 p81        子午、丑未、寅申、卯酉、辰戌、巳亥
  * 六害 p81-82         子未、丑午、寅巳、卯辰、酉戌、亥申（"相害，有暗害之意，一般也不以吉"）
  * 相刑 p82            无礼之刑 子卯；恃势之刑 寅巳申；无恩之刑 丑戌未；自刑 辰午酉亥
  * 三会方 p83          寅卯辰木、巳午未火、申酉戌金、亥子丑水（"缺一不可"）
  * 三合局 p83          亥卯未木、寅午戌火、申子辰水、巳酉丑金（长生+帝旺+墓库）

注意：本模块只负责"检出关系"，**不判吉凶、不判合化是否成功**。
合化要看引化之神（详见 05-动态与刑冲.md「合与合化」一节）。
"""
import sys
import os
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

NAME = ["年", "月", "日", "时"]

TIANGAN_HE = [("甲", "己"), ("乙", "庚"), ("丙", "辛"), ("丁", "壬"), ("戊", "癸")]
TIANGAN_CHONG = [("甲", "庚"), ("乙", "辛"), ("丙", "壬"), ("丁", "癸")]

DIZHI_LIUHE = {
    ("子", "丑"): "土", ("寅", "亥"): "木", ("卯", "戌"): "火",
    ("辰", "酉"): "金", ("巳", "申"): "水", ("午", "未"): "土",
}
DIZHI_CHONG = [("子", "午"), ("丑", "未"), ("寅", "申"),
               ("卯", "酉"), ("辰", "戌"), ("巳", "亥")]
DIZHI_HAI = [("子", "未"), ("丑", "午"), ("寅", "巳"),
             ("卯", "辰"), ("酉", "戌"), ("亥", "申")]

# 相刑（p82）
XING_3 = {
    frozenset({"寅", "巳", "申"}): "恃势之刑",
    frozenset({"丑", "戌", "未"}): "无恩之刑",
}
XING_2 = [("子", "卯")]          # 无礼之刑
ZIXING = ["辰", "午", "酉", "亥"]  # 自刑

SANHE = {"申子辰": "水", "寅午戌": "火", "巳酉丑": "金", "亥卯未": "木"}
SANHUI = {"寅卯辰": "木", "巳午未": "火", "申酉戌": "金", "亥子丑": "水"}


def _pair_key(a, b):
    return frozenset({a, b})


def analyze(pillars, extra=None, extra_name="运/年"):
    """
    pillars: [(干,支)] × 4
    extra:   可选，如大运/流年的 (干,支)，参与和原局的关系判断
    返回结构化结果
    """
    items = [(NAME[i], pillars[i][0], pillars[i][1]) for i in range(4)]
    if extra:
        items.append((extra_name, extra[0], extra[1]))

    res = {
        "天干合": [], "天干冲": [],
        "地支六合": [], "地支六冲": [], "地支六害": [],
        "相刑": [], "三合局": [], "半合": [], "三会方": [],
        "摘要": [],
    }

    # ---- 天干：合 / 冲
    for (n1, g1, _), (n2, g2, _) in combinations(items, 2):
        for a, b in TIANGAN_HE:
            if _pair_key(g1, g2) == _pair_key(a, b):
                res["天干合"].append(
                    {"位": f"{n1}{g1}·{n2}{g2}", "合": f"{a}{b}合", "说明": "合而不化待判（需引化之神）"})
        for a, b in TIANGAN_CHONG:
            if _pair_key(g1, g2) == _pair_key(a, b):
                res["天干冲"].append({"位": f"{n1}{g1}·{n2}{g2}", "冲": f"{a}{b}冲"})

    # ---- 地支：六合 / 六冲 / 六害
    for (n1, _, z1), (n2, _, z2) in combinations(items, 2):
        k = _pair_key(z1, z2)
        for pair, hua in DIZHI_LIUHE.items():
            if k == _pair_key(*pair):
                res["地支六合"].append(
                    {"位": f"{n1}{z1}·{n2}{z2}", "合": f"{pair[0]}{pair[1]}合", "化": hua})
        for a, b in DIZHI_CHONG:
            if k == _pair_key(a, b):
                res["地支六冲"].append({"位": f"{n1}{z1}·{n2}{z2}", "冲": f"{a}{b}冲"})
        for a, b in DIZHI_HAI:
            if k == _pair_key(a, b):
                res["地支六害"].append({"位": f"{n1}{z1}·{n2}{z2}", "害": f"{a}{b}害"})
        for a, b in XING_2:
            if k == _pair_key(a, b):
                res["相刑"].append({"位": f"{n1}{z1}·{n2}{z2}", "刑": f"{a}{b}刑", "名": "无礼之刑"})

    # ---- 自刑
    zhi_count = {}
    for n, _, z in items:
        zhi_count.setdefault(z, []).append(n)
    for z, names in zhi_count.items():
        if z in ZIXING and len(names) >= 2:
            res["相刑"].append({"位": f"{'/'.join(names)}{z}", "刑": f"{z}{z}自刑", "名": "自刑"})

    # ---- 三刑（三字齐）
    all_zhi = {z: [] for _, _, z in items}
    for n, _, z in items:
        all_zhi[z].append(n)
    for combo, label in XING_3.items():
        if all(z in all_zhi for z in combo):
            res["相刑"].append({
                "位": "、".join(f"{'/'.join(all_zhi[z])}{z}" for z in sorted(combo)),
                "刑": "＋".join(sorted(combo)) + "三刑", "名": label})

    # ---- 三合局（三字齐）/ 半合（两字）
    for combo, wx in SANHE.items():
        present = [z for z in combo if z in all_zhi]
        if len(present) == 3:
            res["三合局"].append({
                "位": "、".join(f"{'/'.join(all_zhi[z])}{z}" for z in combo),
                "局": f"{combo}三合{wx}局"})
        elif len(present) == 2:
            # 含中神（第二个字）才叫半合，否则只是"拱"
            mid = combo[1]
            label = "半合" if mid in present else "两字（缺中神，属拱）"
            res["半合"].append({
                "位": "、".join(f"{'/'.join(all_zhi[z])}{z}" for z in present),
                "局": f"{''.join(present)}{label}{wx}"})

    # ---- 三会方
    for combo, wx in SANHUI.items():
        if all(z in all_zhi for z in combo):
            res["三会方"].append({
                "位": "、".join(f"{'/'.join(all_zhi[z])}{z}" for z in combo),
                "会": f"{combo}三会{wx}方"})

    # ---- 摘要
    for k in ("天干合", "天干冲", "地支六合", "地支六冲", "地支六害"):
        for x in res[k]:
            res["摘要"].append(f"{x['位']} {list(x.values())[1]}")
    for x in res["相刑"]:
        res["摘要"].append(f"{x['位']} {x['刑']}（{x['名']}）")
    for k in ("三合局", "半合", "三会方"):
        for x in res[k]:
            res["摘要"].append(f"{x['位']} {list(x.values())[1]}")

    return res


def render(r):
    L = []
    a = L.append
    if not r["摘要"]:
        a("命局内部未检出合冲刑害关系。")
        return "\n".join(L)
    for k, title in (("天干合", "天干合"), ("天干冲", "天干冲"),
                     ("地支六合", "地支六合"), ("地支六冲", "地支六冲"),
                     ("地支六害", "六害"), ("相刑", "相刑"),
                     ("三合局", "三合局"), ("半合", "半合/拱"), ("三会方", "三会方")):
        if not r[k]:
            continue
        parts = []
        for x in r[k]:
            vals = [v for kk, v in x.items() if kk not in ("位", "说明", "名")]
            s = f"{x['位']}={'/'.join(vals)}"
            if x.get("名"):
                s += f"（{x['名']}）"
            if x.get("说明"):
                s += f"［{x['说明']}］"
            parts.append(s)
        a(f"{title}：" + "　".join(parts))
    return "\n".join(L)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    # 终端验证用的盘：乙丑 己卯 庚戌 癸未
    p = [("乙", "丑"), ("己", "卯"), ("庚", "戌"), ("癸", "未")]
    print("乙丑 己卯 庚戌 癸未")
    print(render(analyze(p)))
    print()
    # 胡适：辛卯 庚子 丁丑 丁未（书载：子丑合、丑未冲、卯未半合木局）
    p2 = [("辛", "卯"), ("庚", "子"), ("丁", "丑"), ("丁", "未")]
    print("辛卯 庚子 丁丑 丁未（书载：子丑合、丑未冲、卯未半合木局）")
    print(render(analyze(p2)))
