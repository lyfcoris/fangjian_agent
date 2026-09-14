# -*- coding: utf-8 -*-
"""
kb_ingest.py —— 规范条文入库小工具（扩充 kb/jianli_kb.txt）

三种输入源（任选其一）：
    python kb_ingest.py --pdf  "某规范(文本版).pdf"      # 提取文字（需 pypdf）
    python kb_ingest.py --file "摘录.txt"                 # 已整理好的文本文件
    python kb_ingest.py --text "8.2.1 后浇带…（单段/整段）"

行为：
    1) 读取/提取文字；
    2) 自动按"条文号"（如 8.2.1）切分，一条一段；未识别到条文号时整段作为一条；
    3) 拼接规范名/编号，生成【检索片段】条目（含主题标签，可给可不给）；
    4) 与库内已有条目查重（按正文开头 40 字），只追加新内容；
    5) UTF-8 写回，不破坏现有条目。

常用参数：
    --source "混凝土结构工程施工质量验收规范"   规范全称（不带《》）
    --code   "GB 50204-2015"                    编号（带不带年份均可）
    --tags   "后浇带 渗漏 / 混凝土"              默认主题标签（/、空格、顿号均可分隔）
    --kb     库文件路径（默认自动找 kb/jianli_kb.txt）
    --yes    跳过确认直接写入        --dry-run 只预览不写
不带 --source/--code/--tags 时会报错提示所需参数；在真实终端里可加
--interactive 让工具逐项提问填写。

说明：仅支持"文字层"PDF；扫描版请先 OCR 或另存为文本再 --file 喂入。
"""

import argparse
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 复用检索技能里的库解析器做查重（同一套契约，避免两套解析规则）
_SKILLS = Path(__file__).resolve().parent / "skills"
if str(_SKILLS) not in sys.path:
    sys.path.insert(0, str(_SKILLS))
from jianli_retrieve import parse_entries  # noqa: E402

DEFAULT_KB = Path(__file__).resolve().parent / "kb" / "jianli_kb.txt"

# 条文号行首：8.2.1 或 8.2.1 后接标题/正文
DOTTED = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,3})(?:\s|　|$)(.*)$")
# 章节标题行（如 "3  安全管理"、"3.1  一般规定"）：短且不以句末标点结尾
HEADING_LIKE = re.compile(r"^\d{1,2}(?:\.\d{1,2})?\s+\S{1,20}$")


# ---------- 1. 输入提取 ----------

def extract_pdf(path, force=False):
    """提取 PDF 文字并做可用性体检。
    优先 PyMuPDF（对字体映射异常的 PDF 兼容更好），退回 pypdf。
    疑似扫描件/乱码时直接中止（除非 --force），并给出 OCR / 换版本指引。"""
    text, engine, pages, img_pages = None, "", 0, 0

    try:
        import pymupdf
        doc = pymupdf.open(str(path))
        pages = doc.page_count
        img_pages = sum(1 for p in doc if len(p.get_images()) > 0)
        text = "\n".join(p.get_text() for p in doc)
        engine = "PyMuPDF"
    except Exception:
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            pages = len(reader.pages)
            img_pages = sum(1 for pg in reader.pages
                            if getattr(pg, "images", []) and len(pg.images) > 0)
            text = "\n".join((pg.extract_text() or "") for pg in reader.pages)
            engine = "pypdf"
        except ImportError:
            sys.exit("[kb_ingest] 需要 PDF 解析库，先运行一次：\n"
                     "   pip install pymupdf      （推荐，兼容性更好）\n"
                     "   pip install pypdf        （备选）\n"
                     "不想装库就用 --file / --text 直接喂文字。")

    text = text or ""
    n_chars = len(text.strip())
    n_clause = len(re.findall(r"(?m)^\s*\d{1,2}(?:\.\d{1,2}){1,3}\s", text))
    print("[kb_ingest] PDF 提取：引擎 %s｜页数 %d｜字符 %d｜识别到条文号 %d 个"
          % (engine, pages, n_chars, n_clause))
    if pages and img_pages / pages >= 0.8:
        print("[kb_ingest] 页数中有 %d/%d 页含图片（接近满页）" % (img_pages, pages))

    bad = (n_chars < 500) or (n_clause == 0)
    if bad and not force:
        sys.exit(
            "[kb_ingest] 已中止：这份 PDF 提取不到可用文字（疑似**扫描件**或字体映射异常）。\n"
            "  按下面三种办法之一处理，再用对应命令入库：\n"
            "  ① 换文字版：从标准全文公开系统网页直接复制条文，存 txt 后\n"
            "     python kb_ingest.py --file \"摘录.txt\" --source \"规范全称\" --code \"GB XXXXX-XXXX\" --tags \"关键词\"\n"
            "  ② OCR 这份扫描件：用 WPS / Adobe Acrobat / 白描等做文字识别，导出 txt 后按 ① 入库；\n"
            "     （OCR 会有错字，入库后务必抽检条文号与数字）\n"
            "  ③ 人工摘录：只为演示摘 20~30 条最相关的条文即可，同样走 ①。\n"
            "  若确认提取结果可用、坚持继续，加 --force。")
    return text


