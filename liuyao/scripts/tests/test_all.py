# -*- coding: utf-8 -*-
"""全量回归测试：任何改动后执行 `python tests/test_all.py`。

覆盖：静态数据一致性、六十四卦装卦、纳甲/六亲/世应基准、
      六爻三种输入格式。
"""
import sys
import os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))          # scripts/，含 paipan.py
sys.path.insert(0, os.path.join(HERE, "..", "lib"))   # scripts/lib/，引擎模块

import gua_data          # noqa: E402
import liuyao            # noqa: E402
from lunar_python import Solar  # noqa: E402

PASS, FAIL = [], []


def check(name, fn):
    try:
        fn()
        PASS.append(name)
        print(f"  ✓ {name}")
    except Exception as e:
        FAIL.append((name, e))
        print(f"  ✗ {name}: {e!r}")


# ---------------------------------------------------------------- 静态数据
def t_gua_static():
    gua_data.selfcheck()
    assert len(gua_data.NAJIA) == 8
    for g, v in gua_data.NAJIA.items():
        assert len(v[2]) == 3 and len(v[3]) == 3, g


# ---------------------------------------------------------------- 六爻
GZ_FIX = {"year": "乙巳", "month": "壬午", "day": "乙卯", "time": "辛巳"}


def t_najia_benchmarks():
    """纳甲必须按内外卦取，四卦基准。"""
    cases = [
        ("111111", ["甲子", "甲寅", "甲辰", "壬午", "壬申", "壬戌"], "乾为天"),
        ("000000", ["乙未", "乙巳", "乙卯", "癸丑", "癸亥", "癸酉"], "坤为地"),
        ("101010", ["己卯", "己丑", "己亥", "戊申", "戊戌", "戊子"], "水火既济"),
        ("011111", ["辛丑", "辛亥", "辛酉", "壬午", "壬申", "壬戌"], "天风姤"),
        ("111100", ["甲子", "甲寅", "甲辰", "庚午", "庚申", "庚戌"], "雷天大壮"),
        ("100010", ["庚子", "庚寅", "庚辰", "戊申", "戊戌", "戊子"], "水雷屯"),
    ]
    for bin6, expect, name in cases:
        lines = [{"num": 7 if c == "1" else 8, "yang": c == "1", "dong": False, "name": "静"}
                 for c in bin6]
        ch = liuyao.build_chart(lines, GZ_FIX, "子丑")
        got = [y["najia"] for y in ch["爻"]]
        assert ch["本卦"]["name"] == name, f"{bin6} 卦名 {ch['本卦']['name']} != {name}"
        assert got == expect, f"{name} 纳甲 {got} != {expect}"


def t_all_64():
    for bin6 in gua_data.GUA_NAME_BY_BIN:
        lines = [{"num": 7 if c == "1" else 8, "yang": c == "1",
                  "dong": False, "name": "静"} for c in bin6]
        ch = liuyao.build_chart(lines, GZ_FIX, "子丑")
        assert ch["本卦"]["bin"] == bin6
        assert len(ch["爻"]) == 6
        assert all(y["liuqin"] != "?" for y in ch["爻"])
        assert 1 <= ch["本卦"]["shi_pos"] <= 6
        assert 1 <= ch["本卦"]["ying_pos"] <= 6


def t_shi_ying():
    """八宫卦序对应的世应位置。"""
    expect = {0: (6, 3), 1: (1, 4), 2: (2, 5), 3: (3, 6),
              4: (4, 1), 5: (5, 2), 6: (4, 1), 7: (3, 6)}
    for gong, lst in gua_data.GONG_GUA.items():
        for i, (bin6, name) in enumerate(lst):
            lines = [{"num": 7 if c == "1" else 8, "yang": c == "1",
                      "dong": False, "name": "静"} for c in bin6]
            ch = liuyao.build_chart(lines, GZ_FIX, "子丑")
            assert (ch["本卦"]["shi_pos"], ch["本卦"]["ying_pos"]) == expect[i], name


def t_fushen():
    """水火既济财爻不上卦，应伏于三爻（戊午火）。"""
    lines = [{"num": 7 if c == "1" else 8, "yang": c == "1", "dong": False, "name": "静"}
             for c in "101010"]
    ch = liuyao.build_chart(lines, GZ_FIX, "子丑")
    assert ch["伏神"], "应检测到伏神"
    fs = ch["伏神"][0]
    assert fs["liuqin"] == "妻财", fs
    assert fs["najia"] == "戊午", fs
    assert fs["pos"] == 3, fs


