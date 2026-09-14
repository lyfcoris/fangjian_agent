# -*- coding: utf-8 -*-
"""
jianli_retrieve.py —— 房建监理演示 Agent：条文摘录库本地检索 Skill
纯 Python 标准库，零第三方依赖，适配 DSH 工具沙盒。

职责：在摘录库(kb/jianli_kb.txt)中检索与输入描述最相关的若干条，
并把命中条目整理成 system_prompt.md 约定的【检索片段】格式文本，
供 Agent 直接引用（贴入消息 或 作为工具结果返回）。

用法：
    from jianli_retrieve import retrieve
    print(retrieve("地下车库顶板后浇带两侧渗漏水，部位：车库顶板后浇带。"))

直接运行自测：python skills/jianli_retrieve.py
"""

import re
from math import log
from pathlib import Path


def _default_lib_path():
    """智能定位知识库：优先本项目 kb/jianli_kb.txt，其次脚本旁 jianli_kb.txt"""
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / "kb" / "jianli_kb.txt",   # 项目内：skills/../kb/
        here.parent / "jianli_kb.txt",          # 项目根
        here / "jianli_kb.txt",                 # 脚本同目录
        Path("jianli_kb.txt"),                  # 当前工作目录
    ]
    for c in candidates:
        try:
            if c.exists():
                return str(c)
        except OSError:
            continue
    return str(candidates[0])


# ---------- 1. 库文件解析 ----------

def parse_entries(text):
    """把库文本解析为条目列表：[{'source','labels':[...],'body'}]"""
    entries = []
    cur = None
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln or ln.startswith("#"):
            continue                     # 空行与 # 注释自动忽略
        if ln.startswith("【检索片段】"):
            if cur is not None:
                entries.append(cur)
            cur = {"source": ln[len("【检索片段】"):].strip(),
                   "labels": [], "body_lines": []}
        elif cur is None:
            continue                     # 库头部说明文字（首个条目之前）忽略
        else:
            m = re.match(r"^(?:主题)?标签\s*[:：]\s*(.*)$", ln)
            if m:
                cur["labels"].extend(re.split(r"[/、，,；;\s]+", m.group(1).strip()))
            else:
                cur["body_lines"].append(ln)
    if cur is not None:
        entries.append(cur)
    for e in entries:
        e["labels"] = [x for x in e["labels"] if x]
        e["body"] = "\n".join(e["body_lines"]).strip()
    return entries


# ---------- 2. 中文两字词对 ----------

def _cjk_bigrams(s):
    """只保留汉字后切成连续两字词对，如 '后浇带' -> ['后浇','浇带']"""
    seg = re.sub(r"[^\u4e00-\u9fff]", "", s or "")
    return [seg[i:i + 2] for i in range(max(len(seg) - 1, 0))]


def _entry_text(e):
    return " ".join([e["source"], " ".join(e["labels"]), e["body"]])


# ---------- 3. 主检索函数 ----------

