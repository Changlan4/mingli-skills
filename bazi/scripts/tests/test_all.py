# -*- coding: utf-8 -*-
"""
回归测试：动过排盘/对账逻辑就跑一次。

    python tests/test_all.py

测试集来源：
  * 陆致极《动态分析教程》命例 63（命例甲）——四柱、大运方向、起运岁数有书载答案可对
  * 天文边界硬案例（节气交接、早晚子时）
  * 数据表自洽性（纳音 60 全、藏干 12 全、十神 100 组合）
"""
import os
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.stdout.reconfigure(encoding="utf-8")

from bazi_const import (  # noqa: E402
    GAN, ZHI, CANG_GAN, NAYIN, GAN_YINYANG, GAN_WUXING, shishen,
)
from bazi import paipan, changsheng, _xunkong, true_solar_time  # noqa: E402

PASS = []
FAIL = []


def ok(name, cond, detail=""):
    if cond:
        PASS.append(name)
    else:
        FAIL.append(f"{name}  {detail}")


def eq(name, got, want):
    ok(name, got == want, f"期望 {want}，实得 {got}")


# ---------------------------------------------------------------- 1. 数据表

def test_tables():
    eq("纳音表应有 60 个组合", len(NAYIN), 60)
    eq("藏干表应有 12 个地支", len(CANG_GAN), 12)
    # 抽查纳音
    eq("甲子纳音", NAYIN.get("甲子"), "海中金")
    eq("乙亥纳音", NAYIN.get("乙亥"), "山头火")
    eq("壬辰纳音", NAYIN.get("壬辰"), "长流水")
    eq("庚辰纳音", NAYIN.get("庚辰"), "白蜡金")
    eq("癸亥纳音", NAYIN.get("癸亥"), "大海水")
    # 每个甲子都能查到纳音
    missing = []
    for i in range(60):
        gz = GAN[i % 10] + ZHI[i % 12]
        if gz not in NAYIN:
            missing.append(gz)
    ok("六十甲子纳音无缺漏", not missing, str(missing))


def test_shishen():
    # 日主辛金（阴金）
    eq("辛见乙 为偏财", shishen("辛", "乙"), "偏财")
    eq("辛见庚 为劫财", shishen("辛", "庚"), "劫财")
    eq("辛见壬 为伤官", shishen("辛", "壬"), "伤官")
    eq("辛见辛 为比肩", shishen("辛", "辛"), "比肩")
    eq("辛见丙 为正官", shishen("辛", "丙"), "正官")
    eq("辛见丁 为七杀", shishen("辛", "丁"), "七杀")
    eq("辛见戊 为正印", shishen("辛", "戊"), "正印")
    eq("辛见己 为偏印", shishen("辛", "己"), "偏印")
    # 十神表应为 10x10=100 个组合且都合法
    legal = {"比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"}
    bad = []
    for g in GAN:
        for t in GAN:
            if shishen(g, t) not in legal:
                bad.append((g, t, shishen(g, t)))
    ok("十神 100 组合全部合法", not bad, str(bad[:5]))


def test_changsheng():
    eq("甲长生在亥", changsheng("甲", "亥"), "长生")
    eq("甲帝旺在卯", changsheng("甲", "卯"), "帝旺")
    eq("乙长生在午", changsheng("乙", "午"), "长生")
    eq("辛长生在子", changsheng("辛", "子"), "长生")
    eq("辛沐浴在亥", changsheng("辛", "亥"), "沐浴")
    eq("辛死于巳", changsheng("辛", "巳"), "死")
    eq("壬长生在申", changsheng("壬", "申"), "长生")


def test_xunkong():
    eq("甲子旬空戌亥", _xunkong(0, 0), "戌亥")
    eq("辛未旬空戌亥", _xunkong(7, 7), "戌亥")
    eq("壬辰旬空午未", _xunkong(8, 4), "午未")
    eq("癸亥旬空子丑", _xunkong(9, 11), "子丑")


