# -*- coding: utf-8 -*-
"""分层批量入库：28 本 GB 550xx 通用规范 → 主库(房建相关) + 扩展库 kb/library/(市政类)"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\claude code\规范\规范.docx\规范.docx")
AGENT = Path(r"D:\claude code\DeepSeek-Balance-Whale-Widget-main\agent")
LIB = AGENT / "kb" / "library"
MAIN_KB = AGENT / "kb" / "jianli_kb.txt"

# 编号 -> (全称, 主题标签)
MAIN = {
    "55015": ("建筑节能与可再生能源利用通用规范", "建筑节能/可再生能源/围护结构/保温"),
    "55016": ("建筑环境通用规范", "室内环境/声环境/采光照明/热工"),
    "55019": ("建筑与市政工程无障碍通用规范", "无障碍/坡道/盲道/扶手"),
    "55020": ("建筑给水排水与节水通用规范", "给水排水/节水/管道/水质"),
    "55021": ("既有建筑鉴定与加固通用规范", "既有建筑/鉴定/加固/结构安全"),
    "55022": ("既有建筑维护与改造通用规范", "既有建筑/维护/改造/装饰装修"),
    "55023": ("施工脚手架通用规范", "脚手架/模板支撑/临边防护/高处作业"),
    "55024": ("建筑电气与智能化通用规范", "建筑电气/智能化/防雷接地/配电"),
    "55025": ("宿舍、旅馆建筑项目规范", "宿舍/旅馆/居住建筑/卫生间"),
    "55029": ("安全防范工程通用规范", "安全防范/视频监控/入侵报警/门禁"),
    "55030": ("建筑与市政工程防水通用规范", "防水/渗漏/防水材料/节点构造"),
    "55031": ("民用建筑通用规范", "民用建筑/层高/楼梯/门窗/屋面"),
    "55032": ("建筑与市政工程施工质量控制通用规范", "施工质量控制/验收/检验批/材料进场"),
    "55034": ("建筑与市政施工现场安全卫生与职业健康通用规范",
              "施工现场安全/职业健康/高处坠落防护/临时用电/消防安全"),
    "55036": ("消防设施通用规范", "消防设施/消火栓/自动喷水/火灾报警/防排烟"),
    "55037": ("建筑防火通用规范", "建筑防火/防火分区/安全疏散/耐火极限"),
    "55038": ("住宅项目规范", "住宅项目/套内空间/电梯/隔声"),
}

EXT = {
    "55011": ("城市道路交通工程项目规范", "城市道路/交通工程/路基路面/交通设施"),
    "55012": ("生活垃圾处理处置工程项目规范", "生活垃圾/处理处置/环卫设施"),
    "55013": ("市容环卫工程项目规范", "市容环卫/公共厕所/清扫保洁"),
    "55014": ("园林绿化工程项目规范", "园林绿化/种植/绿地/园路"),
    "55017": ("工程勘察通用规范", "工程勘察/岩土/钻探取样/原位测试"),
    "55018": ("工程测量通用规范", "工程测量/控制测量/变形监测"),
    "55026": ("城市给水工程项目规范", "城市给水/净水厂/输配水"),
    "55027": ("城乡排水工程项目规范", "城乡排水/管渠/污水处理"),
    "55028": ("特殊设施工程项目规范", "特殊设施/地下空间/人防"),
    "55033": ("城市轨道交通工程项目规范", "城市轨道交通/地铁/区间隧道"),
    "55035": ("城乡历史文化保护利用项目规范", "历史文化保护/历史建筑/传统村落"),
}


def find_book(code4):
    for p in ROOT.glob("*"):
        if p.is_file() and code4 in p.name and p.suffix.lower() in (".docx", ".doc"):
            return p
    return None


def strip_gb55011_from_main():
    """把主库里已有的 GB 55011 条目摘掉（它要搬到扩展库）"""
    txt = MAIN_KB.read_text(encoding="utf-8-sig")
    header, _, rest = txt.partition("【检索片段】")
    blocks = ["【检索片段】" + b for b in rest.split("【检索片段】") if b.strip()]
    keep = [b for b in blocks if "GB 55011" not in b.splitlines()[0]]
    removed = len(blocks) - len(keep)
    MAIN_KB.write_text(header.rstrip() + "\n\n" + "\n\n".join(keep) + "\n",
                       encoding="utf-8", newline="\n")
    return removed


def run_ingest(path, source, code, tags, kb):
    cmd = [sys.executable, str(AGENT / "kb_ingest.py"), "--file", str(path),
           "--source", source, "--code", code, "--tags", tags,
           "--kb", str(kb), "--yes", "--force"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    tail = [l for l in (r.stdout or "").strip().splitlines() if l.strip()]
    line = tail[-1] if tail else (r.stderr or "")[:70]
    return r.returncode, line


def code_from_content(path, code4):
    """从文档内容里取规范编号与年份（找不到就用不带年份的编号）"""
    sys.path.insert(0, str(AGENT))
    import kb_ingest as K
    import contextlib, io
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            t = K.normalize_text(K.extract_docx(path))
    except Exception:
        return "GB %s" % code4
    m = re.search(r"GB\s*/?\s*T?\s*%s\s*[—\-–]\s*((?:19|20)\d{2})" % code4, t)
    if m:
        return "GB %s-%s" % (code4, m.group(1))
    m2 = re.search(r"GB\s*/?\s*T?\s*(%s)" % code4, t)
    return "GB %s" % (m2.group(1) if m2 else code4)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    LIB.mkdir(parents=True, exist_ok=True)

    removed = strip_gb55011_from_main()
    print("① 主库摘除 GB 55011 旧条目：%d 条（将改入扩展库）\n" % removed)

    print("② 主库入库（房建监理相关 %d 本）" % len(MAIN))
    for code4, (name, tags) in MAIN.items():
        p = find_book(code4)
        if not p:
            print("   [跳过] 未找到 GB%s 文件" % code4); continue
        code = code_from_content(p, code4)
        rc, line = run_ingest(p, name, code, tags, MAIN_KB)
        print("   %-8s %-34s %s" % ("GB" + code4, name[:32], line))

    print("\n③ 扩展库入库（市政/勘察类 %d 本，每本一个文件）" % len(EXT))
    for code4, (name, tags) in EXT.items():
        p = find_book(code4)
        if not p:
            print("   [跳过] 未找到 GB%s 文件" % code4); continue
        code = code_from_content(p, code4)
        target = LIB / ("GB%s %s.txt" % (code4, name))
        rc, line = run_ingest(p, name, code, tags, target)
        print("   %-8s %-34s %s" % ("GB" + code4, name[:32], line))


if __name__ == "__main__":
    main()