def extract_docx(path):
    """提取 .docx 文字（段落 + 表格），用于喂入规范 Word 版。"""
    try:
        from docx import Document
    except ImportError:
        sys.exit("[kb_ingest] 需要 python-docx：pip install python-docx")
    d = Document(str(path))
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            parts.append("  ".join(c.text.strip() for c in row.cells))
    text = "\n".join(parts)
    print("[kb_ingest] DOCX 提取：段落 %d｜字符 %d" % (len(d.paragraphs), len(text.strip())))
    return text


def normalize_text(text):
    """清理排版空格：去掉汉字之间的空格（'安 全' → '安全'），保留数字/单位之间的空格。
    PDF/Word 的"折行 + 词间空格"会把检索词拆散，必须先归一，否则匹配不到。"""
    text = text.replace("\u3000", " ")                                   # 全角空格
    text = re.sub(r"(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"[ \t]{3,}", "  ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def split_clauses(text):
    """按行首条文号（含点，如 8.2.1）切段；无条文号时整段作为一条。"""
    clauses, cur = [], None
    for raw in text.splitlines():
        s = raw.strip()
        m = DOTTED.match(s)
        if m:
            if cur is not None:
                clauses.append(cur)
            cur = {"num": m.group(1),
                   "body_lines": [m.group(2).strip()] if m.group(2).strip() else []}
            continue
        if cur is not None and s:
            # 章节标题（"3 安全管理" / "3.1 一般规定"）不并入条文正文
            if HEADING_LIKE.match(s) and not s.endswith(("。", "；", "：", "，", ".", ";", ":")):
                continue
            cur["body_lines"].append(s)
    if cur is not None:
        clauses.append(cur)

    out = []
    for c in clauses:
        body = "\n".join(c["body_lines"]).strip()
        body = re.sub(r"\n{3,}", "\n\n", body)
        if body:
            out.append({"num": c["num"], "body": body})
    return out


# ---------- 2. 元信息收集 ----------

def split_tags(s):
    return [t for t in re.split(r"[/、，,;；\s]+", s or "") if t]


def _prompt(label):
    """交互提问：任何异常（非交互/管道关闭）都按空输入处理，绝不崩溃。"""
    try:
        return input(label).strip()
    except EOFError:
        return ""


def ask_missing(args, need_num_prompt):
    """规范名/编号/标签缺省时的取值：
    - 默认（非交互）：只用命令行参数，缺 --source 时报错提示；
    - --interactive：在真实终端里逐项提问（仍需 --source，可追问编号/标签/条文号）。"""
    name = args.source or ""
    code = args.code or ""
    tags = split_tags(args.tags)
    num = args.num or ""

    interactive = args.interactive and sys.stdin.isatty()
    if interactive:
        if not name:
            name = _prompt("规范全称（不含《》，如 混凝土结构工程施工质量验收规范）：")
        if not code:
            code = _prompt("规范编号（如 GB 50204-2015，可回车跳过）：")
        if not tags:
            tags = split_tags(_prompt("默认主题标签（/ 分隔，可回车跳过）："))
        if need_num_prompt and not num:
            num = _prompt("本条条文号（可回车跳过）：")

    if not name:
        raise SystemExit("[kb_ingest] 缺少规范全称，请在命令里加 --source \"规范全称\"；\n"
                         "  可选补充：--code \"GB XXXXX-XXXX\" / --tags \"词A 词B\" / --num \"8.2.1\"；\n"
                         "  或在真实终端加 --interactive 逐项填写。")
    return name, code, tags, num


def build_entries(name, code, tags, clauses, single_num=""):
    entries = []
    for c in clauses:
        num = c["num"] or single_num
        head = "【检索片段】《%s》%s" % (name, code) if code else "【检索片段】《%s》" % name
        if num:
            head += " 第%s条" % num
        label = "主题标签：%s" % (" / ".join(tags)) if tags else ""
        entries.append({"text": (head + ("\n" + label if label else "") + "\n" + c["body"]).strip(),
                        "key": re.sub(r"\s+", "", c["body"])[:40]})
    return entries


# ---------- 2.5 入库质量闸门（防止灌入表格碎片与乱码） ----------

FULLWIDTH_ALNUM = re.compile(r"[\uff10-\uff19\uff21-\uff3a\uff41-\uff5a]")
RADICAL_BLOCK = re.compile(r"[\u2e80-\u2fdf]")   # 康熙部首等：PDF 字体映射错位的典型产物


def quality_flags(body):
    """返回单条正文的疑似问题标签（空列表 = 通过）"""
    flags = []
    if len(re.sub(r"\s+", "", body)) < 8:
        flags.append("过短/表格碎片")
    if len(FULLWIDTH_ALNUM.findall(body)) >= 2 or RADICAL_BLOCK.search(body):
        flags.append("疑似乱码")
    cjk = len(re.findall(r"[\u4e00-\u9fff]", body))
    if body and cjk / max(len(body), 1) < 0.5:
        flags.append("汉字占比过低")
    return flags


def quality_gate(entries):
    """返回 [(entry, flags)] 列表"""
    out = []
    for e in entries:
        f = quality_flags(e["text"])
        if f:
            out.append((e, f))
    return out


# ---------- 3. 查重 + 写回 ----------

def dedupe(entries, existing_text):
    """与库内既有条目按"正文前 40 字"查重（复用检索技能的解析器）。"""
    seen = {re.sub(r"\s+", "", e["body"])[:40]
            for e in parse_entries(existing_text)}
    added, skipped = [], []
    for e in entries:
        if e["key"] in seen:
            skipped.append(e)
        else:
            seen.add(e["key"])
            added.append(e)
    return added, skipped


def write_kb(path, entries):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = p.read_text(encoding="utf-8-sig").strip() if p.exists() else ""
    if not p.exists():
        header = ("# 房建监理演示 Agent 条文摘录库（由 kb_ingest.py 持续扩充）\n"
                  "# 格式：【检索片段】《规范全称》编号 第X.X.X条\n"
                  "#      主题标签：词A / 词B\n#      正文（条文原文）\n")
        existing = header.rstrip()
    new_text = "\n\n".join(e["text"] for e in entries)
    content = existing + "\n\n" + new_text + "\n"
    # 强制 LF 换行，与库内既有条目保持一致
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    return len(re.findall(r"(?m)^【检索片段】", content))


# ---------- 4. 主流程 ----------

def main():
    ap = argparse.ArgumentParser(description="规范条文入库（kb_ingest）")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf", metavar="PATH", help="文本型 PDF 文件")
    src.add_argument("--file", metavar="PATH", help="文本文件（UTF-8）或 Word 文件（.docx）")
    src.add_argument("--text", metavar="TEXT", help="直接传文字")
    ap.add_argument("--kb", default=str(DEFAULT_KB), help="库文件路径（默认 kb/jianli_kb.txt）")
    ap.add_argument("--source", help="规范全称，如 混凝土结构工程施工质量验收规范")
    ap.add_argument("--code", help="规范编号，如 GB 50204-2015")
    ap.add_argument("--tags", help="默认主题标签（/ 或空格分隔）")
    ap.add_argument("--num", help="未识别到条文号时手工指定本条条文号（如 8.2.1）")
    ap.add_argument("--min-body", type=int, default=8,
                    help="正文最少字数（默认 8），低于此值视为表格碎片并跳过")
    ap.add_argument("--require-keyword", action="append", metavar="词",
                    help="只入库正文含该关键词的条目，可重复指定（如 --require-keyword 验收 --require-keyword 施工）")
    ap.add_argument("--force", action="store_true",
                    help="忽略质量闸门警告，强行写入（碎片/乱码比例过高时使用）")
    ap.add_argument("--interactive", action="store_true",
                    help="缺省信息时在终端逐项提问（默认非交互，只用命令行参数）")
    ap.add_argument("--yes", action="store_true", help="跳过确认")
    ap.add_argument("--dry-run", action="store_true", help="只预览不写入")
    args = ap.parse_args()

    # 取原文
    if args.pdf:
        text = extract_pdf(args.pdf, force=args.force)
    elif args.file:
        fp = Path(args.file)
        text = extract_docx(fp) if fp.suffix.lower() == ".docx" else fp.read_text(encoding="utf-8-sig")
    else:
        text = args.text
    text = normalize_text((text or "").strip())
    if not text:
        sys.exit("[kb_ingest] 输入为空，未做任何修改。")

    clauses = split_clauses(text)
    if not clauses:
        # 未识别到任何条文号：把整段作为一条，条文号可留空或 --num 手工指定
        clauses = [{"num": None, "body": text}]

    # 质量闸门 1：过短的表格碎片直接跳过
    kept_clauses, dropped_short = [], []
    for c in clauses:
        if len(re.sub(r"\s+", "", c["body"])) >= args.min_body:
            kept_clauses.append(c)
        else:
            dropped_short.append(c)
    clauses = kept_clauses
    total_clauses = len(dropped_short) + len(clauses)
    if dropped_short and total_clauses and len(dropped_short) / total_clauses >= 0.5:
        print("警告：过短碎片占 %.0f%%（%d/%d），该 PDF 版式零散/表格居多，"
              "建议换文字层清楚的版本，或先另存为文本再入库。"
              % (100.0 * len(dropped_short) / total_clauses,
                 len(dropped_short), total_clauses))
    if not clauses:
        sys.exit("[kb_ingest] 全部条文正文都少于 %d 字（疑似 PDF 表格碎片），未做任何修改。\n"
                 "  确认要入库请加 --min-body 0。" % args.min_body)

    need_num_prompt = len(clauses) == 1 and clauses[0]["num"] is None
    name, code, tags, single_num = ask_missing(args, need_num_prompt)
    entries = build_entries(name, code, tags, clauses, single_num)

    # 质量闸门 2：关键词白名单（可选，只收与监理主题相关的条文）
    dropped_kw = 0
    if args.require_keyword:
        kept = [e for e in entries if any(k in e["text"] for k in args.require_keyword)]
        dropped_kw = len(entries) - len(kept)
        entries = kept
    if not entries:
        sys.exit("[kb_ingest] 没有条目通过 --require-keyword 过滤，未做任何修改。")

    # 质量闸门 3：乱码 / 汉字占比异常检测
    bad = quality_gate(entries)
    if dropped_short:
        print("已跳过 %d 条过短碎片（正文 <%d 字）" % (len(dropped_short), args.min_body))
    if dropped_kw:
        print("已跳过 %d 条不含关键词的条目（--require-keyword）" % dropped_kw)
    if bad:
        print("注意：疑似问题条目 %d / %d 条" % (len(bad), len(entries)))
        for e, f in bad[:3]:
            print("   - [%s] %s" % ("、".join(f), e["text"][:60].replace("\n", " ")))
        ratio = len(bad) / len(entries)
        over = (len(bad) >= 1 and ratio >= 0.5) or (len(bad) >= 3 and ratio >= 0.3)
        if not args.force and over:
            sys.exit("[kb_ingest] 已中止：疑似碎片/乱码比例过高（%.0f%%），未写入任何内容。\n"
                     "  建议：① 换文字层清楚的规范版本，或先 OCR/另存为文本；\n"
                     "        ② 加 --min-body 提高字数门槛、--require-keyword 只收相关条文；\n"
                     "        ③ 若确认无误确需入库，加 --force 强行写入。" % (ratio * 100))

    # 预览
    print("准备入库 %d 条：" % len(entries))
    for i, e in enumerate(entries[:3], 1):
        first_line = e["text"].splitlines()[0]
        print("  %d) %s …%s" % (i, first_line, "…" if len(e["text"]) > 90 else ""))
    if len(entries) > 3:
        print("  …（其余 %d 条略）" % (len(entries) - 3))
    if args.dry_run:
        print("[dry-run] 以上为预览，未写入。")
        return

    # 确认
    if not args.yes:
        if not sys.stdin.isatty():
            sys.exit("[kb_ingest] 非交互环境请加 --yes 直接写入（或先 --dry-run 预览）。")
        if input("确认写入 %d 条？(y/N) " % len(entries)).strip().lower() != "y":
            print("已取消。")
            return

    existing_text = Path(args.kb).read_text(encoding="utf-8-sig") if Path(args.kb).exists() else ""
    added, skipped = dedupe(entries, existing_text)
    if added:
        total = write_kb(args.kb, added)
        print("已追加 %d 条（查重跳过 %d 条）。库内现有条目：%d" % (len(added), len(skipped), total))
    else:
        print("全部 %d 条与库内重复，未写入。" % len(entries))


if __name__ == "__main__":
    main()
