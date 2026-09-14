# -*- coding: utf-8 -*-
"""
install.py —— 一键安装「房建监理模式」到本机 DeepSeek Harness（DSH）

它做三件事：
  1) 把 Agent 预设写入  <DSH_HOME>/.agent-presets/jianli-supervisor/
     （优先用本机随附的 standard 预设重建组装，并把 persona 替换成本项目人设；
       找不到随附预设时退回仓库自带的组装文件）
  2) 把两个技能写入      <DSH_HOME>/skills/
     （并把技能里的 <PROJECT_DIR> 占位符替换成本项目实际路径）
  3) 打印自检信息与上手步骤

用法：
    python install.py                 # 安装（自动定位 DSH_HOME）
    python install.py --check         # 只检查环境与安装状态，不改动文件
    python install.py --dsh-home "D:\\.dsh"        # 手动指定 DSH_HOME
    python install.py --standard-preset "<路径>"   # 手动指定随附 standard 预设文件

装完不需要重启 DSH：预设名单会在重新打开设置页/新建会话时重新读取。
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PRESET_ID = "jianli-supervisor"
PRESET_NAME = "房建监理模式"
PRESET_DESC = ("房建监理整改 Agent（课程演示原型）：接收施工现场隐患描述或 BIMFACE 碰撞检测 JSON，"
               "结合条文摘录知识库检索片段，输出【问题归纳】【规范依据】【监理整改意见】三段式书面意见；"
               "只引用检索片段内容，不编造条文。")
STANDARD_REL = Path("config") / "agent-presets" / "standard" / "agent.cordis.yml"


# ---------- 环境探测 ----------

def find_dsh_home(explicit=None):
    if explicit:
        return Path(explicit).expanduser().resolve()
    if os.environ.get("DSH_HOME"):
        return Path(os.environ["DSH_HOME"]).expanduser().resolve()
    return (Path.home() / ".dsh").resolve()


def _looks_like_dsh_install(p):
    try:
        return (Path(p) / STANDARD_REL).is_file()
    except OSError:
        return False


def find_shipped_standard(explicit=None):
    """定位随附的 standard 预设组装文件（用于生成与当前 DSH 版本匹配的预设）"""
    if explicit:
        p = Path(explicit).expanduser()
        return p if p.is_file() else None

    candidates = []

    # 1) dsh 可执行文件所在位置往上找
    exe = shutil.which("dsh")
    if exe:
        cur = Path(exe).resolve()
        for parent in list(cur.parents)[:6]:
            candidates += [parent / "@deepseek-ai" / "dsh",
                           parent / "node_modules" / "@deepseek-ai" / "dsh"]

    # 2) npm 全局目录
    try:
        out = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=20)
        if out.returncode == 0 and out.stdout.strip():
            candidates.append(Path(out.stdout.strip()) / "@deepseek-ai" / "dsh")
    except Exception:
        pass

    # 3) 常见全局安装位置
    for base in (os.environ.get("APPDATA"), os.environ.get("ProgramFiles"),
                 os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")):
        if base:
            candidates += [Path(base) / "npm" / "node_modules" / "@deepseek-ai" / "dsh",
                           Path(base) / "node_modules" / "@deepseek-ai" / "dsh"]

    for c in candidates:
        if _looks_like_dsh_install(c):
            return c / STANDARD_REL
    return None


# ---------- 组装预设 ----------

def build_composition(prompt_text, shipped=None):
    """返回 (组装文本, 说明)。优先替换随附 standard 预设里的 persona。"""
    lines = prompt_text.strip().splitlines()
    block = "    text: |-\n" + "\n".join(
        ("      " + ln) if ln.strip() else "" for ln in lines) + "\n"
    if shipped and Path(shipped).is_file():
        text = Path(shipped).read_text(encoding="utf-8")
        pattern = re.compile(r"(?m)^(    text: )>-\n(?:      .*\n)+")
        new, n = re.subn(pattern, lambda m: block, text, count=1)
        if n == 1:
            return new, "已基于本机随附 standard 预设重建，persona 替换为本项目人设"
    bundled = ROOT / "deploy" / "dsh-preset" / PRESET_ID / "agent.cordis.yml"
    return bundled.read_text(encoding="utf-8"), "未找到本机随附预设，改用仓库自带组装文件"


def install_preset(dsh_home, shipped):
    prompt = (ROOT / "system_prompt.md").read_text(encoding="utf-8")
    composition, note = build_composition(prompt, shipped)
    dest = dsh_home / ".agent-presets" / PRESET_ID
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "agent.cordis.yml").write_text(composition, encoding="utf-8", newline="\n")
    (dest / "preset.yml").write_text(
        "name: %s\ndescription: %s\norder: 20\n" % (PRESET_NAME, PRESET_DESC),
        encoding="utf-8", newline="\n")
    return dest, note


def install_skills(dsh_home):
    src = ROOT / "deploy" / "dsh-skills"
    done = []
    for d in sorted(p for p in src.iterdir() if p.is_dir()):
        content = (d / "SKILL.md").read_text(encoding="utf-8").replace("<PROJECT_DIR>", str(ROOT))
        dest = dsh_home / "skills" / d.name
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SKILL.md").write_text(content, encoding="utf-8", newline="\n")
        done.append(dest)
    return done


# ---------- 自检 ----------

def kb_entries():
    kb = ROOT / "kb" / "jianli_kb.txt"
    if not kb.is_file():
        return 0
    return sum(1 for ln in kb.read_text(encoding="utf-8-sig").splitlines()
               if ln.startswith("【检索片段】"))


def report(dsh_home, shipped):
    print("=" * 62)
    print("环境自检")
    print("=" * 62)
    print("Python      :", sys.version.split()[0])
    print("项目目录    :", ROOT)
    print("DSH_HOME    :", dsh_home, "（存在）" if dsh_home.exists() else "（不存在，首次安装会创建）")
    print("随附 standard 预设:", shipped if shipped else "未找到（将使用仓库自带组装文件）")
    preset = dsh_home / ".agent-presets" / PRESET_ID / "agent.cordis.yml"
    print("预设已安装  :", "是" if preset.is_file() else "否",
          "->", preset)
    sk = dsh_home / "skills"
    for name in ("jianli-kb-retrieval", "bimface-collision-parse"):
        p = sk / name / "SKILL.md"
        print("技能 %-24s %s" % (name + ":", "已安装" if p.is_file() else "未安装"))
    print("知识库条目  :", kb_entries(), "条")
    for mod, why in (("pymupdf", "读 PDF（推荐）"), ("pypdf", "读 PDF（备选）"),
                     ("docx", "读 Word .docx"), ("matplotlib", "画流程图（可选）")):
        try:
            __import__(mod)
            print("依赖 %-10s 已安装（%s）" % (mod, why))
        except ImportError:
            print("依赖 %-10s 未安装（%s，可选）" % (mod, why))
    print("\n上手：启动 DSH → 设置 →「Agent 预设」或新建会话界面的模式 chip → 选「%s」" % PRESET_NAME)


def main():
    ap = argparse.ArgumentParser(description="安装「房建监理模式」到本机 DSH")
    ap.add_argument("--check", action="store_true", help="只自检，不改动文件")
    ap.add_argument("--dsh-home", help="DSH_HOME 路径（默认 $DSH_HOME 或 ~/.dsh）")
    ap.add_argument("--standard-preset", help="手动指定随附 standard 预设文件路径")
    args = ap.parse_args()

    dsh_home = find_dsh_home(args.dsh_home)
    shipped = find_shipped_standard(args.standard_preset)

    if args.check:
        report(dsh_home, shipped)
        return

    dest, note = install_preset(dsh_home, shipped)
    skills = install_skills(dsh_home)

    print("✅ 安装完成")
    print("  预设:", dest, "（%s）" % note)
    for s in skills:
        print("  技能:", s)
    print()
    report(dsh_home, shipped)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
