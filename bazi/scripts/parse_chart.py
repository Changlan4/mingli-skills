#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
八字盘面对账校验：把用户粘来的盘（别的软件/书上/手抄）逐项拆开，用引擎重算，逐条挑错。

为什么需要它：排盘软件口径极不统一——真太阳时用不用、早/晚子时怎么算、
起运按 3 天 1 年还是精确到时辰、十神按日干还是年干。只要四柱错一个字，
后面解什么都白搭。本工具不改用户的盘，只做"哪一项对、哪一项不对"的核对。

用法：
  python parse_chart.py 盘面.txt
  python parse_chart.py 盘面.txt --birth "1990-06-15 10:00" --gender male --city 上海
  cat 盘面.txt | python parse_chart.py - --json

能校验的（不需要出生时间，纯靠盘面内部一致性）：
  十神、藏干、纳音、旬空、日柱旬空、大运序列与顺逆、起运岁数合理性
能校验的（给了出生时间）：
  四柱本身、真太阳时、大运起点
"""
import argparse
import json as jsonlib
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from bazi_const import (  # noqa: E402
    GAN, ZHI, CANG_GAN, GAN_WUXING, GAN_YINYANG, NAYIN, WUSHU, shishen, KE, SHENG,
)
from bazi import paipan, changsheng, _xunkong  # noqa: E402

GAN_CLASS = "[" + GAN + "]"
ZHI_CLASS = "[" + ZHI + "]"
GZ_RE = re.compile(GAN_CLASS + ZHI_CLASS)
GAN_RUN = re.compile(GAN_CLASS + "{2,}")
ZHI_RUN = re.compile(ZHI_CLASS + "{2,}")

SHISHEN_WORDS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印",
                 "枭神", "日元", "日主"]

COL = ["年柱", "月柱", "日柱", "时柱"]


# ---------------------------------------------------------------- 解析

def _pairs_from_text(text):
    """从文本中尽力还原四柱 [(干,支)×4] 与大运干支"""
    result = {"four": None, "dayun": [], "gender": None, "start_age": None,
              "shishen_marks": [], "raw_shishen": []}

    # 性别
    if re.search(r"[乾]造|乾命|男命|性别[:：]\s*男", text):
        result["gender"] = 1
    if re.search(r"[坤]造|坤命|女命|性别[:：]\s*女", text):
        result["gender"] = 0

    # 起运岁数（"6岁起运"/"起运：6年"/"大运 6 岁"）
    m = re.search(r"起运[^\d]{0,6}(\d{1,2})\s*(岁|年)", text)
    if not m:
        m = re.search(r"(\d{1,2})\s*岁\s*(起运|上运|交运)", text)
    if m:
        result["start_age"] = int(m.group(1))

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    def split_gan_zhi(ln):
        clean = re.sub(r"\s+", "", ln)
        gs = [c for c in clean if c in GAN]
        zs = [c for c in clean if c in ZHI]
        return gs, zs

    # 路线 B 优先：上下两行，一行 4 天干、下一行 4 地支（常见软件的竖排表格）
    # 这条最可靠，因为能精确锁定"天干行 + 地支行"这一对，不会误抓大运行。
    for i in range(len(lines) - 1):
        g1, z1 = split_gan_zhi(lines[i])
        g2, z2 = split_gan_zhi(lines[i + 1])
        if len(g1) == 4 and not z1 and len(z2) == 4 and not g2:
            result["four"] = [g1[j] + z2[j] for j in range(4)]
            break

    # 路线 A：单行直接给四柱，排除大运/运程行
    if result["four"] is None:
        for ln in lines:
            if "大运" in ln or "运程" in ln or "流年" in ln:
                continue
            hits = GZ_RE.findall(ln)
            if len(hits) == 4:
                result["four"] = hits
                break

    # 路线 A2：兜底，取首个不是大运行的 4 个
    if result["four"] is None:
        for ln in lines:
            if "大运" in ln or "运程" in ln:
                continue
            hits = GZ_RE.findall(ln)
            if len(hits) >= 4:
                result["four"] = hits[:4]
                break

    # 大运：从"大运"所在行开始往后取干支。注意不能按"是否与四柱相同"过滤——
    # 大运第一个干支很可能恰好与年柱/月柱同字（如命例甲年柱乙亥，第五步大运也是乙亥）。
    for i, ln in enumerate(lines):
        if "大运" in ln or "运程" in ln:
            chunk = "\n".join(lines[i:i + 6])
            dys = GZ_RE.findall(chunk)
            if len(dys) >= 2:
                seen, out = set(), []
                for d in dys:
                    if d not in seen:
                        seen.add(d)
                        out.append(d)
                result["dayun"] = out[:12]
            break

    return result


# ---------------------------------------------------------------- 对账

def check(four, gender=None, dayun=None, start_age=None, birth=None):
    """
    返回 (报告行列表, 结构化结果)
    报告每行：(等级, 项目, 说明)  等级 ∈ ✓ / ✗ / ? / ⚠
    """
    rep = []
    info = {"四柱": four, "项目": []}

    def add(level, item, msg):
        rep.append((level, item, msg))
        info["项目"].append({"等级": level, "项目": item, "说明": msg})

    day_gan = four[2][0]
    add("✓", "日柱", f"{four[2]}（日主 {day_gan}{GAN_WUXING[day_gan]}，"
                     f"{GAN_YINYANG[day_gan]}干）")

    # 1) 干支组合合法性：天干地支必须同阴阳
    bad = []
    for i, gz in enumerate(four):
        gi, zi = GAN.index(gz[0]), ZHI.index(gz[1])
        if gi % 2 != zi % 2:
            bad.append(f"{COL[i]} {gz}")
    legal = not bad
    if bad:
        add("✗", "干支组合", "阴阳不配（六十甲子不存在此组合）：" + "、".join(bad) +
            "　→ 极可能是抄错或软件错误。**此柱无效，与之相关的藏干/十神/纳音结论均不可信**")
    else:
        add("✓", "干支组合", "四柱均为合法六十甲子组合")

    # 2) 五鼠遁：时柱的时干必须与本日日干配套（排盘软件最常错在这里）
    try:
        base = GAN.index(WUSHU[day_gan])
        expect_hour_gan = GAN[(base + ZHI.index(four[3][1])) % 10]
        if expect_hour_gan == four[3][0]:
            add("✓", "五鼠遁", f"日干{day_gan}见时支{four[3][1]}，时干应为"
                              f"{expect_hour_gan}，盘中{four[3][0]} ✓")
        else:
            add("✗", "五鼠遁", f"日柱{four[2]}、时支{four[3][1]}，按五鼠遁时干必为"
                              f"{expect_hour_gan}（即 {expect_hour_gan}{four[3][1]}），"
                              f"盘中却作 {four[3]}。时柱与日柱不配套——要么日柱错，"
                              f"要么时柱错，要么时辰记错。")
    except Exception as e:
        add("?", "五鼠遁", f"无法校验：{e}")

    # 3) 藏干（引擎给出的标准答案）
    cg_lines = []
    for i, gz in enumerate(four):
        hides = CANG_GAN[gz[1]]
        cg_lines.append(f"{COL[i]}{gz}→{'/'.join(hides)}")
    add("⚠" if bad else "✓", "藏干", "；".join(cg_lines) +
        ("（注：其中含非法柱，仅供参考）" if bad else ""))

    # 4) 十神（按日干重算）
    ss_lines = []
    for i, gz in enumerate(four):
        if i == 2:
            continue
        ss_lines.append(f"{COL[i]}{gz[0]}={shishen(day_gan, gz[0])}")
    add("✓", "天干十神", "；".join(ss_lines))

    # 5) 纳音
    ny = [f"{COL[i]}{gz}={NAYIN.get(gz, '不存在')}" for i, gz in enumerate(four)]
    add("✓", "纳音", "；".join(ny))

    # 6) 旬空
    xk = _xunkong(GAN.index(four[2][0]), ZHI.index(four[2][1]))
    add("✓", "旬空", f"日柱{four[2]}属旬空 {xk}")

    # 7) 大运序列与顺逆
    if dayun:
        month_gz = four[1]
        mi_g, mi_z = GAN.index(month_gz[0]), ZHI.index(month_gz[1])
        forward_seq, backward_seq = [], []
        for k in range(1, len(dayun) + 2):
            forward_seq.append(GAN[(mi_g + k) % 10] + ZHI[(mi_z + k) % 12])
            backward_seq.append(GAN[(mi_g - k) % 10] + ZHI[(mi_z - k) % 12])

        fwd_match = all(dayun[k] == forward_seq[k] for k in range(min(len(dayun), len(forward_seq))))
        bwd_match = all(dayun[k] == backward_seq[k] for k in range(min(len(dayun), len(backward_seq))))

        if fwd_match:
            direction = "顺行"
            add("✓", "大运序列", f"与月柱{month_gz}顺排一致（{'>'.join(dayun[:4])}…）")
        elif bwd_match:
            direction = "逆行"
            add("✓", "大运序列", f"与月柱{month_gz}逆排一致（{'>'.join(dayun[:4])}…）")
        else:
            direction = None
            # 诊断：是否只是整体错位（最常见的是第一步误用月柱本身）
            shifted_f = all(dayun[k] == forward_seq[k + 1] for k in range(min(len(dayun) - 1, len(forward_seq) - 1)))
            shifted_b = all(dayun[k] == backward_seq[k + 1] for k in range(min(len(dayun) - 1, len(backward_seq) - 1)))
            if dayun[0] == month_gz:
                add("✗", "大运序列",
                    f"大运第一步用了月柱本身（{month_gz}）。大运应从月柱的**下一柱**起步，"
                    f"{'顺' if shifted_f or not shifted_b else '逆'}排应为："
                    f"{'>'.join((forward_seq if not shifted_b else backward_seq)[:len(dayun)])}。"
                    f"整体错开一格。")
            elif shifted_f or shifted_b:
                seq = forward_seq if shifted_f else backward_seq
                add("✗", "大运序列",
                    f"整体错位一格。按{'顺' if shifted_f else '逆'}排应为："
                    f"{'>'.join(seq[:len(dayun)])}，盘中为 {'>'.join(dayun[:6])}。")
            else:
                add("✗", "大运序列",
                    f"既非顺排也非逆排。\n     盘中：{'>'.join(dayun[:6])}\n"
                    f"     顺排应为：{'>'.join(forward_seq[:len(dayun)])}\n"
                    f"     逆排应为：{'>'.join(backward_seq[:len(dayun)])}")

        # 顺逆与年份阴阳是否相符
        if direction and gender is not None:
            year_gan = four[0][0]
            yang_year = GAN_YINYANG[year_gan] == "阳"
            expect_forward = (yang_year and gender == 1) or ((not yang_year) and gender == 0)
            got_forward = (direction == "顺行")
            if expect_forward == got_forward:
                add("✓", "大运方向", f"{'阳' if yang_year else '阴'}年{'男' if gender == 1 else '女'}命"
                                     f"应{'顺' if expect_forward else '逆'}排，盘中为{direction} ✓")
            else:
                add("✗", "大运方向", f"{'阳' if yang_year else '阴'}年{'男' if gender == 1 else '女'}命"
                                     f"应{'顺' if expect_forward else '逆'}排，但盘中为{direction} ✗")

    # 7) 起运岁数合理性
    if start_age is not None:
        if 1 <= start_age <= 10:
            add("✓", "起运岁数", f"{start_age} 岁起运，在合理范围（1-10 岁）")
        else:
            add("⚠", "起运岁数", f"{start_age} 岁起运，超出常见范围，确认是否为虚岁/周岁口径")

    # 8) 有出生时间则核对四柱
    if birth:
        try:
            r = paipan(birth["y"], birth["m"], birth["d"], birth["h"], birth["mi"],
                       gender=gender if gender is not None else 1,
                       city=birth.get("city"), longitude=birth.get("lon"))
            engine_four = r["八字"].split()
            diff = [(COL[i], four[i], engine_four[i])
                    for i in range(4) if four[i] != engine_four[i]]
            if diff:
                msg = "；".join(f"{c}: 盘中{d} vs 引擎算{e}" for c, d, e in diff)
                add("✗", "四柱核对", msg)
            else:
                add("✓", "四柱核对", f"与出生时间 {r['输入']['公历']} 排出的四柱完全一致")
            info["引擎重排"] = engine_four
            info["引擎真太阳时"] = r["真太阳时"]
            for w in r.get("warnings", []):
                add("⚠", "边界告警", w)
        except Exception as e:
            add("?", "四柱核对", f"无法重排：{e}")

    return rep, info


def render_report(rep, info, parsed):
    L = []
    a = L.append
    a("=" * 60)
    a("【排盘对账报告】")
    a("=" * 60)
    four = parsed["four"]
    gender = parsed.get("gender")
    gtxt = {1: "乾造（男）", 0: "坤造（女）", None: "性别未识别"}[gender]
    a(f"识别到 {len(four)} 柱：{'　'.join(four)}　{gtxt}")
    if parsed.get("dayun"):
        a(f"识别到大运：{'　'.join(parsed['dayun'][:8])}")
    a("")
    n_ok = n_bad = n_unk = n_warn = 0
    for level, item, msg in rep:
        if level == "✓":
            n_ok += 1
        elif level == "✗":
            n_bad += 1
        elif level == "⚠":
            n_warn += 1
        else:
            n_unk += 1
        a(f"{level} {item}：{msg}")
    a("")
    a("-" * 60)
    if n_bad == 0:
        a(f"结论：未发现硬错误（{n_ok} 项通过{f'，{n_warn} 项需注意' if n_warn else ''}）。")
    else:
        a(f"结论：发现 {n_bad} 处硬错误，必须先与用户确认再解读。")
        a("　　　排盘错在四柱/大运上，后面无论怎么解都是错的。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="八字盘面对账校验")
    ap.add_argument("file", help="盘面文本文件，- 表示从 stdin 读")
    ap.add_argument("--birth", help='出生时间 "1990-06-15 10:00"（给了才能核对四柱）')
    ap.add_argument("--gender", help="male/female/男/女")
    ap.add_argument("--city", help="出生城市")
    ap.add_argument("--lon", type=float, help="出生地经度")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.file == "-":
        text = sys.stdin.read()
    else:
        with open(args.file, encoding="utf-8", errors="ignore") as f:
            text = f.read()

    parsed = _pairs_from_text(text)
    if not parsed["four"]:
        print("✗ 未能从文本中识别出四柱。请确认盘面里有 4 个干支（如 庚午 壬午 辛亥 癸巳），"
              "或按『天干一行 / 地支一行』的格式贴出。", file=sys.stderr)
        sys.exit(1)

    gender = parsed["gender"]
    if args.gender:
        gender = 1 if str(args.gender).lower() in ("male", "m", "男", "乾") else 0
        parsed["gender"] = gender  # 回写，否则报告头仍显示"性别未识别"

    birth = None
    if args.birth:
        s = args.birth.replace("/", "-")
        dp, tp = (s.split(" ") + ["12:00"])[:2]
        y, m, d = [int(x) for x in dp.split("-")]
        h, mi = [int(x) for x in tp.replace("：", ":").split(":")[:2]]
        birth = {"y": y, "m": m, "d": d, "h": h, "mi": mi,
                 "city": args.city, "lon": args.lon}

    rep, info = check(parsed["four"], gender=gender, dayun=parsed["dayun"],
                      start_age=parsed["start_age"], birth=birth)

    if args.json:
        print(jsonlib.dumps({"识别": parsed, "报告": info}, ensure_ascii=False, indent=2))
    else:
        print(render_report(rep, info, parsed))


if __name__ == "__main__":
    main()
