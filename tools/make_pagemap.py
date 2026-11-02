#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描你自己那份原书文本，生成「章节 → 页码」映射。

仓库里不给页码：同一本书的印刷版、扫描版、不同 PDF 软件导出的页码能差几十页，
写死页码只会骗人。这个脚本在本地跑，只吃你自己的文件，不上传任何内容。

用法：
    python make_pagemap.py 我的书.txt                  # 输出 pagemap.json
    python make_pagemap.py 我的书.txt -o bazi-map.json
    python make_pagemap.py 我的书.txt --book 八字命理学基础教程

文本怎么来：
    PDF 用任意工具导出成 txt 即可。多数 PDF 提取工具会在每页之间插入换页符 \\f，
    脚本按 \\f 分页；没有换页符时会把整份当成一页，页码就没意义了，建议先转好。
"""
import argparse
import json
import re
import sys
from pathlib import Path

CN = "一二三四五六七八九十百"

# 章标题：第X章 后面跟标题，最长 40 字，遇到标点或换行停下
PAT = re.compile(rf"第[{CN}\d]+章[\s　]?([^\n，。；！？]{{0,40}})")


def scan(path: Path):
    raw = path.read_text(encoding="utf-8", errors="ignore")
    pages = raw.split("\f")
    if len(pages) == 1:
        print("⚠ 没发现换页符（\\f），整份按一页处理，页码不可用。", file=sys.stderr)
        print("  建议先用 PDF 工具导出成带分页的文本。", file=sys.stderr)
    chapters, seen = [], set()
    for no, page in enumerate(pages, 1):
        for m in PAT.finditer(page):
            title = m.group(0).strip()
            title = re.sub(r"\s{2,}", " ", title)
            if title not in seen:
                seen.add(title)
                chapters.append({"title": title, "page": no})
    return {"source": path.name, "pages": len(pages), "chapters": chapters}


def main():
    ap = argparse.ArgumentParser(description="生成原书章节页码映射")
    ap.add_argument("textfile", help="你自己的书导出的 txt")
    ap.add_argument("-o", "--out", default="pagemap.json", help="输出文件名")
    ap.add_argument("--book", default="", help="书名，写进文件名方便区分（可空）")
    args = ap.parse_args()

    src = Path(args.textfile)
    if not src.exists():
        sys.exit(f"找不到文件：{src}")

    data = scan(src)
    data["book"] = args.book
    Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    n = len(data["chapters"])
    print(f"扫到 {data['pages']} 页、{n} 个章节标题 -> {args.out}")
    for c in data["chapters"][:8]:
        print(f"  p{c['page']:<4} {c['title']}")
    if n > 8:
        print(f"  …… 还有 {n - 8} 条")
    if n == 0:
        print("⚠ 一个章节标题都没认出来。你的文本可能是繁体、或章节标题用了别的写法。", file=sys.stderr)
        print("  可以打开输出文件手动补几条，格式是 {\"title\": \"第三章 结构分析\", \"page\": 50}。", file=sys.stderr)


if __name__ == "__main__":
    main()
