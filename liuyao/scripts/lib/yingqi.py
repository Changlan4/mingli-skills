# -*- coding: utf-8 -*-
"""六爻应期推算：按用神状态生成候选应验日期（确定性规则，非自由发挥）。

规则来源：值日、冲空、填实、冲墓、逢合、冲飞神。
输出的是候选日期与依据，最终如何取舍由上层解读判断。
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lunar_python import Solar  # noqa: E402
from gua_data import ZHI_CHONG, ZHI_LIUHE, ZHI_WUXING, WX_MU  # noqa: E402

# 六亲生克：官鬼生父母、父母生兄弟、兄弟生子孙、子孙生妻财、妻财生官鬼
# 原神 = 生用神的那一亲
YUANSHEN = {
    "父母": "官鬼",
    "兄弟": "父母",
    "子孙": "兄弟",
    "妻财": "子孙",
    "官鬼": "妻财",
}


def day_ganzhi(dt: datetime) -> str:
    """某日的日干支。取正午，避开子时歧义。"""
    lunar = Solar.fromYmdHms(dt.year, dt.month, dt.day, 12, 0, 0).getLunar()
    return lunar.getDayInGanZhi()


def month_zhi_of(dt: datetime) -> str:
    lunar = Solar.fromYmdHms(dt.year, dt.month, dt.day, 12, 0, 0).getLunar()
    return lunar.getMonthZhi()


def choose_yongshen(chart: dict, liuqin: str, prefer_pos: str = "") -> dict:
    """在本卦中定位用神。

    顺序：指定位置（来自「舍衰取旺」的取舍结果）> 动爻 > 世爻 > 第一个。
    本卦不现时返回伏神。
    """
    yao = [y for y in chart["爻"] if y["liuqin"] == liuqin]
    if yao and prefer_pos:
        for y in yao:
            if y["pos_name"] == prefer_pos:
                return {"where": "本卦", **y}
    if yao:
        dong = [y for y in yao if y["dong"]]
        if dong:
            return {"where": "本卦", **dong[0]}
        shi = [y for y in yao if y["shi"]]
        if shi:
            return {"where": "本卦", **shi[0]}
        return {"where": "本卦", **yao[0]}
    for f in chart.get("伏神", []):
        if f["liuqin"] == liuqin:
            return {"where": "伏神", **f}
    return {}


def build_conditions(ys: dict, chart: dict = None) -> list:
    """根据用神状态，生成「什么日子算应期」的条件列表。"""
    conds = []
    zhi = ys.get("zhi")
    if not zhi:
        return conds
    kong = ys.get("is_kong", False)
    ru_mu = ys.get("is_ru_mu", False)
    mu_zhi = ys.get("mu_zhi") or WX_MU.get(ZHI_WUXING[zhi])
    month_po = ys.get("is_month_po", False)
    is_fushen = "fei_shen" in ys

    if kong:
        conds.append(("出空填实", lambda gz, z=zhi: gz[1] == z,
                      f"用神{zhi}空亡，逢{zhi}日填实"))
        conds.append(("冲空", lambda gz, z=zhi: ZHI_CHONG[z] == gz[1],
                      f"用神{zhi}空亡，逢{ZHI_CHONG[zhi]}日冲空"))
    else:
        conds.append(("值日", lambda gz, z=zhi: gz[1] == z,
                      f"用神{zhi}当值，逢{zhi}日应"))

    if ru_mu:
        conds.append(("冲墓", lambda gz, m=mu_zhi: ZHI_CHONG[m] == gz[1],
                      f"用神入{mu_zhi}墓，逢{ZHI_CHONG[mu_zhi]}日冲墓"))

    if month_po:
        conds.append(("逢合", lambda gz, z=zhi: ZHI_LIUHE[z] == gz[1],
                      f"用神{zhi}月破，逢{ZHI_LIUHE[zhi]}日合起"))

    if is_fushen:
        fei = ys["fei_shen"]["zhi"]
        conds.append(("冲飞神", lambda gz, f=fei: ZHI_CHONG[f] == gz[1],
                      f"用神伏于{fei}下，逢{ZHI_CHONG[fei]}日冲开飞神"))
        conds.append(("伏神值日", lambda gz, z=zhi: gz[1] == z,
                      f"伏神{zhi}值日透出"))

    if ys.get("dong"):
        conds.append(("动爻值日", lambda gz, z=zhi: gz[1] == z,
                      f"用神发动，逢{zhi}日应"))

    # 化绊解绊：用神或原神被合绊住，须冲开绊神才见实效
    ys_lq = ys.get("liuqin") or ""
    yuan = YUANSHEN.get(ys_lq)
    for y in (chart or {}).get("爻", []):
        if not (y["dong"] and y.get("bian") and y["bian"].get("hua_ban")):
            continue
        if y["liuqin"] not in (ys_lq, yuan):
            continue
        ban_zhi = y["bian"]["zhi"]
        role = "用神" if y["liuqin"] == ys_lq else "原神"
        conds.append((
            f"解绊-{y['pos_name']}",
            lambda gz, b=ban_zhi: ZHI_CHONG[b] == gz[1],
            f"{role}{y['pos_name']}{y['najia']}化{y['bian']['najia']}成合绊，"
            f"逢{ZHI_CHONG[ban_zhi]}日冲开绊神{ban_zhi}方得解脱",
        ))

    # 去重（保留首个同名条件）
    seen, out = set(), []
    for name, fn, desc in conds:
        if name in seen:
            continue
        seen.add(name)
        out.append((name, fn, desc))
    return out


def calc_yingqi(chart: dict, start: datetime, yongshen_liuqin: str,
                days: int = 60, max_hits: int = 15, prefer_pos: str = "") -> dict:
    """生成未来 days 天内的候选应期。"""
    ys = choose_yongshen(chart, yongshen_liuqin, prefer_pos)
    if not ys:
        return {"用神": yongshen_liuqin, "候选": [],
                "说明": "未在卦中找到该六亲，无法推应期"}
    conds = build_conditions(ys, chart)

    hits = []
    for i in range(1, days + 1):
        d = start + timedelta(days=i)
        gz = day_ganzhi(d)
        reasons = [desc for name, fn, desc in conds if fn(gz)]
        if reasons:
            hits.append({
                "日期": d.strftime("%Y-%m-%d"),
                "日干支": gz,
                "月建": month_zhi_of(d),
                "距起卦": f"{i}天后",
                "依据": reasons,
            })
        if len(hits) >= max_hits:
            break

    state = []
    if ys.get("is_kong"):
        state.append("旬空")
    if ys.get("is_ru_mu"):
        state.append(f"入{ys.get('mu_zhi')}墓")
    if ys.get("is_month_po"):
        state.append("月破")
    if ys.get("is_day_po"):
        state.append("日破")
    if "fei_shen" in ys:
        state.append(f"伏于{ys['fei_shen']['zhi']}下")
    if ys.get("dong"):
        state.append("发动")

    # 月建变化节点：月破之爻逢换月即「出破」
    jiedian, prev = [], month_zhi_of(start)
    for i in range(1, days + 1):
        d = start + timedelta(days=i)
        mz = month_zhi_of(d)
        if mz != prev:
            jiedian.append({
                "日期": d.strftime("%Y-%m-%d"),
                "新月建": mz,
                "说明": f"由{prev}月转{mz}月；月破或受月建克制者，逢此日出脱",
            })
            prev = mz

    # 忌日：冲伤原神者不利（如原神午火被冲，则不能生用神）
    yuan_lq = YUANSHEN.get(yongshen_liuqin)
    ji, seen_ji = [], set()
    yuan_yaos = [y for y in chart.get("爻", []) if y["liuqin"] == yuan_lq]
    if yuan_yaos:
        yz, ynj = yuan_yaos[0]["zhi"], yuan_yaos[0]["najia"]
        for i in range(1, days + 1):
            d = start + timedelta(days=i)
            gz = day_ganzhi(d)
            if ZHI_CHONG[yz] == gz[1] and gz not in seen_ji:
                seen_ji.add(gz)
                ji.append({
                    "日期": d.strftime("%Y-%m-%d"),
                    "日干支": gz,
                    "说明": f"冲伤原神{yuan_lq}{ynj}，原神不能生用神，此日不宜取为应期",
                })
            if len(ji) >= 4:
                break

    return {
        "用神": yongshen_liuqin,
        "用神位置": f"{ys['where']}·{ys.get('pos_name', '')}·{ys.get('najia', '')}",
        "用神地支": ys.get("zhi"),
        "用神状态": state or ["静而待应"],
        "候选": hits,
        "忌日": ji,
        "月建节点": jiedian,
        "说明": "按值日/冲空/填实/冲墓/逢合/冲飞神/解绊七类规则机械生成，"
                "仅列候选与依据；实际应验取哪一天，须结合用神旺衰与事之缓急判断",
    }


if __name__ == "__main__":
    from liuyao import build_chart, coins_to_yao
    GZ = {"year": "乙巳", "month": "丙戌", "day": "甲戌", "time": "己巳"}
    ch = build_chart([coins_to_yao(x) for x in (1, 2, 3, 0, 1, 2)], GZ, "申酉")
    r = calc_yingqi(ch, datetime(2025, 11, 1, 10, 30), "妻财")
    print("用神:", r["用神位置"], r["用神状态"])
    for h in r["候选"][:8]:
        print(" ", h["日期"], h["日干支"], "|", "；".join(h["依据"]))