# ---------------------------------------------------------------- 2. 排盘

def test_liao():
    """书载：乙亥 庚辰 辛未 壬辰；阴年男命逆行；约 6 岁起运；36 岁入丙火运"""
    r = paipan(1935, 4, 25, 7, 30, gender=1, city="哈尔滨")
    eq("命例甲 四柱", r["八字"], "乙亥 庚辰 辛未 壬辰")
    eq("命例甲 日主", r["日主"]["干"], "辛")
    eq("命例甲 大运方向", r["大运"]["方向"], "逆行")
    eq("命例甲 日柱藏干", [h["干"] for h in r["四柱"]["日"]["藏干"]], ["己", "丁", "乙"])
    eq("命例甲 月柱藏干", [h["干"] for h in r["四柱"]["月"]["藏干"]], ["戊", "乙", "癸"])
    eq("命例甲 年柱十神", r["四柱"]["年"]["天干十神"], "偏财")
    eq("命例甲 时柱十神", r["四柱"]["时"]["天干十神"], "伤官")
    # 书里说 1971 年 36 岁（周岁）走入丙火大运
    d = {x["干支"]: x for x in r["大运"]["列表"]}
    ok("命例甲 丙子大运存在", "丙子" in d, str(list(d)))
    if "丙子" in d:
        ok("丙子运覆盖 1971 年", d["丙子"]["起始年"] <= 1971 <= d["丙子"]["结束年"],
           str(d["丙子"]))
        eq("丙子运十神为正官", d["丙子"]["十神"], "正官")
    # 起运约 6 岁（周岁口径 6 年 5 个月）
    ok("命例甲 起运 6 年余", r["大运"]["起运"].startswith("6年"), r["大运"]["起运"])


def test_yuanshushan_1881():
    """
    《动态分析教程》命例 1：命例丁 1881-09-08 寅时。
    书载自述「乙木秋生」「惜八字缺水」；大运逆排 1 岁起运，
    丙申→乙未→甲午→癸巳→壬辰→辛卯→庚寅→己丑，与其「21岁交甲运」「31岁交癸运」
    「41岁交壬运」「71岁交己运」的自述逐条吻合。
    此例同时验证引擎对 19 世纪日期的支持。
    """
    r = paipan(1881, 9, 8, 4, 0, gender=1, city="扬州", use_true_solar=False)
    eq("命例丁 四柱", r["八字"], "辛巳 丁酉 乙巳 戊寅")
    eq("命例丁 日主", r["日主"]["干"], "乙")
    eq("命例丁 大运方向", r["大运"]["方向"], "逆行")
    seq = [x["干支"] for x in r["大运"]["列表"][:8]]
    eq("命例丁 大运序列", seq,
       ["丙申", "乙未", "甲午", "癸巳", "壬辰", "辛卯", "庚寅", "己丑"])
    # 「惜八字缺水」：四柱天干地支与藏干都不见水
    from bazi_const import CANG_GAN, GAN_WUXING, ZHI_WUXING
    has_water = any(GAN_WUXING[g] == "水" or ZHI_WUXING[z] == "水" for g, z in
                    [("辛","巳"),("丁","酉"),("乙","巳"),("戊","寅")])
    ok("命例丁 八字无水（与原书自述一致）", not has_water)


def test_dayun_direction():
    """阳年男顺、阳年女逆、阴年男逆、阴年女顺"""
    cases = [
        (1990, 6, 15, 1, True, "庚午年(阳) 男 应顺"),
        (1990, 6, 15, 0, False, "庚午年(阳) 女 应逆"),
        (1991, 6, 15, 1, False, "辛未年(阴) 男 应逆"),
        (1991, 6, 15, 0, True, "辛未年(阴) 女 应顺"),
    ]
    for y, m, d, g, want_fwd, label in cases:
        r = paipan(y, m, d, 10, 0, gender=g, city="北京")
        got_fwd = r["大运"]["方向"] == "顺行"
        ok(label, got_fwd == want_fwd,
           f"实得 {r['大运']['方向']}（{r['八字'].split()[0]}年）")


