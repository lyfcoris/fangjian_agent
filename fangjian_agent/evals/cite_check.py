# -*- coding: utf-8 -*-
"""
cite_check.py —— 引用回查校验器（防幻觉的"第三道防线"，程序化验证）

做什么：拿一段 Agent 输出的三段式整改意见，做三件事：
  1. 抽取其中所有"GB xxxx(-年份) 第x.x.x条"式引用；
  2. 逐条到知识库（主库 + 扩展库）里回查，验证该"规范编号+条文号"是否真实存在；
  3. 校验三段格式完整性。

结果：输出 引用数 / 库内命中数 / 疑似编造数 / 三段完整度，
      并给出可写进答辩材料的"引用准确率"。

用法：
    python evals/cite_check.py "【问题归纳】……【规范依据】……【监理整改意见】……"
    python evals/cite_check.py --file answer.txt
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "skills"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from jianli_retrieve import parse_entries  # noqa: E402

CITE_RE = re.compile(r"GB\s*/?\s*T?\s*(55\d{3})(?:\s*[-—–−]\s*(\d{4}))?\s*第\s*(\d+(?:\.\d+)*)\s*条")
HEADINGS = ["【问题归纳】", "【规范依据】", "【监理整改意见】"]


def build_index(lib_paths):
    """从库中抽取 (编号, 条文号) 集合；编号统一去掉年份后再比对（年份只作参考）。"""
    index = set()
    for p in lib_paths:
        if not p.is_file():
            continue
        for e in parse_entries(p.read_text(encoding="utf-8-sig")):
            m = re.search(r"GB\s*/?\s*T?\s*(55\d{3})(?:\s*[-—–−]\s*\d{4})?\s*第\s*(\d+(?:\.\d+)*)\s*条", e["source"])
            if m:
                index.add((m.group(1), m.group(2)))
    return index


def check(text):
    cites = CITE_RE.findall(text)
    paths = [ROOT / "kb" / "jianli_kb.txt"]
    lib = ROOT / "kb" / "library"
    if lib.is_dir():
        paths.extend(lib.glob("*.txt"))
    index = build_index(paths)
    hits, miss = [], []
    for code, year, clause in cites:
        if (code, clause) in index:
            hits.append((code, year, clause))
        else:
            miss.append((code, year, clause))
    fmt_ok = all(h in text for h in HEADINGS)
    return {
        "total_cites": len(cites),
        "hit": len(hits),
        "miss": len(miss),
        "miss_list": miss,
        "format_ok": fmt_ok,
        "accuracy": (len(hits) / len(cites)) if cites else 1.0,
    }


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = sys.argv[1:]
    if args and args[0] == "--file":
        text = Path(args[1]).read_text(encoding="utf-8")
    elif args:
        text = " ".join(args)
    else:
        print("用法：python evals/cite_check.py <Agent输出文本>  或  --file answer.txt")
        sys.exit(0)

    r = check(text)
    print("=" * 58)
    print("引用回查校验")
    print("=" * 58)
    print("引用总数      :", r["total_cites"])
    print("库内命中      :", r["hit"])
    print("疑似编造/库外 :", r["miss"],
          ("（" + "; ".join("GB%s-%s 第%s条" % (c, y or "?", n) for c, y, n in r["miss_list"]) + "）") if r["miss_list"] else "")
    print("引用准确率    : %.0f%%" % (r["accuracy"] * 100))
    print("三段格式完整  :", "是 ✅" if r["format_ok"] else "否 ❌（缺少：" + "、".join(h for h in HEADINGS if h not in text) + "）")
    print("-" * 58)
    verdict = "✅ 通过：所有引用条文均可在知识库查证" if not r["miss"] and r["format_ok"] else "❌ 未通过：存在库外引用或三段格式缺失"
    print(verdict)
    sys.exit(0 if (not r["miss"] and r["format_ok"]) else 1)


if __name__ == "__main__":
    main()
