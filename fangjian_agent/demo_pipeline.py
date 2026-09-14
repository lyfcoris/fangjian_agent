# -*- coding: utf-8 -*-
"""
demo_pipeline.py —— 房建监理演示 Agent：本地链路自检脚本（无需 LLM / API）

验证三件事：
  1. 检索 Skill：5 个土建演示用例是否命中预期主题条目；
  2. 解析 Skill：BIMFACE 模拟 JSON 能否解析成结构化碰撞块；
  3. 消息组装：生成可直接粘贴给 DSH Agent 的输入样例（含碰撞场景）。

运行：python demo_pipeline.py
退出码：全部通过为 0，任一失败为 1。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in (ROOT, ROOT / "skills", ROOT / "inputs"):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

from jianli_retrieve import retrieve, parse_entries
from bimface_parse import parse_bimface, format_results
from demo_cases import CASES


def main():
    fails = 0

    # ---------- 环节 1：土建 5 用例检索命中自检 ----------
    print("=" * 66)
    print("环节1：土建 5 用例检索自检（知识库 kb/jianli_kb.txt）")
    print("=" * 66)
    for case in CASES:
        out = retrieve(description=case["description"], top_k=3,
                       include_debug=True)
        entries = parse_entries(out)
        joined = "\n".join(
            e["source"] + " " + " ".join(e["labels"]) + " " + e["body"]
            for e in entries)
        missed = [t for t in case["expect"] if t not in joined]
        if missed:
            fails += 1
            status = "FAIL 缺词: " + "、".join(missed)
        else:
            status = "PASS"
        print("\n[%s] %s" % (status, case["id"]))
        print("  输入：%s..." % case["description"][:30])
        for e in entries[:2]:
            print("  - %s | 标签:%s"
                  % (e["source"][:26], "/".join(e["labels"])))

    # ---------- 环节 2：BIMFACE 模拟 JSON 解析自检 ----------
    print("\n" + "=" * 66)
    print("环节2：BIMFACE 碰撞 JSON 解析（inputs/bimface_sample.json）")
    print("=" * 66)
    try:
        items = parse_bimface(str(ROOT / "inputs" / "bimface_sample.json"))
        print(format_results(items))
        if len(items) != 2:
            fails += 1
            print("[FAIL] 期望解析出 2 条碰撞，实际 %d 条" % len(items))
        else:
            print("\n[PASS] 解析出 2 条碰撞，编号：%s"
                  % "、".join(it["id"] for it in items))
    except Exception as exc:  # noqa: BLE001 —— 自检脚本允许宽捕获并报错
        fails += 1
        print("[FAIL] 解析异常：%s" % exc)
        items = []

    # ---------- 环节 3：组装消息示例 ----------
    print("\n" + "=" * 66)
    print("环节3：组装好的 Agent 输入样例（可直接粘贴到 DSH Agent 对话）")
    print("=" * 66)

    # 3a. 土建文本输入场景
    c1 = CASES[0]
    frags = retrieve(description=c1["description"], top_k=2,
                     include_debug=False)
    print("\n----- 样例A：土建隐患文本输入 -----")
    print("[现场输入]\n%s" % c1["description"])
    print("\n[知识库检索片段（粘贴进消息即可）]\n%s" % frags)

    # 3b. BIMFACE 碰撞输入场景
    if items:
        frags2 = retrieve(description=items[0]["desc"], top_k=2,
                          include_debug=False)
        print("\n----- 样例B：BIMFACE 碰撞结构化输入 -----")
        print("[碰撞解析结果（由 bimface_parse 生成）]")
        print(format_results([items[0]]))
        print("\n[知识库检索片段]\n%s" % frags2)

    # ---------- 汇总 ----------
    print("\n" + "=" * 66)
    if fails:
        print("自检结果：%d 项未通过，见上方 FAIL 行。" % fails)
        sys.exit(1)
    print("自检结果：全部通过 ✅  "
          "检索链路、BIMFACE 解析链路、消息组装均正常。")
    print("下一步：在 DSH 新建会话界面的模式chip里选『房建监理模式』预设")
    print("（预设已写入 D:/.dsh/.agent-presets/jianli-supervisor），")
    print("按 README 第二节点选、第三节发消息即可运行。")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