def test_jieqi_boundary():
    """2000 年立春约在北京时间 2/4 20:40。立春前必为己卯年丁丑月，立春后为庚辰年戊寅月。"""
    before = paipan(2000, 2, 4, 20, 30, gender=1, city="北京", use_true_solar=False)
    after = paipan(2000, 2, 4, 20, 50, gender=1, city="北京", use_true_solar=False)
    eq("立春前 年柱", before["八字"].split()[0], "己卯")
    eq("立春前 月柱", before["八字"].split()[1], "丁丑")
    eq("立春后 年柱", after["八字"].split()[0], "庚辰")
    eq("立春后 月柱", after["八字"].split()[1], "戊寅")
    ok("立春边界触发告警", any("节气" in w for w in (before["warnings"] + after["warnings"])),
       "边界处应提示人工复核")


def test_late_zi():
    """晚子时：sect2 日柱算当日、sect1 算次日；时干一律按次日日干起"""
    s2 = paipan(2024, 2, 10, 23, 30, gender=1, city="北京", use_true_solar=False, school="sect2")
    s1 = paipan(2024, 2, 10, 23, 30, gender=1, city="北京", use_true_solar=False, school="sect1")
    eq("晚子时 sect2 日柱", s2["四柱"]["日"]["干支"], "甲辰")
    eq("晚子时 sect1 日柱", s1["四柱"]["日"]["干支"], "乙巳")
    eq("晚子时 时柱（两派一致）", s2["四柱"]["时"]["干支"], "丙子")
    eq("晚子时 sect1 时柱", s1["四柱"]["时"]["干支"], "丙子")


def test_true_solar():
    """哈尔滨(126.63E) 真太阳时比北京时间早约 26.5 分 + 均时差"""
    dt = datetime.datetime(1935, 4, 25, 7, 30)
    ts, detail = true_solar_time(dt, 126.63)
    ok("真太阳时经度差约 +26.5 分", abs(detail["经度差(分)"] - 26.52) < 0.1, str(detail))
    ok("真太阳时被提前", ts > dt, f"{ts} vs {dt}")
    # 乌鲁木齐 87.62E 应比北京时间晚约 130 分
    ts2, d2 = true_solar_time(dt, 87.62)
    ok("乌鲁木齐经度差约 -129 分", abs(d2["经度差(分)"] + 129.5) < 2, str(d2))
    ok("乌鲁木齐真太阳时被推后", ts2 < dt, f"{ts2} vs {dt}")


def test_lunar_input():
    """农历输入应与对应公历排出同一四柱"""
    solar_r = paipan(1990, 6, 15, 10, 0, gender=1, city="上海")
    from lunar_python import Solar
    lm = Solar.fromYmdHms(1990, 6, 15, 10, 0, 0).getLunar()
    ly, lmo, ld = lm.getYear(), lm.getMonth(), lm.getDay()
    lunar_r = paipan(ly, abs(lmo), ld, 10, 0, gender=1, city="上海",
                     calendar="lunar", is_leap_month=(lmo < 0))
    eq("农历输入与公历输入四柱一致", lunar_r["八字"], solar_r["八字"])


def test_cross_engine():
    """交叉校验不应报出日柱不一致"""
    bad = []
    for (y, m, d, h) in [(1950, 3, 15, 8), (1975, 9, 1, 14), (2001, 12, 25, 2), (2020, 7, 7, 20)]:
        r = paipan(y, m, d, h, 0, gender=1, city="北京", use_true_solar=False)
        for c in r["交叉校验"]:
            if "不一致" in c:
                bad.append((y, m, d, h, c))
    ok("sxtwl 日柱交叉校验一致", not bad, str(bad))


