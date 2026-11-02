# -*- coding: utf-8 -*-
"""盘面解析：把用户粘来的「别的软件排好的六爻盘」还原成标准盘。

思路不是硬读用户的每个字段，而是：
    1. 从文本里抠出最不可能出错的骨架 —— 六爻的阴阳与动不动
    2. 抠出时间／四柱／月建日辰
    3. 用脚本重新排一遍盘
    4. 拿重排结果去和用户原文里的纳甲、六亲、卦名逐项对账
    5. 对得上就交付标准盘；对不上就报冲突点，绝不硬猜

这样即使原盘格式千奇百怪，只要骨架没错，结果就一定能对上。

用法：
    python parse_chart.py 盘面.txt
    cat 盘面.txt | python parse_chart.py -
    python parse_chart.py --json 盘面.txt     # 只出 JSON
"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import gua_data as gd          # noqa: E402
import liuyao as ly            # noqa: E402

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

# 旬首地支 → 旬空两支
JIAXUN = {"子": "戌亥", "戌": "申酉", "申": "午未",
          "午": "辰巳", "辰": "寅卯", "寅": "子丑"}

YANG_SYMS = ("━━━", "▅▅▅▅▅", "▅▅▅▅ ▅", "———", "───")
YIN_SYMS = ("━ ━", "▅▅ ▅▅", "▅▅　▅▅", "— —", "- -")

POS_LABELS = {"初": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "上": 6}

 # ---------------------------------------------------------------- 基础换算
def xunkong_of_day(day_ganzhi: str) -> str:
    """由日柱干支推旬空两支。"""
    gz = day_ganzhi.strip()
    if len(gz) < 2 or gz[0] not in GAN or gz[1] not in ZHI:
        return ""
    gi, zi = GAN.index(gz[0]), ZHI.index(gz[1])
    head = ZHI[(zi - gi) % 12]
    return JIAXUN.get(head, "")


def normalize_ganzhi(month_gz: str, day_gz: str) -> dict:
    """把「丙戌月 / 甲戌日」这类文本整理成 {month:'丙戌', day:'甲戌'}。"""
    out = {"month": "", "day": ""}
    m = re.search(r"([%s])([%s])月" % (GAN, ZHI), month_gz or "")
    if m:
        out["month"] = m.group(0)[:-1]
    d = re.search(r"([%s])([%s])日" % (GAN, ZHI), day_gz or "")
    if d:
        out["day"] = d.group(0)[:-1]
    return out


# ---------------------------------------------------------------- 元信息
RE_DATETIME = [
    r"(20\d{2})\s*[年\-/.]\s*(\d{1,2})\s*[月\-/.]\s*(\d{1,2})\s*日?\s*(\d{1,2})\s*[时:：]\s*(\d{1,2})?",
    r"(20\d{2})[-\s]*(\d{1,2})[-\s]*(\d{1,2})\s+(\d{1,2}):(\d{2})",
]


def extract_datetime(text):
    for pat in RE_DATETIME:
        m = re.search(pat, text)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            h = int(m.group(4)) if m.group(4) else 0
            mi = int(m.group(5)) if len(m.groups()) >= 5 and m.group(5) else 0
            if 1 <= mo <= 12 and 1 <= d <= 31 and 0 <= h <= 23:
                return (y, mo, d, h, mi)
    return None


RE_FOURPILLARS = re.compile(
    r"(?:干支|四柱|起卦)?[：:\s]*([%s][%s])年\s*([%s][%s])月\s*([%s][%s])日\s*([%s][%s])时"
    % (GAN, ZHI, GAN, ZHI, GAN, ZHI, GAN, ZHI))


def extract_fourpillars(text):
    m = RE_FOURPILLARS.search(text)
    if not m:
        return None
    return {"year": m.group(1), "month": m.group(2),
            "day": m.group(3), "time": m.group(4)}


def extract_month_day(text):
    """单独抓「月建：戌 / 日辰：戌」或「戌月 甲戌日」。"""
    out = {}
    m = re.search(r"月建[：:]\s*([%s])" % ZHI, text)
    if m:
        out["月支"] = m.group(1)
    m = re.search(r"日辰[：:]\s*([%s])" % ZHI, text)
    if m:
        out["日支"] = m.group(1)
    d = re.search(r"([%s][%s])\s*日" % (GAN, ZHI), text)
    if d:
        out["日柱"] = d.group(1)
    mo = re.search(r"([%s][%s])\s*月" % (GAN, ZHI), text)
    if mo:
        out["月柱"] = mo.group(1)
    else:
        # 书里常见只写月支（如「卯月 甲寅日」），六爻只用月支，天干无关
        mo2 = re.search(r"([%s])\s*月" % ZHI, text)
        if mo2:
            out["月支"] = mo2.group(1)
    return out


def extract_xunkong(text):
    m = re.search(r"(?:旬空|空亡|空亡支)[：:\s]*([%s])\s*([%s])" % (ZHI, ZHI), text)
    if m:
        return m.group(1) + m.group(2)
    return ""


def extract_question(text):
    m = re.search(r"(?:所问|问题|占问|求测)[：:]\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------- 六爻行
RE_LIUSHEN = re.compile(r"(青龙|朱雀|勾陈|螣蛇|腾蛇|白虎|玄武)")
RE_LIUQIN = re.compile(r"(父母|兄弟|子孙|妻财|官鬼)")
RE_ZHI_GAN = re.compile(r"([%s])([%s])" % (GAN, ZHI))


RE_YANG_TOKEN = re.compile(r"▅▅▅▅▅|━━━")
RE_YIN_TOKEN = re.compile(r"▅▅[　\s]+▅▅|━[　\s]+━")


def classify_yao(sym_text):
    """判断阴阳。返回 True=阳, False=阴, None=看不出。

    关键：很多排盘软件把「本卦爻 → 变卦爻」放在同一行，行内同时出现阴阳两种符号。
    此时必须取**最靠左**的那个符号 —— 那才是本卦的爻，右边的属于变卦。
    """
    my = RE_YANG_TOKEN.search(sym_text)
    mn = RE_YIN_TOKEN.search(sym_text)
    if not my and not mn:
        return None
    if my and not mn:
        return True
    if mn and not my:
        return False
    return my.start() < mn.start()


RE_LABELED_YAO = re.compile(
    r"([初二三四五上])爻\s*[：:　 ]*\s*(老阳|少阳|老阴|少阴|阳动|阴动|阳|阴)")


def parse_yao_labeled(text):
    """「初爻 阳 / 三爻 阳 动」这类带位置标签的写法。"""
    found = {}
    for m in RE_LABELED_YAO.finditer(text):
        pos = POS_LABELS[m.group(1)]
        word = m.group(2)
        yang = word in ("阳", "老阳", "少阳", "阳动")
        dong = word in ("老阳", "老阴", "阳动", "阴动")
        # 标签后面紧跟「动」也算发动
        tail = text[m.end():m.end() + 3]
        if re.match(r"\s*[（(]?\s*动", tail):
            dong = True
        found[pos] = {"yang": yang, "dong": dong}
    if len(found) == 6:
        return [found[i] for i in range(1, 7)]
    return []


def is_dong(line):
    """是否发动。"""
    if re.search(r"[○×]", line):
        return True
    if re.search(r"(?<![不动变])动|→|化[^　\s]", line):
        return True
    return False


def parse_yao_rows(text):
    """从盘面文本里抓六爻行，返回 6 个 {pos?, yang, dong, liuqin, najia, shi, ying}。

    先尝试「带爻符号」的行；抓不到再退回纯文字/数字格式。
    """
    rows = []
    for raw in text.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue
        yang = classify_yao(line)
        if yang is None:
            continue
        row = {"raw": line.strip(), "yang": yang, "dong": is_dong(line)}
        m = RE_LIUQIN.search(line)
        if m:
            row["liuqin"] = m.group(1)
        m = RE_ZHI_GAN.search(line)
        if m:
            row["gan"], row["zhi"] = m.group(1), m.group(2)
            # 纳甲是「天干+地支」，六亲在它前面；避免把六亲的字当地支
        m = RE_LIUSHEN.search(line)
        if m:
            row["liushen"] = m.group(1).replace("腾蛇", "螣蛇")
        if "世" in line:
            row["shi"] = True
        if "应" in line:
            row["ying"] = True
        # 位置标签（初爻/上爻）
        m = re.search(r"([初上])爻", line)
        if m:
            row["pos"] = 1 if m.group(1) == "初" else 6
        else:
            m = re.search(r"([一二三四五六])爻", line)
            if m:
                row["pos"] = POS_LABELS[m.group(1)]
        rows.append(row)

    if len(rows) >= 6:
        return rows[:6] if len(rows) == 6 else _dedupe_rows(rows)
    return []


def _dedupe_rows(rows):
    """多于 6 行时，按有无位置标签、有无纳甲筛掉噪声行。"""
    scored = sorted(
        rows,
        key=lambda r: (0 if r.get("pos") else 1, 0 if r.get("zhi") else 1,
                       0 if r.get("liuqin") else 1),
    )
    picked = scored[:6]
    picked.sort(key=lambda r: r.get("pos", 0))
    return picked


def parse_yao_numeric(text):
    """纯数字摇卦：6 个 6/7/8/9，或 6 个 0~3 的背数。"""
    nums = re.findall(r"(?<!\d)([6-9])(?!\d)", text.replace("，", " ").replace(",", " "))
    seq = [int(n) for n in nums]
    if len(seq) >= 6:
        seq = seq[:6]
        return [{"yang": n in (7, 9), "dong": n in (6, 9), "_num": n} for n in seq]
    return []


def parse_yao_words(text):
    """显式文字：阳/阴 + 动。"""
    hits = re.findall(r"(老阳|少阳|老阴|少阴|阳动|阴动|阳|阴)", text)
    if len(hits) < 6:
        return []
    out = []
    for h in hits[:6]:
        yang = h in ("阳", "老阳", "少阳", "阳动")
        dong = h in ("老阳", "老阴", "阳动", "阴动")
        out.append({"yang": yang, "dong": dong})
    return out


# ---------------------------------------------------------------- 卦名
def extract_gua_names(text):
    """抓本卦/变卦名。返回 (本卦名, 变卦名)。"""
    names = [n for n in gd.GUA_NAME_BY_BIN.values()]
    all_names = sorted(set(names), key=len, reverse=True)
    found = []
    for n in all_names:
        if n in text:
            found.append(n)
    # 去掉被更长的卦名包含的
    found = [n for n in found if not any(n != o and n in o for o in found)]
    # 「X之Y」结构
    m = re.search(r"之", text)
    ben = bian = None
    for n in found:
        idx = text.index(n)
        if m and idx > m.start():
            bian = bian or n
        else:
            ben = ben or n
    return ben, bian


# ---------------------------------------------------------------- 主流程
def build_from_skeleton(lines6, ganzhi, xunkong="", question=""):
    """lines6: [{yang, dong}]*6（初→上）。"""
    chart = ly.build_chart(lines6, ganzhi, xunkong)
    return chart


def parse(text, datetime_hint=None):
    """解析盘面文本，返回 (chart, report)。"""
    report = {"警告": [], "缺失": [], "对账": [], "来源": "unknown"}
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # ---- 1. 时间与四柱
    dt = extract_datetime(text)
    fp = extract_fourpillars(text)
    md = extract_month_day(text)
    ganzhi = {"year": "", "month": "", "day": "", "time": ""}
    if dt:
        try:
            from lunar_python import Solar
            lunar = Solar.fromYmdHms(dt[0], dt[1], dt[2], dt[3], dt[4], 0).getLunar()
            ec = lunar.getEightChar()
            ganzhi = {"year": ec.getYear(), "month": ec.getMonth(),
                      "day": ec.getDay(), "time": ec.getTime()}
            report["起卦时间"] = "%04d-%02d-%02d %02d:%02d" % dt
        except Exception as e:      # noqa: BLE001
            report["警告"].append("公历转干支失败：%s" % e)
    if fp:
        ganzhi.update(fp)
        report["来源"] = "四柱文本"
    elif dt:
        report["来源"] = "公历时间"
    else:
        if md.get("月柱") or md.get("月支"):
            ganzhi["month"] = md.get("月柱", "")
            if not ganzhi["month"] and md.get("月支"):
                ganzhi["month"] = "甲" + md["月支"]
        if md.get("日柱") or md.get("日支"):
            ganzhi["day"] = md.get("日柱", "")
            if not ganzhi["day"] and md.get("日支"):
                ganzhi["day"] = "甲" + md["日支"]
        if ganzhi["day"]:
            report["来源"] = "月建日辰文本"
            report["警告"].append("缺少年柱与时柱；六爻判断只用月建、日辰与日干，已足够，"
                                  "但六神按日干取，请确认日干无误")
    if fp:
        report["来源"] = "四柱文本"

    if not ganzhi["day"]:
        report["缺失"].append("日柱（日干定六神、日支定日辰旺衰）")
    if not ganzhi["month"]:
        report["缺失"].append("月柱（月建定一月旺衰）")

    # ---- 2. 六爻骨架
    rows = parse_yao_rows(text)
    order = "上→初"
    lines6 = []
    seq = []          # 初→上 顺序的原始行，供后面对账
    labeled = parse_yao_labeled(text) if len(rows) < 6 else []
    if rows:
        # 行序：若首行标了上爻或末行标了初爻，说明是上→下
        if rows[0].get("pos") == 6 or rows[-1].get("pos") == 1:
            order = "上→初"
            seq = list(reversed(rows))
        elif rows[0].get("pos") == 1:
            order = "初→上"
            seq = rows
        else:
            order = "上→初（默认）"
            seq = list(reversed(rows))
        lines6 = [{"yang": r["yang"], "dong": r["dong"]} for r in seq]
        report["读法"] = order
    else:
        if labeled:
            lines6 = labeled
            report["读法"] = "位置标签"
        num6 = parse_yao_numeric(text) if not lines6 else []
        if num6:
            lines6 = [{"yang": r["yang"], "dong": r["dong"]} for r in num6]
            report["读法"] = "数字"
            report["来源"] = "数字摇卦"
        elif not lines6:
            w = parse_yao_words(text)
            if w:
                lines6 = w
                report["读法"] = "文字阴阳"

    if len(lines6) != 6:
        report["缺失"].append("六个爻的阴阳与动不动（这是排盘的骨架，必须给全）")
        return None, report

    # ---- 3. 旬空
    xunkong = extract_xunkong(text)
    if not xunkong and ganzhi.get("day"):
        xunkong = xunkong_of_day(ganzhi["day"])
        report["对账"].append("旬空由日柱推算：%s" % xunkong)

    # ---- 4. 重排
    chart = ly.build_chart(lines6, ganzhi, xunkong)
    chart["起卦时间"] = report.get("起卦时间", "")
    chart["干支"] = ganzhi
    chart["所问"] = extract_question(text)
    chart["解析报告"] = report
    report["来源"] = report["来源"] if report["来源"] != "unknown" else "重排"

    # ---- 5. 对账
    ben_name, bian_name = extract_gua_names(text)
    calc_ben = chart["本卦"]["name"]
    calc_bian = chart["变卦"]["name"] if chart.get("变卦") else None
    if ben_name:
        if ben_name == calc_ben:
            report["对账"].append("本卦名一致：%s" % calc_ben)
        else:
            report["警告"].append("本卦对不上：原文「%s」vs 骨架重排「%s」"
                                  % (ben_name, calc_ben))
    if bian_name and calc_bian:
        if bian_name == calc_bian:
            report["对账"].append("变卦名一致：%s" % calc_bian)
        else:
            report["警告"].append("变卦对不上：原文「%s」vs 骨架重排「%s」"
                                  % (bian_name, calc_bian))

    # 逐爻对账纳甲与六亲（seq 已按初→上 排好，与 chart["爻"] 同序）
    mismatch = 0
    for i, y in enumerate(chart["爻"]):
        r = seq[i] if seq and i < len(seq) else None
        if not r:
            continue
        if r.get("zhi") and r["zhi"] != y["zhi"]:
            report["警告"].append("%s 地支对不上：原文「%s%s」vs 重排「%s%s」"
                                  % (y["pos_name"], r.get("gan", ""), r["zhi"],
                                     y["gan"], y["zhi"]))
            mismatch += 1
        if r.get("liuqin") and r["liuqin"] != y["liuqin"]:
            report["警告"].append("%s 六亲对不上：原文「%s」vs 重排「%s」"
                                  % (y["pos_name"], r["liuqin"], y["liuqin"]))
            mismatch += 1
    if rows and mismatch == 0:
        report["对账"].append("六爻纳甲与六亲逐爻一致")

    return chart, report


def render_report(report):
    out = []
    out.append("【解析报告】")
    out.append("  来源：%s　读法：%s" % (report.get("来源", "?"), report.get("读法", "?")))
    if report.get("起卦时间"):
        out.append("  起卦时间：%s" % report["起卦时间"])
    if report["对账"]:
        out.append("  对账通过：")
        for s in report["对账"]:
            out.append("    ✓ %s" % s)
    if report["警告"]:
        out.append("  警告：")
        for s in report["警告"]:
            out.append("    ! %s" % s)
    if report["缺失"]:
        out.append("  缺失（必须向用户补问）：")
        for s in report["缺失"]:
            out.append("    × %s" % s)
    return "\n".join(out)


def main():
    args = sys.argv[1:]
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    if not args:
        print(__doc__)
        return 1
    src = args[0]
    text = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()

    chart, report = parse(text)
    if chart is None:
        print(render_report(report))
        return 2
    if as_json:
        print(json.dumps(chart, ensure_ascii=False, indent=2))
    else:
        print(render_report(report))
        print()
        import paipan
        print(paipan.render_liuyao_text(chart, chart.get("所问", "")))
    return 0 if not report["警告"] else 3


if __name__ == "__main__":
    sys.exit(main())
