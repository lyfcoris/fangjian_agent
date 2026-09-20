# -*- coding: utf-8 -*-
"""
eval_run.py —— 检索质量评测脚本（离线、无需 LLM）

输出四个指标 + 知识库体检：
  1. Hit@1   ：第 1 条命中含期望关键词的比例
  2. Hit@3   ：前 3 条命中含期望关键词的比例
  3. MRR     ：首次出现期望关键词的排名倒数均值
  4. 拒答正确率：无关输入时检索"未命中"（不硬凑条文）的比例
  5. 库体检 ：条目数、重复正文数、缺主题标签数、来源行缺"第X条/编号"数

用法：python evals/eval_run.py          （默认阈值：Hit@3 ≥ 0.8 且 拒答 = 1.0）
退出码：达标 0，未达标 1（便于回归时自动发现退化）
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "skills", ROOT / "evals"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from jianli_retrieve import retrieve, parse_entries, _default_lib_path  # noqa: E402
from eval_cases import POSITIVE, NEGATIVE  # noqa: E402

TOP_K = 3
THRESH_HIT3 = 0.80
THRESH_REFUSE = 1.00


def entries_of(desc, top_k=TOP_K):
    """跑检索并把命中结果解析回条目列表"""
    out = retrieve(description=desc, top_k=top_k, include_debug=False)
    return out, parse_entries(out)


def entry_text(e):
    return e["source"] + " " + " ".join(e["labels"]) + " " + e["body"]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    lib = _default_lib_path()
    print("=" * 68)
    print("检索评测：知识库 %s" % lib)
    print("=" * 68)

    hit1 = hit3 = 0
    rr_sum = 0.0
    details = []
    for c in POSITIVE:
        _, entries = entries_of(c["description"])
        texts = [entry_text(e) for e in entries]
        rank = next((i for i, t in enumerate(texts, 1) if c["expect_top1"] in t), 0)
        ok3 = (any(c["expect_top1"] in t for t in texts)
               and any(c["expect_top3"] in t for t in texts))
        hit1 += 1 if rank == 1 else 0
        hit3 += 1 if ok3 else 0
        rr_sum += (1.0 / rank) if rank else 0.0
        details.append({
            "id": c["id"], "hit@1": rank == 1, "hit@3": ok3, "rank": rank,
            "top1": entries[0]["labels"] if entries else [],
        })
        print("[%s] %s（首个相关条目排名：%s）"
              % ("PASS" if ok3 else "FAIL", c["id"], rank or "无"))

    refused = 0
    for c in NEGATIVE:
        out, entries = entries_of(c["description"])
        is_refuse = (not entries) or out.startswith("[检索Skill] 未命中")
        refused += 1 if is_refuse else 0
        print("[%s] %s（应拒答）" % ("PASS" if is_refuse else "FAIL", c["id"]))

    n_pos, n_neg = len(POSITIVE), len(NEGATIVE)
    m_hit1, m_hit3 = hit1 / n_pos, hit3 / n_pos
    mrr = rr_sum / n_pos
    m_refuse = refused / n_neg

    # ---- 知识库体检 ----
    lib_text = Path(lib).read_text(encoding="utf-8-sig")
    entries = parse_entries(lib_text)
    bodies = [re.sub(r"\s+", "", e["body"]) for e in entries]
    dup = len(bodies) - len(set(bodies))
    no_label = sum(1 for e in entries if not e["labels"])
    no_clause = sum(1 for e in entries
                    if not (re.search(r"第[\d.]+条", e["source"]) or re.search(r"[A-Z]{1,3}\s?\d", e["source"])))

    print("\n" + "-" * 68)
    print("指标：Hit@1 = %.2f   Hit@3 = %.2f   MRR = %.3f   拒答正确率 = %.2f"
          % (m_hit1, m_hit3, mrr, m_refuse))
    print("库体检：条目 %d 条｜重复正文 %d 条｜缺主题标签 %d 条｜来源行缺编号/条文号 %d 条"
          % (len(entries), dup, no_label, no_clause))
    ok = (m_hit3 >= THRESH_HIT3) and (m_refuse >= THRESH_REFUSE)
    print("结论：%s（阈值 Hit@3 ≥ %.2f、拒答 = %.2f）"
          % ("达标 ✅" if ok else "未达标 ❌", THRESH_HIT3, THRESH_REFUSE))

    report = {
        "kb": lib, "entries": len(entries),
        "hit@1": round(m_hit1, 4), "hit@3": round(m_hit3, 4),
        "mrr": round(mrr, 4), "refuse_rate": round(m_refuse, 4),
        "kb_issues": {"duplicate_bodies": dup, "missing_labels": no_label,
                      "missing_clause_no": no_clause},
        "details": details,
    }
    rep_path = ROOT / "evals" / "report.json"
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("报告已写入：%s" % rep_path)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