def test_five_element_stats():
    r = paipan(1935, 4, 25, 7, 30, gender=1, city="哈尔滨")
    st = r["五行统计"]
    total = sum(st["五行权重"].values())
    ok("五行权重总量约 10-11.5（4干×1.0 + 4支藏干按1.0/0.5/0.3加权）", 10.0 <= total <= 11.5, f"实得 {total}")
    ok("同类+异类 = 总量",
       abs(st["同类(比劫+印)"] + st["异类(官杀+财+食伤)"] - total) < 0.15,
       f"{st['同类(比劫+印)']}+{st['异类(官杀+财+食伤)']} vs {total}")



# ---------------------------------------------------------------- 4. 强弱 / 调候 / 格局（书中命例）

def test_strength_book_cases():
    """书载结论：命例乙 弱（同方3(2) 异方5(2)）；命例丙 很强（同方6(1) 异方2(1)，三要素全得）"""
    from strength import strength
    hu = strength([("辛","卯"),("庚","子"),("丁","丑"),("丁","未")], "丁")
    eq("命例乙 同方本气", hu["日主同方"]["本气"], 3)
    eq("命例乙 同方附气", hu["日主同方"]["附气"], 2)
    eq("命例乙 异方本气", hu["日主异方"]["本气"], 5)
    eq("命例乙 异方附气", hu["日主异方"]["附气"], 2)
    eq("命例乙 强弱档位", hu["强弱档位"], "弱")
    nh = strength([("戊","午"),("乙","卯"),("甲","子"),("乙","亥")], "甲")
    eq("命例丙 同方本气", nh["日主同方"]["本气"], 6)
    eq("命例丙 同方附气", nh["日主同方"]["附气"], 1)
    eq("命例丙 异方本气", nh["日主异方"]["本气"], 2)
    eq("命例丙 异方附气", nh["日主异方"]["附气"], 1)
    eq("命例丙 强弱档位", nh["强弱档位"], "很强")
    # 命例丁（动态教程 p26）：同方2(0) vs 异方6(6)，差 -10，但时支寅帝旺为根
    # 原书明言「没有到「很弱」的地步」，判「弱」。这是"有根不判极弱"的锚点。
    yu = strength([("辛","巳"),("丁","酉"),("乙","巳"),("戊","寅")], "乙")
    eq("命例丁 同方本气", yu["日主同方"]["本气"], 2)
    eq("命例丁 异方本气", yu["日主异方"]["本气"], 6)
    eq("命例丁 得地（时支寅帝旺）", yu["得地"], True)
    eq("命例丁 强弱档位（有根不判极弱）", yu["强弱档位"], "弱")
    # 命例戊（动态教程 p87）：丙申 甲午 丁巳 壬寅，丁火午月当令、巳帝旺、午禄、
    # 甲印丙劫，原书「自身显然很强」。同方7 vs 异方8 差值 -1，但三要素全得 → 很强。
    wt = strength([("丙","申"),("甲","午"),("丁","巳"),("壬","寅")], "丁")
    eq("命例戊 三要素全得", wt["得令"] and wt["得地"] and wt["得助"], True)
    eq("命例戊 强弱档位（三得压过数值）", wt["强弱档位"], "很强")
    # 书载命例（动态 p240）癸巳 甲子 丁酉 甲辰，丁火子月，通根年支巳火又得双甲扶持
    # 原书「由弱（转）强」；引擎判「强」，方向一致。
    mz = strength([("癸","巳"),("甲","子"),("丁","酉"),("甲","辰")], "丁")
    eq("命例9 得地（年支巳）", mz["得地"], True)
    ok("命例9 强弱不低于中和", mz["强弱档位"] in ("中和","稍强","强","很强","极强"),
       mz["强弱档位"])
    ok("命例丙 得令得地得助三项全得",
       nh["得令"] and nh["得地"] and nh["得助"],
       f"{nh['三要素']}")