def retrieve(description="", keywords="", lib_path=None,
             lib_text=None, top_k=3, min_bigram_hits=2,
             min_ratio=0.45, min_score=5.0, include_debug=False):
    """
    参数：
      description      隐患/问题描述（自由文本）
      keywords         可选，手动指定检索词（空格分隔），并入匹配依据
      lib_path         摘录库文件路径；None 时自动定位 kb/jianli_kb.txt
      lib_text         可选，直接传库内容字符串，绕过文件读取
                       （工具沙盒禁止读文件时的兜底方案）
      top_k            最多返回几条，默认 3
      min_bigram_hits  正文最少命中几个两字词对才入选（标签命中不受此限）
      min_ratio        相对强度过滤：低于"最强命中 45%"的尾部条目丢弃，
                       压制无关噪声（如机电场景误带出土建通用条目）
      min_score        绝对分数下限：低于此分数的弱命中一律判为"未命中"，
                       防止无关输入（如闲聊、合同条款）硬凑出条文
      include_debug    True 时每条前附加匹配度/命中词，便于调参
    返回：可直接粘贴的【检索片段】文本；无命中时返回明确提示。
    """
    # --- 读库（文件 + 内存字符串两级兜底） ---
    if lib_text is None:
        path = lib_path or _default_lib_path()
        try:
            lib_text = Path(path).read_text(encoding="utf-8-sig")
        except OSError as exc:
            return ("[检索Skill] 读取库文件失败：%s\n"
                    "处理：确认 %s 存在且为 UTF-8 文本；"
                    "若工具沙盒禁止读文件，改用 lib_text= 参数直接传入库内容。"
                    % (exc, path))

    entries = parse_entries(lib_text)
    if not entries:
        return "[检索Skill] 库中未解析到任何条目，请检查文件是否为【检索片段】开头格式。"

    # --- 构造匹配依据 ---
    q_text = ((description or "") + "  " + (keywords or "")).strip()
    if not q_text:
        return "[检索Skill] description 与 keywords 均为空，无法检索。"
    qb = list(dict.fromkeys(_cjk_bigrams(q_text)))   # 去重保序

    # IDF 加权：出现在越少条目里的词对区分力越强，
    # 让“后浇带、渗漏”这类特色词压过“施工、质量”这类常见词
    etexts = [_entry_text(e) for e in entries]
    df = {b: sum(1 for t in etexts if b in t) for b in qb}
    idf = {b: log((len(entries) + 1) / (df[b] + 1)) + 1.0 for b in qb}

    # --- 逐条打分：词对命中分 + 主题标签命中加分 ---
    # 标签加分设高权重：让"主题归属正确但表述简练"的条目，
    # 压过靠"构件/缺陷/严重程度"等通用词攒分的无关条目（防噪声）。
    LABEL_BONUS = 6.0
    scored = []
    for idx, e in enumerate(entries):
        et = etexts[idx]
        matched = [b for b in qb if b in et]
        label_hits = [lb for lb in e["labels"] if lb in q_text]
        score = sum(idf[b] for b in matched) + LABEL_BONUS * len(set(label_hits))
        scored.append((score, len(matched), label_hits, e))

    # --- 过滤 + 排序 + 相对强度裁尾 + 绝对分数下限 ---
    passed = [s for s in scored
              if (s[1] >= min_bigram_hits or len(s[2]) > 0) and s[0] >= min_score]
    passed.sort(key=lambda s: (-s[0], -s[1]))

    if not passed:
        note = ("[检索Skill] 未命中：知识库未检索到直接适用的规范条文，"
                "应只给出管理性处置建议。")
        if include_debug:
            cand = sorted(scored, key=lambda s: -s[0])[:3]
            info = " | ".join("%s(%.1f)" % (c[3]["source"][:20], c[0])
                              for c in cand)
            note += "\n[调试] 最接近的三条（未达阈值）：" + info
        return note

    # 尾部弱命中可能属无关噪声（如碰撞查询误带出土建通用条目），
    # 分数低于最强命中 min_ratio 比例的条目直接丢弃
    best_score = passed[0][0]
    kept = [s for s in passed if s[0] >= best_score * min_ratio]
    kept = kept[:top_k] or passed[:1]

    # --- 排版输出（默认即【检索片段】契约格式） ---
    parts = []
    for rank, (score, n_bigram, label_hits, e) in enumerate(kept, 1):
        chunk = "【检索片段】%s\n主题标签：%s\n%s" % (
            e["source"],
            " / ".join(e["labels"]) if e["labels"] else "（无标签）",
            e["body"])
        if include_debug:
            chunk = ("# 命中%d 匹配度=%.1f 词对%d个 标签命中:%s\n%s"
                     % (rank, score, n_bigram,
                        "、".join(label_hits) or "无", chunk))
        parts.append(chunk)
    return "\n\n".join(parts)


# ---------- 4. 命令行自测 ----------

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(retrieve(
        description="地下车库顶板后浇带两侧混凝土接茬处渗漏水，板底潮湿，"
                    "后浇带封闭至今约20天。部位：车库顶板后浇带。",
        top_k=3,
        include_debug=True,
    ))
