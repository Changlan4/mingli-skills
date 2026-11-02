# -*- coding: utf-8 -*-
"""六爻排盘命令行入口。

用法：
  python paipan.py liuyao --yao "7 8 9 6 7 8" --datetime "2025-11-01 10:30" --question "问财运"
  python paipan.py liuyao --yao "阳,阴,阳动,阴,阳,阴" --datetime "2025-11-01 10:30"

输出：默认 JSON（供 agent 使用）；--text 输出人类可读盘面。
"""
import sys
import os
import json
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from lunar_python import Solar  # noqa: E402
from gua_data import ZHI_WUXING, SHENG, KE  # noqa: E402
import liuyao as liuyao_mod  # noqa: E402


def parse_time(text: str) -> dict:
    """解析「2025-11-01 10:30 / 2025年11月1日 10时30分」这类时间写法。"""
    import re
    s = text.strip()
    s = s.replace("年", "-").replace("月", "-").replace("日", " ").replace("/", "-")
    s = s.replace("时", ":").replace("点", ":").replace("分", "")
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})[ T]*(\d{1,2})?:?(\d{1,2})?", s)
    if not m:
        raise ValueError(f"无法解析时间：{text}")
    return {
        "year": int(m.group(1)), "month": int(m.group(2)), "day": int(m.group(3)),
        "hour": int(m.group(4)) if m.group(4) else 0,
        "minute": int(m.group(5)) if m.group(5) else 0,
    }


# ------------------------------------------------------------------ 四柱
def ganzhi_of_datetime(dt) -> dict:
    lunar = Solar.fromYmdHms(dt.year, dt.month, dt.day,
                             dt.hour, dt.minute, 0).getLunar()
    ec = lunar.getEightChar()
    return {
        "year": ec.getYear(),
        "month": ec.getMonth(),
        "day": ec.getDay(),
        "time": ec.getTime(),
        "xunkong": lunar.getDayXunKong(),
        "lunar": lunar.toString(),
    }


# ------------------------------------------------------------------ 用神取舍
def render_liuyao_text(chart: dict, question: str = "") -> str:
    lines = []
    ben, bian = chart["本卦"], chart["变卦"]
    lines.append(f"起卦：{chart.get('起卦时间', '')}  "
                 f"{chart['干支']['year']}年 {chart['干支']['month']}月 "
                 f"{chart['干支']['day']}日 {chart['干支']['time']}时")
    lines.append(f"月建：{chart['月建']}　日辰：{chart['日辰']}　旬空：{chart['旬空'] or '—'}")
    if question:
        lines.append(f"所问：{question}")
    lines.append("")
    title = f"{ben['full_name']}（{ben['gong']}宫·{ben['seq_name']}·{ben['body']}）"
    if bian:
        title += f"　之　{bian['name']}（{bian['body']}）"
    lines.append(title)
    gb = chart.get("卦体", {}).get("组合")
    if gb:
        lines.append(f"卦体：{gb}")
    ban = chart.get("化绊") or {}
    if ban.get("化绊数"):
        lines.append(f"化绊：{ban['化绊数']}/{ban['动爻数']} 个动爻化绊 —— {ban['定性']}")
    fy = chart.get("反吟") or {}
    if fy.get("has"):
        lines.append(f"反吟：{'、'.join(fy['pairs'])}（主反复）")
    lines.append("")
    lines.append("─────────────── 六爻（上 → 初）───────────────")
    for y in reversed(chart["爻"]):
        mark = ""
        if y["shi"]:
            mark = " 世"
        elif y["ying"]:
            mark = " 应"
        shen = y["liushen"]
        lq = y["liuqin"]
        nj = y["najia"]
        sym = y["yao_symbol"]
        extras = []
        if y.get("is_kong"):
            extras.append("空")
        if y.get("is_ru_mu"):
            extras.append(f"入{y.get('mu_zhi', '')}墓")
        if y.get("is_month_po"):
            extras.append("月破")
        if y.get("is_day_chong"):
            extras.append(f"日冲·{y.get('day_chong_judge', '')}")
        ext = ("(" + ",".join(extras) + ")") if extras else ""
        bian_s = ""
        if y.get("bian"):
            b = y["bian"]
            bian_s = f"　→ {b['najia']} {b['liuqin']}{b['wuxing']}"
            if b.get("jin_tui") in ("进", "退"):
                bian_s += f"（化{b['jin_tui']}神）"
            if b.get("hua_mu"):
                bian_s += "（化墓）"
            if b.get("hua_ban"):
                bian_s += "（化绊）"
            if b.get("ke_dong"):
                bian_s += "（回头克）"
        lines.append(f"{y['pos_name']} {shen} {lq}{nj}{y['wuxing']} {sym}{ext}{mark}"
                     f"{' 动' if y['dong'] else ''}{bian_s}")
    lines.append("─────────────────────────────────────────────")
    if chart["伏神"]:
        parts = []
        for f in chart["伏神"]:
            s = f"{f['pos_name']}伏{f['liuqin']}{f['najia']}{f['wuxing']}"
            if f.get("feifu"):
                s += f"（{f['feifu']['relation']}）"
            if f.get("is_ru_mu"):
                s += f"（入{f['mu_zhi']}墓）"
            parts.append(s)
        lines.append("伏神：" + "；".join(parts))
    return "\n".join(lines)


# ------------------------------------------------------------------ 入口
def main():
    ap = argparse.ArgumentParser(description="六爻排盘")
    ap.add_argument("kind", choices=["liuyao"], help="排盘类型（仅六爻）")
    ap.add_argument("--yao", help='六爻摇卦结果，如 "7 8 9 6 7 8"')
    ap.add_argument("--datetime", help="起卦时间，如 2025-11-01 10:30")
    ap.add_argument("--question", default="", help="所问何事")
    ap.add_argument("--gender", default="", choices=["", "male", "female"],
                    help="性别，仅用于婚姻类取用（男取妻财，女取官鬼）")
    ap.add_argument("--text", action="store_true", help="输出人类可读盘面")
    args = ap.parse_args()

    if not args.yao:
        ap.error("liuyao 需要 --yao")
    lines = liuyao_mod.parse_inputs(args.yao)
    if len(lines) != 6:
        ap.error(f"--yao 需要 6 个爻，实得 {len(lines)} 个")
    if args.datetime:
        dt = parse_time(args.datetime)
        from datetime import datetime as _dt
        d = _dt(dt["year"], dt["month"], dt["day"], dt["hour"], dt["minute"])
    else:
        from datetime import datetime as _dt
        d = _dt.now()
    gz = ganzhi_of_datetime(d)
    chart = liuyao_mod.build_chart(lines, gz, gz["xunkong"])
    chart["起卦时间"] = d.strftime("%Y-%m-%d %H:%M")
    chart["干支"] = {"year": gz["year"], "month": gz["month"],
                     "day": gz["day"], "time": gz["time"]}
    chart["农历"] = gz["lunar"]
    # 取用神与应期一律交给 judge.py：那里有 ch11 的六步次序与 ch40 的四档日月转换。
    # 这里若再算一遍，两处结论会打架（旧的「舍衰取旺」打分与新的「有异取异」并不相同）。

    if args.text:
        print(render_liuyao_text(chart, args.question))
    else:
        print(json.dumps(chart, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