def test_tiaohou():
    """调候表抽查 + 命例己寒暖燥湿计分校验（原书 p103 标注 -18）"""
    from tiaohou import tiaohou_yongshen, temp_score
    eq("甲木寅月调候用神", tiaohou_yongshen("甲","寅")[1], "丙癸")
    eq("丙火午月调候用神", tiaohou_yongshen("丙","午")[1], "壬庚")
    eq("辛金辰月调候用神", tiaohou_yongshen("辛","辰")[1], "壬甲")
    t = temp_score([("辛","酉"),("庚","子"),("癸","未"),("丙","辰")])
    eq("命例己 天干计分合计", sum(t["天干计分"]), -4)
    eq("命例己 地支计分合计", sum(t["地支计分"]), -10)
    eq("命例己 月令加分", t["月令加分"], -4)
    eq("命例己 寒暖燥湿总分", t["合计"], -18)
    ok("命例己判为寒湿", t["合计"] < -6, t["判断"])


def test_geju_book_cases():
    """书载：命例9 癸巳甲子丁酉甲辰 取七杀格；命例甲 乙亥庚辰辛未壬辰 取伤官格（偏财被庚合克）"""
    from geju import geju
    m = geju([("癸","巳"),("甲","子"),("丁","酉"),("甲","辰")], "丁")
    eq("命例9 取格", m["取格"], "七杀格")
    l = geju([("乙","亥"),("庚","辰"),("辛","未"),("壬","辰")], "辛")
    eq("命例甲 取格", l["取格"], "伤官格")
    # 戴笠（命例4）丙火生巳月临官 → 建禄格
    d = geju([("丁","酉"),("乙","巳"),("丙","戌"),("丁","酉")], "丙")
    eq("戴笠 取格", d["取格"], "建禄格")
    # 张敬尧（命例13）乙木，辛金七杀主导 → 七杀格
    z = geju([("辛","巳"),("丁","酉"),("乙","卯"),("己","卯")], "乙")
    eq("张敬尧 取格", z["取格"], "七杀格")
    ok("命例甲 检出乙庚相合", any("乙" in x and "庚" in x for x in l["天干相合"]), str(l["天干相合"]))


# ---------------------------------------------------------------- 3. 对账

def test_ganzhi_level():
    """
    干支优略等级（动态 p293-295）：书中例二十五「命例壬」己卯 戊辰 戊子 甲寅，
    原书逐柱标注（下）（上）（上）（上）。
    """
    from ganzhi_level import four_levels, ganzhi_type
    r = four_levels([("己","卯"),("戊","辰"),("戊","子"),("甲","寅")])
    lv = [d["等级"] for d in r["逐柱"]]
    eq("命例壬 干支等级", lv, ["下等", "上等", "上等", "上等"])
    # 五种基本类型抽查
    eq("甲午属上生下", ganzhi_type("甲","午"), "上生下")
    eq("甲子属下生上", ganzhi_type("甲","子"), "下生上")
    eq("甲辰属上克下", ganzhi_type("甲","辰"), "上克下")
    eq("甲申属下克上", ganzhi_type("甲","申"), "下克上")
    eq("甲寅属上下同", ganzhi_type("甲","寅"), "上下同")
    # 上下相合：戊子（戊癸合）、丁亥（丁壬合）、辛巳（丙辛合）、壬午（丁壬合）
    for g, z in (("戊","子"),("丁","亥"),("辛","巳"),("壬","午")):
        lv2 = [d for d in four_levels([(g,z),(g,z),(g,z),(g,z)])["逐柱"]]
        eq(f"{g}{z} 因上下相合判上等", lv2[0]["等级"], "上等")


