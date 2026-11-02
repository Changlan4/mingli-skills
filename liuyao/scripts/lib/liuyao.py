# -*- coding: utf-8 -*-
"""六爻纳甲装卦引擎：由摇卦结果生成完整卦盘（确定性，不依赖任何 AI）。

产出的是"事实"，解读留给上层 agent。同一输入恒得同一输出。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gua_data import (  # noqa: E402
    GUA_NAME_BY_BIN, GUA_INDEX, GONG_GUA, NAJIA, SHI_YING, SHI_YING_NAME,
    GONG_WUXING, ZHI_WUXING, GAN_WUXING, SHENG, KE,
    ZHI_LIUHE, ZHI_CHONG, ZHI_SANHE, liuqin, liushen_of, gua_info,
    WX_MU, MU_WX, JIN_TUI, WX_ZHI,
)

YAO_NAME = {1: "初爻", 2: "二爻", 3: "三爻", 4: "四爻", 5: "五爻", 6: "上爻"}
YAO_POS_DIZHI = {1: "初", 2: "二", 3: "三", 4: "四", 5: "五", 6: "上"}


# ------------------------------------------------------------------ 摇卦 → 爻
def coins_to_yao(coins_back: int) -> dict:
    """三枚铜钱抛出，coins_back 为背面（无字面）枚数。

    传统记法：一背字多=少阳，二背=少阴，三背=老阳(动)，三字=老阴(动)。
    """
    table = {
        0: (6, 0, "老阴", "阴爻动"),
        1: (7, 1, "少阳", "阳爻静"),
        2: (8, 0, "少阴", "阴爻静"),
        3: (9, 1, "老阳", "阳爻动"),
    }
    num, is_yang, name, desc = table[coins_back]
    return {"num": num, "yang": bool(is_yang), "name": name, "dong": num in (6, 9)}


def parse_inputs(spec: str) -> list:
    """解析六爻输入。

    支持三种写法：
      1) 数字串：6 个 6/7/8/9，空格或逗号分隔，如 "7 8 9 6 7 8"
      2) 背数串：6 个 0-3，表示每次三枚铜钱的背面枚数，如 "1 2 3 0 1 2"
      3) 显式串：用 "阳/阴" + "动/静"，如 "阳,阴,阳动,阴,阳,阴"
    """
    s = spec.strip()
    # 模式 3：显式
    if any(k in s for k in ("阳", "阴")):
        parts = [p.strip() for p in s.replace("，", ",").split(",") if p.strip()]
        out = []
        for p in parts:
            yang = p.startswith("阳")
            dong = "动" in p
            num = (9 if dong else 7) if yang else (6 if dong else 8)
            out.append({"num": num, "yang": yang, "dong": dong,
                        "name": {9: "老阳", 7: "少阳", 6: "老阴", 8: "少阴"}[num]})
        return out
    nums = [int(x) for x in s.replace("，", " ").replace(",", " ").split()]
    if len(nums) != 6:
        raise ValueError(f"需要 6 个爻，实得 {len(nums)} 个：{nums}")
    if all(n in (6, 7, 8, 9) for n in nums):
        out = []
        for n in nums:
            yang = n in (7, 9)
            out.append({"num": n, "yang": yang, "dong": n in (6, 9),
                        "name": {9: "老阳", 7: "少阳", 6: "老阴", 8: "少阴"}[n]})
        return out
    if all(0 <= n <= 3 for n in nums):
        return [coins_to_yao(n) for n in nums]
    raise ValueError(f"无法识别的六爻输入：{nums}（应为 6/7/8/9 或 0-3 背数）")


# ------------------------------------------------------------------ 干支关系
def zhi_vs(base: str, other: str) -> dict:
    """判定 other 相对 base 的状态。

    用于「爻 vs 月建/日辰」时：base 为月建或日辰，other 为该爻地支，
    返回的标签是以「该爻」为主语的被动状态，如「受生」「受克」「泄气」。
    """
    b_wx, o_wx = ZHI_WUXING[base], ZHI_WUXING[other]
    tags = []
    if b_wx == o_wx:
        tags.append("同气")
    if ZHI_CHONG[base] == other:
        tags.append("相冲")
    if ZHI_LIUHE[base] == other:
        tags.append("相合")
    if SHENG[b_wx] == o_wx:
        tags.append("受生")      # 月建/日辰 生 该爻
    if KE[b_wx] == o_wx:
        tags.append("受克")      # 月建/日辰 克 该爻
    if SHENG[o_wx] == b_wx:
        tags.append("泄气")      # 该爻 生 月建/日辰
    if KE[o_wx] == b_wx:
        tags.append("克出")      # 该爻 克 月建/日辰
    return {"tags": tags or ["无特殊关系"]}


# ------------------------------------------------------------------ 墓库 / 进退 / 飞伏
def mu_of(zhi: str) -> str:
    """该地支所属五行的墓库地支。"""
    return WX_MU[ZHI_WUXING[zhi]]


def check_ru_mu(zhi: str, month_zhi: str = "", day_zhi: str = "") -> dict:
    """判该爻是否入墓（日墓 / 月墓）。

    入墓条件：该爻五行之墓库，恰为日辰或月建。
    **爻自身即墓库地支者不作入墓论**——它本身就是那个墓库，不是被墓收。
    例：辰爻属土、土墓在辰，辰月辰日不判辰爻入墓；戌爻属土，遇辰月辰日才判入墓。
    """
    wx = ZHI_WUXING[zhi]
    mu = WX_MU[wx]
    if zhi == mu:
        return {
            "is_ru_mu": False,
            "mu_zhi": mu,
            "mu_of_wuxing": wx,
            "mu_note": f"{zhi}爻自身即{wx}之墓库，不作入墓论",
        }
    by = []
    if month_zhi and month_zhi == mu:
        by.append("月墓")
    if day_zhi and day_zhi == mu:
        by.append("日墓")
    out = {
        "is_ru_mu": bool(by),
        "mu_zhi": mu,
        "mu_of_wuxing": wx,
    }
    if by:
        out["mu_by"] = by
        # 出墓：冲墓（墓库被冲）或该爻逢值
        out["chu_mu"] = f"冲墓（{ZHI_CHONG[mu]}日/月）或值{mu}被冲开"
    return out


def check_hua_mu(dong_zhi: str, bian_zhi: str) -> bool:
    """动爻是否化入墓（化出之支为该动爻五行的墓库）。"""
    return WX_MU[ZHI_WUXING[dong_zhi]] == bian_zhi


def check_jin_tui(dong_zhi: str, bian_zhi: str) -> str:
    """动爻化进化退。返回 '进' / '退' / '平'。"""
    got = JIN_TUI.get((dong_zhi, bian_zhi))
    if got:
        return got
    if ZHI_WUXING[dong_zhi] == ZHI_WUXING[bian_zhi]:
        return "平"    # 同五行但非顺逆（如丑化未）
    return "—"        # 跨五行，不论进退


def check_feifu(fei_zhi: str, fu_zhi: str) -> dict:
    """飞神与伏神的关系。"""
    f = ZHI_WUXING[fei_zhi]
    v = ZHI_WUXING[fu_zhi]
    if f == v:
        rel = "比和"
        tone = "伏神与飞神同气，不受压制"
    elif SHENG[f] == v:
        rel = "飞来生伏"
        tone = "飞神生伏神，伏而易出，得助"
    elif KE[f] == v:
        rel = "飞来克伏"
        tone = "飞神克伏神，伏而受制，难出"
    elif SHENG[v] == f:
        rel = "伏去生飞"
        tone = "伏神生飞神，泄气，虽有而无功"
    elif KE[v] == f:
        rel = "伏去克飞"
        tone = "伏神克飞神，能制飞神，可出"
    else:
        rel, tone = "?", ""
    return {"relation": rel, "tone": tone,
            "chuxian": f"冲开飞神（{ZHI_CHONG[fei_zhi]}日）或伏神值日（{fu_zhi}日）"}


def chong_judge(zhi: str, month_zhi: str, day_zhi: str, is_dong: bool,
                is_kong: bool = False) -> str:
    """该爻被日辰冲时，判其性质。

    传统口径：
      旬空又逢日冲       → 「冲空」：空逢冲而实，反成有用之动，**不是日破**
      临月建或得月建生扶 → 旺，动爻「冲不散」、静爻「暗动」
      本身已月破         → 「重破」（月破再逢日冲）
      动爻而月建不助     → 「冲则动」
      其余休囚静爻       → 「日破」
    """
    if is_kong:
        return "冲空"
    if not month_zhi:
        return ""
    mwx, zwx = ZHI_WUXING[month_zhi], ZHI_WUXING[zhi]
    lin_month = (mwx == zwx)
    month_sheng = (SHENG[mwx] == zwx)
    yue_po = (ZHI_CHONG[month_zhi] == zhi)
    if lin_month or month_sheng:
        return "冲不散" if is_dong else "暗动"
    if yue_po:
        return "重破"
    if is_dong:
        return "冲则动"
    return "日破"


def check_hua_ban(dong_zhi: str, bian_zhi: str) -> bool:
    """动爻化出之支与自身六合 → 化绊（动而受合，主牵绊）。"""
    return ZHI_LIUHE[dong_zhi] == bian_zhi


def check_fanyin(yao_list: list) -> dict:
    """反吟：卦中两爻相冲而同时发动，主反复、来回折腾。"""
    dong = [y for y in yao_list if y["dong"]]
    pairs = []
    for i in range(len(dong)):
        for j in range(i + 1, len(dong)):
            if ZHI_CHONG[dong[i]["zhi"]] == dong[j]["zhi"]:
                pairs.append(f"{dong[i]['pos_name']}{dong[i]['najia']}"
                             f"—{dong[j]['pos_name']}{dong[j]['najia']}")
    return {"has": bool(pairs), "pairs": pairs}


# ------------------------------------------------------------------ 装卦主逻辑
def build_chart(lines: list, ganzhi: dict, xunkong: str = "") -> dict:
    """lines: 6 个 dict（初→上），每项含 num/yang/dong。
    ganzhi: {"year":..,"month":..,"day":..,"time":..} 四柱干支。
    """
    # 本卦 / 变卦二进制
    ben_bits = "".join("1" if ln["yang"] else "0" for ln in lines)
    dong_pos = [i + 1 for i, ln in enumerate(lines) if ln["dong"]]
    bian_bits = "".join(
        ("0" if ln["yang"] else "1") if ln["dong"] else ("1" if ln["yang"] else "0")
        for ln in lines
    ) if dong_pos else ben_bits

    ben = gua_info(ben_bits)
    bian = gua_info(bian_bits) if dong_pos else None

    gong = ben["gong"]
    gwx = ben["gong_wuxing"]
    # 纳甲按「内外卦各自的八卦」取，不是按卦宫取。
    # NAJIA[X] = (内卦天干, 外卦天干, 内卦三爻地支, 外卦三爻地支)
    lower_najia = NAJIA[ben["lower"]]
    upper_najia = NAJIA[ben["upper"]]
    day_gan = ganzhi.get("day", "甲")[0]
    shen6 = liushen_of(day_gan)

    month_zhi = ganzhi.get("month", "")[1] if len(ganzhi.get("month", "")) >= 2 else ""
    day_zhi = ganzhi.get("day", "")[1] if len(ganzhi.get("day", "")) >= 2 else ""

    # 变卦纳甲同样按变卦的内外卦取；变爻六亲仍按本卦宫论
    if bian:
        b_lower_najia = NAJIA[bian["lower"]]
        b_upper_najia = NAJIA[bian["upper"]]

    yao_list = []
    for i in range(6):
        pos = i + 1
        ln = lines[i]
        if pos <= 3:
            gan, zhi = lower_najia[0], lower_najia[2][pos - 1]
        else:
            gan, zhi = upper_najia[1], upper_najia[3][pos - 4]
        wx = ZHI_WUXING[zhi]
        lq = liuqin(gong, zhi)

        item = {
            "pos": pos,
            "pos_name": YAO_NAME[pos],
            "is_yang": ln["yang"],
            "yao_symbol": "━━━" if ln["yang"] else "━ ━",
            "yin_yang": "阳" if ln["yang"] else "阴",
            "najia": gan + zhi,
            "gan": gan,
            "zhi": zhi,
            "wuxing": wx,
            "liuqin": lq,
            "liushen": shen6[i],
            "shi": pos == ben["shi"],
            "ying": pos == ben["ying"],
            "dong": ln["dong"],
            "yao_type": ln.get("name", ""),
        }

        # 旬空先定：日冲的性质要看它是不是空爻（空逢冲即实）
        is_kong = bool(xunkong and zhi in xunkong)
        if is_kong:
            item["is_kong"] = True
            item["xunkong"] = xunkong

        # 与月建、日辰的关系
        if month_zhi:
            item["month_rel"] = zhi_vs(month_zhi, zhi)["tags"]
            item["is_month_po"] = (ZHI_CHONG[month_zhi] == zhi)
        if day_zhi:
            item["day_rel"] = zhi_vs(day_zhi, zhi)["tags"]
            is_chong = (ZHI_CHONG[day_zhi] == zhi)
            item["is_day_chong"] = is_chong
            if is_chong:
                judge = chong_judge(zhi, month_zhi, day_zhi, ln["dong"], is_kong)
                item["day_chong_judge"] = judge
                # 只有休囚者逢冲才成「日破」；空者冲实、旺者冲不散、静者暗动
                item["is_day_po"] = judge in ("日破", "重破")
            else:
                item["is_day_po"] = False

        # 入墓（日墓 / 月墓）
        mu = check_ru_mu(zhi, month_zhi, day_zhi)
        item.update(mu)

        # 变爻
        if ln["dong"] and bian:
            if pos <= 3:
                bgan, bzhi = b_lower_najia[0], b_lower_najia[2][pos - 1]
            else:
                bgan, bzhi = b_upper_najia[1], b_upper_najia[3][pos - 4]
            bwx = ZHI_WUXING[bzhi]
            item["bian"] = {
                "najia": bgan + bzhi,
                "zhi": bzhi,
                "wuxing": bwx,
                "liuqin": liuqin(gong, bzhi),
                # 变爻对动爻的作用
                "rel_to_dong": zhi_vs(zhi, bzhi)["tags"],
                "sheng_dong": SHENG[bwx] == wx,   # 变生本（回头生）
                "ke_dong": KE[bwx] == wx,         # 变克本（回头克）
                "dong_sheng_bian": SHENG[wx] == bwx,
                "dong_ke_bian": KE[wx] == bwx,
                # 化进化退、化墓、化绊
                "jin_tui": check_jin_tui(zhi, bzhi),
                "hua_mu": check_hua_mu(zhi, bzhi),
                "hua_ban": check_hua_ban(zhi, bzhi),
            }
        yao_list.append(item)

    # 伏神：本卦所缺六亲，取本宫首卦同位之爻
    present = {y["liuqin"] for y in yao_list}
    all_lq = ["父母", "兄弟", "子孙", "妻财", "官鬼"]
    fushen = []
    if missing := [l for l in all_lq if l not in present]:
        ben_gong_najia = NAJIA[gong]
        # 本宫首卦即本宫卦，其六爻纳甲
        for m in missing:
            for pos in range(1, 7):
                outer = pos >= 4
                fzhi = (ben_gong_najia[3][pos - 4] if outer
                        else ben_gong_najia[2][pos - 1])
                if liuqin(gong, fzhi) == m:
                    fgan = ben_gong_najia[1] if outer else ben_gong_najia[0]
                    # 飞神＝本卦该位的爻
                    fei = yao_list[pos - 1]
                    ff = check_feifu(fei["zhi"], fzhi)
                    mu = check_ru_mu(fzhi, month_zhi, day_zhi)
                    fushen.append({
                        "pos": pos,
                        "pos_name": YAO_NAME[pos],
                        "liuqin": m,
                        "najia": fgan + fzhi,
                        "zhi": fzhi,
                        "wuxing": ZHI_WUXING[fzhi],
                        "note": f"本卦不现{m}，伏于{YAO_NAME[pos]}之下",
                        "fei_shen": {
                            "najia": fei["najia"],
                            "zhi": fei["zhi"],
                            "wuxing": fei["wuxing"],
                            "liuqin": fei["liuqin"],
                        },
                        "feifu": ff,
                        "is_ru_mu": mu["is_ru_mu"],
                        "mu_zhi": mu["mu_zhi"],
                        "mu_by": mu.get("mu_by", []),
                        "is_kong": bool(xunkong and fzhi in xunkong),
                    })
                    break

    # ---------------- 卦体（六冲 / 六合）
    ben_body = ben["body"]
    bian_body = bian["body"] if bian else None
    if bian_body:
        if ben_body == "六冲" and bian_body == "六冲":
            combo = "六冲变六冲：冲中再冲，主散、不持久、起得快塌得也快"
        elif ben_body == "六合" and bian_body == "六合":
            combo = "六合变六合：合中再合，主缠绵难解"
        elif ben_body == "六冲" and bian_body == "六合":
            combo = "六冲变六合：先散后合"
        elif ben_body == "六合" and bian_body == "六冲":
            combo = "六合变六冲：先合后散，主先成后败"
        else:
            combo = f"本卦{ben_body}、变卦{bian_body}"
    else:
        combo = f"本卦{ben_body}（静卦）" if ben_body != "常卦" else "常卦（静）"

    # ---------------- 化绊
    ban_dong = [y for y in yao_list
                if y["dong"] and y.get("bian") and y["bian"].get("hua_ban")]
    ban_info = {
        "化绊爻": [f"{y['pos_name']}{y['najia']}" for y in ban_dong],
        "化绊数": len(ban_dong),
        "动爻数": len(dong_pos),
    }
    if len(dong_pos) >= 3 and len(ban_dong) == len(dong_pos):
        ban_info["定性"] = ("全动化绊：符合真绊定式。动爻如被绑死，有动等于没动，"
                        "事多不了了之或不见善果，且了无应期")
    elif len(ban_dong) >= 2:
        ban_info["定性"] = "多爻化绊，须核其中是否有得日辰或他爻冲开者（冲开则成假绊）"
    elif ban_dong:
        ban_info["定性"] = "一爻化绊，多属假绊，逢冲即解"
    else:
        ban_info["定性"] = "无化绊"

    # ---------------- 反吟
    fanyin = check_fanyin(yao_list)

    return {
        "本卦": {
            "name": ben["name"],
            "full_name": ben["name"],
            "bin": ben["bin"],
            "gong": ben["gong"],
            "gong_wuxing": gwx,
            "seq_name": ben["seq_name"],
            "shi_pos": ben["shi"],
            "ying_pos": ben["ying"],
            "upper": ben["upper"],
            "lower": ben["lower"],
            "body": ben_body,
            "order_wenwang": ben["order_wenwang"],
        },
        "变卦": {
            "name": bian["name"],
            "gong": bian["gong"],
            "gong_wuxing": bian["gong_wuxing"],
            "upper": bian["upper"],
            "lower": bian["lower"],
            "body": bian_body,
            "order_wenwang": bian["order_wenwang"],
        } if bian else None,
        "卦体": {
            "本卦": ben_body,
            "变卦": bian_body,
            "组合": combo,
        },
        "化绊": ban_info,
        "反吟": fanyin,
        "动爻": dong_pos,
        "月建": month_zhi,
        "日辰": day_zhi,
        "旬空": xunkong,
        "爻": yao_list,
        "伏神": fushen,
        "六亲齐全": not fushen,
    }


def YaoName_(pos):
    return YAO_NAME[pos]


def Yao_Pos(pos):
    return YAO_POS_DIZHI[pos]


# ------------------------------------------------------------------ 自检
def _selftest():
    GZ = {"year": "乙巳", "month": "壬午", "day": "乙卯", "time": "辛巳"}
    # 乾为天，全老阳 → 乾变坤，六爻全动
    ch = build_chart([coins_to_yao(3) for _ in range(6)], GZ, "子丑")
    assert ch["本卦"]["name"] == "乾为天", ch["本卦"]["name"]
    assert ch["变卦"]["name"] == "坤为地", ch["变卦"]["name"]
    assert ch["动爻"] == [1, 2, 3, 4, 5, 6]
    assert ch["爻"][0]["najia"] == "甲子", ch["爻"][0]["najia"]
    assert ch["爻"][5]["najia"] == "壬戌", ch["爻"][5]["najia"]

    # 坤为地，全少阴 → 静卦
    ch2 = build_chart([coins_to_yao(2) for _ in range(6)], GZ, "子丑")
    assert ch2["本卦"]["name"] == "坤为地"
    assert ch2["变卦"] is None and ch2["动爻"] == []
    assert [y["najia"] for y in ch2["爻"]] == [
        "乙未", "乙巳", "乙卯", "癸丑", "癸亥", "癸酉"]

    # 水火既济：下离上坎，纳甲须按内外卦分取（不是按卦宫）
    ch3 = build_chart([coins_to_yao(x) for x in (1, 2, 1, 2, 1, 2)], GZ, "子丑")
    assert ch3["本卦"]["name"] == "水火既济", ch3["本卦"]["name"]
    got = [y["najia"] for y in ch3["爻"]]
    assert got == ["己卯", "己丑", "己亥", "戊申", "戊戌", "戊子"], got
    assert [y["liuqin"] for y in ch3["爻"]] == [
        "子孙", "官鬼", "兄弟", "父母", "官鬼", "兄弟"]
    # 世应：三世卦应世3应6
    assert ch3["本卦"]["shi_pos"] == 3 and ch3["本卦"]["ying_pos"] == 6

    # 天风姤：下巽上乾，内卦应纳辛丑辛亥辛酉
    ch4 = build_chart([coins_to_yao(x) for x in (0, 1, 1, 1, 1, 1)], GZ, "子丑")
    assert ch4["本卦"]["name"] == "天风姤", ch4["本卦"]["name"]
    got4 = [y["najia"] for y in ch4["爻"]]
    assert got4 == ["辛丑", "辛亥", "辛酉", "壬午", "壬申", "壬戌"], got4

    print("六爻自检通过：乾/坤/既济/姤 四卦纳甲、六亲、世应一致")
    print("  乾为天:", [y["najia"] for y in ch["爻"]])
    print("  水火既济:", got)
    print("  天风姤:", got4)


if __name__ == "__main__":
    _selftest()