def t_dongbian():
    """全动：乾变坤；异卦动变纳甲按变卦内外卦取。"""
    ch = liuyao.build_chart([{"num": 9, "yang": True, "dong": True, "name": "老阳"}
                             for _ in range(6)], GZ_FIX, "子丑")
    assert ch["本卦"]["name"] == "乾为天"
    assert ch["变卦"]["name"] == "坤为地"
    assert ch["动爻"] == [1, 2, 3, 4, 5, 6]
    kun_in, kun_out = gua_data.NAJIA["坤"][2], gua_data.NAJIA["坤"][3]
    for y in ch["爻"]:
        want_zhi = kun_in[y["pos"] - 1] if y["pos"] <= 3 else kun_out[y["pos"] - 4]
        assert y["bian"]["zhi"] == want_zhi, f"{y['pos']}爻变出{y['bian']['zhi']}应为{want_zhi}"


def t_input_formats():
    a = liuyao.parse_inputs("7 8 9 6 7 8")
    b = liuyao.parse_inputs("1 2 3 0 1 2")
    c = liuyao.parse_inputs("阳,阴,阳动,阴,阳,阴")
    assert [x["num"] for x in a] == [7, 8, 9, 6, 7, 8]
    assert [x["num"] for x in b] == [7, 8, 9, 6, 7, 8]
    assert [x["num"] for x in c] == [7, 8, 9, 8, 7, 8]
    assert [x["dong"] for x in a] == [False, False, True, True, False, False]


# ---------------------------------------------------------------- 墓库/进退/飞伏/应期
def t_ru_mu():
    """午火之墓在戌：日辰戌则日墓；爻自身临墓库不算入墓。"""
    r = liuyao.check_ru_mu("午", month_zhi="戌", day_zhi="戌")
    assert r["is_ru_mu"] and r["mu_zhi"] == "戌", r
    assert set(r["mu_by"]) == {"月墓", "日墓"}, r["mu_by"]
    # 戌爻自身：土墓在辰，戌日不算戌爻入墓
    r2 = liuyao.check_ru_mu("戌", month_zhi="戌", day_zhi="戌")
    assert not r2["is_ru_mu"], r2
    # 辰日 → 戌爻（土）入辰墓（水土同宫）
    r3 = liuyao.check_ru_mu("戌", day_zhi="辰")
    assert r3["is_ru_mu"] and r3["mu_zhi"] == "辰", r3
    # 五行墓库全表
    assert liuyao.mu_of("寅") == "未" and liuyao.mu_of("午") == "戌"
    assert liuyao.mu_of("申") == "丑" and liuyao.mu_of("子") == "辰"


def t_hua_mu():
    """亥水化辰 → 化墓（水墓在辰）；申金化酉 → 非墓。"""
    assert liuyao.check_hua_mu("亥", "辰") is True
    assert liuyao.check_hua_mu("午", "戌") is True
    assert liuyao.check_hua_mu("申", "酉") is False


def t_jin_tui():
    """化进/化退表。"""
    cases = [("寅", "卯", "进"), ("巳", "午", "进"), ("申", "酉", "进"),
             ("亥", "子", "进"), ("丑", "辰", "进"), ("辰", "未", "进"),
             ("卯", "寅", "退"), ("午", "巳", "退"), ("酉", "申", "退"),
             ("子", "亥", "退"), ("戌", "未", "退"), ("辰", "丑", "退"),
             ("申", "戌", "—")]
    for a, b, want in cases:
        got = liuyao.check_jin_tui(a, b)
        assert got == want, f"{a}化{b} 应为{want}，实得{got}"


def t_feifu():
    """飞伏生克五类。"""
    cases = [("亥", "午", "飞来克伏"),   # 飞水克伏火
             ("辰", "申", "飞来生伏"),   # 飞土生伏金
             ("申", "辰", "伏去生飞"),   # 伏土生飞金
             ("申", "午", "伏去克飞"),   # 伏火克飞金
             ("子", "子", "比和")]
    for fei, fu, want in cases:
        got = liuyao.check_feifu(fei, fu)["relation"]
        assert got == want, f"飞{fei}伏{fu} 应为{want}，实得{got}"


def t_gua_body_table():
    """六冲卦 10 个、六合卦 8 个，须与经典卦表完全一致。"""
    expect_chong = {"乾为天", "坤为地", "震为雷", "巽为风", "坎为水",
                    "离为火", "艮为山", "兑为泽", "天雷无妄", "雷天大壮"}
    expect_he = {"地天泰", "天地否", "雷地豫", "地雷复",
                 "泽水困", "水泽节", "山火贲", "火山旅"}
    got_chong, got_he = set(), set()
    for bin6, name in gua_data.GUA_NAME_BY_BIN.items():
        b = gua_data.gua_body(bin6)["body"]
        if b == "六冲":
            got_chong.add(name)
        if b == "六合":
            got_he.add(name)
    assert got_chong == expect_chong, got_chong ^ expect_chong
    assert got_he == expect_he, got_he ^ expect_he


