#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
八字排盘命令行入口

示例：
  # 公历 + 城市（自动查经度做真太阳时校正）
  python paipan.py --date "1935-04-25 07:30" --gender male --city 哈尔滨

  # 直接给经度
  python paipan.py --date "1990-06-15 10:00" --gender female --lon 104.07

  # 农历（闰月加 --leap）
  python paipan.py --lunar "1990-03-15 10:00" --gender female --city 上海

  # 不校正真太阳时（某些软件口径）
  python paipan.py --date "1990-06-15 10:00" --gender female --no-true-solar

  # 晚子时按"子时换日"（日柱算次日）
  python paipan.py --date "2024-02-10 23:30" --gender male --school sect1

  # JSON 输出（给程序用）
  python paipan.py --date "1990-06-15 10:00" --gender male --json

  # 附带流年
  python paipan.py --date "1990-06-15 10:00" --gender male --liunian 2020 2030
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from bazi import paipan, render  # noqa: E402


def parse_dt(s, calendar="solar"):
    s = s.strip().replace("/", "-").replace("年", "-").replace("月", "-").replace("日", " ")
    s = s.replace("T", " ")
    # 允许 "1990-06-15" 只有日期（默认 12:00 并提示）
    if " " not in s:
        for sep in ("-",):
            parts = s.split(sep)
            if len(parts) == 3:
                return int(parts[0]), int(parts[1]), int(parts[2]), 12, 0, False
        raise ValueError(f"无法解析时间：{s}")
    datepart, timepart = s.split(" ", 1)
    y, m, d = [int(x) for x in datepart.split("-")]
    tp = timepart.strip().replace(":", ".").replace("：", ".")
    if "." not in tp:
        tp = tp + ".00"
    hh, mm = tp.split(".")[:2]
    h, mi = int(hh), int(mm)
    has_time = True
    return y, m, d, h, mi, has_time


GENDER_MAP = {"male": 1, "m": 1, "男": 1, "male ": 1, "乾": 1, "乾造": 1,
              "female": 0, "f": 0, "女": 0, "坤": 0, "坤造": 0}


def main():
    ap = argparse.ArgumentParser(description="八字排盘（陆致极体系）")
    ap.add_argument("--date", help='公历生日，如 "1990-06-15 10:00"')
    ap.add_argument("--lunar", help='农历生日，如 "1990-03-15 10:00"')
    ap.add_argument("--leap", action="store_true", help="农历闰月")
    ap.add_argument("--gender", required=True, help="male/female 或 男/女/乾/坤")
    ap.add_argument("--city", help="出生城市（自动查经度）")
    ap.add_argument("--lon", type=float, help="出生地经度，东经为正")
    ap.add_argument("--no-true-solar", action="store_true", help="不做真太阳时校正")
    ap.add_argument("--school", default="sect2", choices=["sect1", "sect2"],
                    help="sect2(默认)晚子时日柱算当日；sect1 算次日")
    ap.add_argument("--dayun", type=int, default=10, help="输出几步大运，默认10")
    ap.add_argument("--liunian", nargs=2, type=int, metavar=("起", "止"),
                    help="附带流年范围，如 --liunian 2020 2030")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if not args.date and not args.lunar:
        ap.error("必须给 --date 或 --lunar")

    gkey = args.gender.strip().lower()
    if gkey not in GENDER_MAP:
        ap.error(f"性别无法识别：{args.gender}")
    gender = GENDER_MAP[gkey]

    raw = args.date or args.lunar
    calendar = "solar" if args.date else "lunar"
    y, m, d, h, mi, has_time = parse_dt(raw, calendar)

    warning_prefix = []
    if not has_time:
        warning_prefix.append("未提供出生时刻，按 12:00 午时试排，请补充准确时间后重排。")

    r = paipan(y, m, d, h, mi, gender=gender, city=args.city, longitude=args.lon,
               calendar=calendar, use_true_solar=not args.no_true_solar,
               school=args.school, dayun_count=args.dayun,
               liunian_range=tuple(args.liunian) if args.liunian else None,
               is_leap_month=args.leap)
    if warning_prefix:
        r["warnings"] = warning_prefix + r["warnings"]

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(render(r))


if __name__ == "__main__":
    main()