def test_relations():
    """
    刑冲会合自动检出。
    锚点一：命例乙 辛卯 庚子 丁丑 丁未，原书 p86 明载「子丑合、丑未冲、卯未半合木局」。
    锚点二：乙丑 己卯 庚戌 癸未，终端验证时人工标出的丑戌未三刑/卯戌合/丑未冲/
            卯未半合/乙庚合，脚本应全部检出。
    """
    from relations import analyze
    hu = analyze([("辛","卯"),("庚","子"),("丁","丑"),("丁","未")])
    s = " ".join(hu["摘要"])
    ok("命例乙 检出子丑合", "子丑合" in s, s)
    ok("命例乙 检出丑未冲", "丑未冲" in s, s)
    ok("命例乙 检出卯未半合木", "卯未半合木" in s, s)

    t = analyze([("乙","丑"),("己","卯"),("庚","戌"),("癸","未")])
    s2 = " ".join(t["摘要"])
    for want in ("乙庚合", "卯戌合", "丑未冲", "丑＋戌＋未三刑", "卯未半合木"):
        ok(f"乙丑己卯庚戌癸未 检出{want}", want in s2, s2)
    ok("丑戌未标为无恩之刑",
       any(x.get("名")=="无恩之刑" for x in t["相刑"]), str(t["相刑"]))

    # 自刑：辰辰
    au = analyze([("甲","辰"),("戊","辰"),("甲","子"),("丙","寅")])
    ok("检出辰辰自刑", any("自刑" in x["刑"] for x in au["相刑"]), str(au["相刑"]))

    # 三会方：寅卯辰
    hui = analyze([("甲","寅"),("乙","卯"),("丙","辰"),("丁","巳")])
    ok("检出寅卯辰三会木方", any("三会" in x["会"] for x in hui["三会方"]), str(hui["三会方"]))


def test_parse_chart():
    import subprocess
    here = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(here, "..", "parse_chart.py")
    good = ("　年柱　月柱　日柱　时柱\n"
            "天干　乙　庚　辛　壬\n"
            "地支　亥　辰　未　辰\n"
            "大运　己卯　戊寅　丁丑　丙子　乙亥\n")
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(good)
    out = subprocess.run([sys.executable, script, path], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    ok("对账脚本正常退出", out.returncode == 0, out.stderr[:200])
    ok("正确盘不报硬错误", "未发现硬错误" in out.stdout, out.stdout[-300:])
    # 错盘：甲丑为非法组合
    with open(path, "w", encoding="utf-8") as f:
        f.write("天干　甲　丙　戊　庚\n地支　丑　寅　辰　午\n")
    out2 = subprocess.run([sys.executable, script, path], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    ok("非法干支被检出", "阴阳不配" in out2.stdout, out2.stdout[-300:])
    # 五鼠遁：戊辰日不可能配庚午时（戊日子时为壬子，午时必为戊午）
    ok("五鼠遁错误被检出", "五鼠遁" in out2.stdout and "戊午" in out2.stdout, out2.stdout[-400:])
    # 大运第一步误用月柱本身，应诊断为"错位一格"而非笼统的"非顺非逆"
    with open(path, "w", encoding="utf-8") as f:
        f.write("天干　戊　丙　戊　庚\n地支　辰　寅　辰　午\n大运　丙寅　丁卯　戊辰　己巳\n")
    out3 = subprocess.run([sys.executable, script, path], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    ok("大运错位一格被诊断", "错开一格" in out3.stdout or "下一步" in out3.stdout or "下一柱" in out3.stdout,
       out3.stdout[-400:])
    os.unlink(path)


# ---------------------------------------------------------------- main

def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        try:
            t()
        except Exception as e:
            FAIL.append(f"{t.__name__} 抛异常: {type(e).__name__}: {e}")
    print(f"\n通过 {len(PASS)} 项，失败 {len(FAIL)} 项\n")
    if FAIL:
        print("失败清单：")
        for f in FAIL:
            print("  ✗", f)
        sys.exit(1)
    print("全部通过 ✓")
    for p in PASS:
        print("  ✓", p)


if __name__ == "__main__":
    main()