def t_chong_judge():
    """日冲性质：临月建者冲不散，休囚者才成日破。"""
    # 午火，午月（临月建），动 → 冲不散
    assert liuyao.chong_judge("午", "午", "子", True) == "冲不散"
    # 午火，午月，静 → 暗动
    assert liuyao.chong_judge("午", "午", "子", False) == "暗动"
    # 午火，子月（月破），又被日冲 → 重破
    assert liuyao.chong_judge("午", "子", "子", False) == "重破"
    # 酉金，午月（火克金，休囚），静 → 日破
    assert liuyao.chong_judge("酉", "午", "卯", False) == "日破"
    # 动爻而月不助 → 冲则动
    assert liuyao.chong_judge("酉", "午", "卯", True) == "冲则动"


def t_dazhuang_bian_xun():
    """《增删卜易》经典例：午月丙子日占开典铺，雷天大壮之巽为风。

    四个判点：六冲变六冲、世爻午火日冲「冲不散」而非「日破」、
    全动化绊为真绊、初爻子与四爻午成反吟。
    """
    lines = liuyao.parse_inputs("9 7 7 9 6 6")
    GZ = {"year": "乙巳", "month": "壬午", "day": "丙子", "time": "癸巳"}
    ch = liuyao.build_chart(lines, GZ, "申酉")

    assert ch["本卦"]["name"] == "雷天大壮", ch["本卦"]["name"]
    assert ch["本卦"]["body"] == "六冲"
    assert ch["变卦"]["name"] == "巽为风", ch["变卦"]["name"]
    assert ch["变卦"]["body"] == "六冲"
    assert "六冲变六冲" in ch["卦体"]["组合"]
    assert ch["动爻"] == [1, 4, 5, 6], ch["动爻"]

    # 纳甲：下乾上震
    assert [y["najia"] for y in ch["爻"]] == [
        "甲子", "甲寅", "甲辰", "庚午", "庚申", "庚戌"]

    # 世爻父母午火 —— 旺相之日冲不成破
    shi = [y for y in ch["爻"] if y["shi"]][0]
    assert shi["liuqin"] == "父母" and shi["zhi"] == "午"
    assert shi["is_day_chong"] is True
    assert shi["day_chong_judge"] == "冲不散", shi["day_chong_judge"]
    assert shi["is_day_po"] is False, "临月建之爻不得判为日破"

    # 全动化绊 → 真绊
    assert ch["化绊"]["化绊数"] == 4, ch["化绊"]
    assert "真绊" in ch["化绊"]["定性"], ch["化绊"]["定性"]

    # 反吟：初爻子与四爻午
    assert ch["反吟"]["has"] is True
    assert any("甲子" in p for p in ch["反吟"]["pairs"]), ch["反吟"]

    # 初爻财爻月破、化丑回头克
    cai = [y for y in ch["爻"] if y["liuqin"] == "妻财"][0]
    assert cai["is_month_po"] is True
    assert cai["bian"]["ke_dong"] is True
    assert cai["bian"]["hua_ban"] is True


def t_ru_mu_self():
    """爻自身即墓库地支者，不作入墓论。"""
    r = liuyao.check_ru_mu("辰", month_zhi="辰", day_zhi="辰")
    assert not r["is_ru_mu"], r
    assert "自身即" in r.get("mu_note", ""), r
    # 戌爻属土，土墓辰，遇辰月才入墓
    r2 = liuyao.check_ru_mu("戌", month_zhi="辰")
    assert r2["is_ru_mu"] and r2["mu_zhi"] == "辰", r2
    # 子水墓辰
    r3 = liuyao.check_ru_mu("子", day_zhi="辰")
    assert r3["is_ru_mu"], r3


def t_chong_kong():
    """空爻逢日冲为「冲空」，不是日破。"""
    assert liuyao.chong_judge("寅", "辰", "申", False, is_kong=True) == "冲空"
    assert liuyao.chong_judge("寅", "辰", "申", False) == "日破"


def t_fubing_case():
    """乾之小畜，辰月戊申日，占父母近病。

    四个判点：父子多现须舍衰取旺（持世戌土月破不可用）、辰爻自身不作入墓、
    寅木空而被冲为「冲空」、应期取丑日解午未之绊、子日冲午伤原神列为忌日。
    """
    import paipan
    import yingqi
    from datetime import datetime as _dt

    lines = liuyao.parse_inputs("7 7 7 9 7 7")
    GZ = {"year": "乙巳", "month": "庚辰", "day": "戊申", "time": "丁巳"}
    ch = liuyao.build_chart(lines, GZ, "寅卯")

    assert ch["本卦"]["name"] == "乾为天", ch["本卦"]["name"]
    assert ch["变卦"]["name"] == "风天小畜", ch["变卦"]["name"]
    assert ch["本卦"]["body"] == "六冲"

    chen = [y for y in ch["爻"] if y["zhi"] == "辰"][0]
    assert chen["is_ru_mu"] is False, chen
    xu = [y for y in ch["爻"] if y["zhi"] == "戌"][0]
    assert xu["is_ru_mu"] is True and xu["is_month_po"] is True

    yin = [y for y in ch["爻"] if y["zhi"] == "寅"][0]
    assert yin["is_kong"] is True
    assert yin["day_chong_judge"] == "冲空", yin["day_chong_judge"]
    assert yin["is_day_po"] is False

    # 取用神已移交 judge（ch11 六步次序）。此卦父母两现（世爻戌土月破、三爻辰土临月建），
    # 两者都属「见异」；按原文，多爻同时见异时以事态现状对证，没有硬性先后。
    import judge
    yh = judge.choose_yongshen(ch, "父母", "占父母近病")
    assert yh["选定"] is not None, yh
    assert yh["选定"]["六亲"] == "父母", yh["选定"]
    assert yh["次第"], yh["次第"]

    r = yingqi.calc_yingqi(ch, _dt(2025, 4, 9, 10, 0), "父母", prefer_pos="三爻")
    assert r["用神位置"].startswith("本卦·三爻"), r["用神位置"]
    txt = " ".join(" ".join(h["依据"]) for h in r["候选"])
    assert "冲开绊神" in txt, txt
    assert "绊神未" in txt, txt
    assert r["忌日"], "应列出冲伤原神的忌日"
    assert any("午" in j["说明"] for j in r["忌日"]), r["忌日"]


def t_yingqi():
    """既济财伏，应期应含冲墓、冲飞神、值日三类。"""
    import yingqi
    from datetime import datetime as _dt
    lines = [{"num": 7 if c == "1" else 8, "yang": c == "1",
              "dong": False, "name": "静"} for c in "101010"]
    GZ = {"year": "乙巳", "month": "丙戌", "day": "甲戌", "time": "己巳"}
    ch = liuyao.build_chart(lines, GZ, "申酉")
    r = yingqi.calc_yingqi(ch, _dt(2025, 11, 1, 10, 30), "妻财")
    assert r["用神位置"].startswith("伏神"), r["用神位置"]
    text = "".join(" ".join(h["依据"]) for h in r["候选"])
    assert "冲墓" in text, text
    assert "冲开飞神" in text, text
    assert r["月建节点"], "应有换月节点"
    for h in r["候选"]:
        assert h["日期"] and h["日干支"], h


# ---------------------------------------------------------------- 主程序
def main():
    print("=" * 56)
    print("命理排盘引擎 · 全量回归")
    print("=" * 56)
    print("\n[静态数据]")
    check("六十四卦/八宫/卦序一致性", t_gua_static)
    print("\n[六爻]")
    check("纳甲基准（按内外卦取）", t_najia_benchmarks)
    check("六十四卦全覆盖装卦", t_all_64)
    check("八宫世应位置", t_shi_ying)
    check("伏神检出（既济财伏三爻）", t_fushen)
    check("动爻与变卦纳甲", t_dongbian)
    check("三种输入格式等价", t_input_formats)
    print("\n[墓库/进退/飞伏/应期]")
    check("入墓判定（含土爻不临墓）", t_ru_mu)
    check("化墓判定", t_hua_mu)
    check("化进化退表", t_jin_tui)
    check("飞伏五类生克", t_feifu)
    check("应期候选生成", t_yingqi)
    print("\n[卦体与经典卦例回归]")
    check("六冲10卦/六合8卦", t_gua_body_table)
    check("日冲性质（冲不散/暗动/日破/重破）", t_chong_judge)
    check("大壮之巽（开典铺卦例）", t_dazhuang_bian_xun)
    check("辰爻自身不作入墓", t_ru_mu_self)
    check("空爻逢冲为冲空", t_chong_kong)
    check("乾之小畜（占父病卦例）", t_fubing_case)

    print("\n" + "=" * 56)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        for n, e in FAIL:
            print(f"  ✗ {n}: {e!r}")
        sys.exit(1)
    print("全部通过")


if __name__ == "__main__":
    main()
