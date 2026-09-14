# -*- coding: utf-8 -*-
"""
bimface_parse.py —— 房建监理演示 Agent：BIMFACE 碰撞检测 JSON 解析 Skill
纯 Python 标准库，零第三方依赖，适配 DSH 工具沙盒。

职责：读取 BIMFACE 碰撞检测导出的 JSON 文件（或 JSON 字符串），
把每条碰撞归一化成 system_prompt.md 约定的结构化块：
    碰撞编号 / 碰撞类型 / 构件A / 构件B / 位置 / 偏差值
并附带一句“归一化描述”，供检索 Skill 与 Agent 直接使用。

字段兼容：因 BIMFACE 导出格式随版本/工程配置变化，本解析器对常见
字段命名做容错（clashId/id、elements/componentA|B、location/position、
clearance/distance 等，支持中文键），找不到真实样例时仍可运行。
拿到你的真实导出文件后，把结构贴给开发方核对映射即可（README 待办）。

用法：
    from bimface_parse import parse_bimface
    items = parse_bimface("inputs/bimface_sample.json")      # 传路径
    items = parse_bimface('{"clashes":[...]}')               # 传 JSON 字符串
    print(format_results(items))

直接运行：python skills/bimface_parse.py <json文件路径>
"""

import json
import sys


# ---------- 通用取值工具 ----------

def _pick(d, *keys, default=None):
    """按多个候选键依次取值，命中第一个非空返回"""
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _elem(v):
    """把“构件”字段（字符串或字典）归一成 {'name','category'}"""
    if isinstance(v, str):
        return {"name": v, "category": ""}
    if isinstance(v, dict):
        name = _pick(v, "name", "elementName", "displayName", "componentName",
                     "label", "构件名", "名称")
        cat = _pick(v, "category", "elementType", "type", "componentType",
                    "专业", "类别")
        if not name:
            name = _pick(v, "id", "guid", "elementId")
        return {"name": str(name or "未知构件"), "category": str(cat or "")}
    return {"name": str(v), "category": ""}


def _norm_clash_type(t):
    """碰撞类型归一化：兼容中英文常见写法"""
    s = str(t or "").strip().lower()
    if any(k in s for k in ("硬", "hard", "侵入", "intersect", "interfere")):
        return "硬碰撞"
    if any(k in s for k in ("软", "soft", "间隙", "净距", "clearance",
                            "proximity", "最小距离")):
        return "净距/间隙不足"
    if any(k in s for k in ("重叠", "overlap", "duplicate", "coincide")):
        return "构件重叠"
    return str(t).strip() or "未标注"


# ---------- 主解析 ----------

def _extract_location(c):
    loc = _pick(c, "location", "position", "point", "coords", "clashPoint",
                "pos", "位置", "坐标")
    if loc is None:
        return {}
    if isinstance(loc, (list, tuple)) and len(loc) >= 3:
        return {"x": loc[0], "y": loc[1], "z": loc[2]}
    if isinstance(loc, dict):
        return {
            "level": _pick(loc, "level", "floor", "storey", "楼层", "标高"),
            "grid": _pick(loc, "grid", "axis", "gridPosition", "轴线"),
            "x": _pick(loc, "x", "X"),
            "y": _pick(loc, "y", "Y"),
            "z": _pick(loc, "z", "Z"),
        }
    return {"raw": str(loc)}


def _extract_deviation(c, clash_type):
    """偏差值：数字一律按米处理，输出人读文本"""
    v = _pick(c, "clearance", "distance", "gap", "deviation", "净距",
              "间隙", "偏差")
    if v is None or not isinstance(v, (int, float)):
        return "未提供偏差值"
    mm = abs(v) * 1000.0
    if v < 0:
        return "净距 %.3f m（构件侵入约 %.0f mm）" % (v, mm)
    if "净距" in clash_type or "不足" in clash_type:
        return "净距 %.3f m（约 %.0f mm，需对照设计最小净距要求核验）" % (v, mm)
    return "净距 %.3f m（约 %.0f mm）" % (v, mm)


def _format_location(loc):
    parts = []
    if loc.get("level"):
        parts.append(str(loc["level"]))
    if loc.get("grid"):
        parts.append(str(loc["grid"]))
    if loc.get("raw"):
        parts.append(str(loc["raw"]))
    xyz = []
    for k in ("x", "y", "z"):
        if loc.get(k) is not None:
            xyz.append("%s=%s" % (k, loc[k]))
    if xyz:
        parts.append("(" + ", ".join(xyz) + ")")
    return " / ".join(parts) if parts else "未提供位置"


def parse_bimface(data):
    """
    data：JSON 字符串 或 文件路径 或 已解析的 dict/list
    返回：[{'id','type','severity','elemA','elemB','loc','loc_text',
            'deviation','desc'}, ...]
    """
    # --- 输入归一 ---
    if isinstance(data, (dict, list)):
        obj = data
    elif isinstance(data, str):
        s = data.strip()
        if s.startswith(("{", "[")):
            obj = json.loads(s)
        else:
            with open(s, "r", encoding="utf-8-sig") as f:
                obj = json.load(f)
    else:
        raise TypeError("不支持的输入类型: %s" % type(data))

    if isinstance(obj, list):
        clashes = obj
    elif isinstance(obj, dict):
        clashes = _pick(obj, "clashes", "results", "items", "collisions",
                        "clashResults", "碰撞结果", "列表") or []
        if isinstance(clashes, dict):
            clashes = list(clashes.values())
    else:
        clashes = []

    items = []
    for c in clashes:
        if not isinstance(c, dict):
            continue
        clash_type = _norm_clash_type(_pick(c, "clashType", "type", "collisionType",
                                            "碰撞类型", "类别"))
        # 构件：优先 elements 列表前两项，其次 elementA/elementB 等
        elems = _pick(c, "elements", "elementsInfo", "构件列表", default=[])
        elem_a = elem_b = None
        if isinstance(elems, list) and len(elems) >= 1:
            elem_a = _elem(elems[0])
            if len(elems) >= 2:
                elem_b = _elem(elems[1])
        if elem_a is None:
            elem_a = _elem(_pick(c, "elementA", "componentA", "firstElement",
                                 "first", "构件A", "构件一"))
        if elem_b is None:
            elem_b = _elem(_pick(c, "elementB", "componentB", "secondElement",
                                 "second", "构件B", "构件二"))
        loc = _extract_location(c)
        loc_text = _format_location(loc)
        dev = _extract_deviation(c, clash_type)
        sev = _pick(c, "severity", "priority", "严重程度", "等级") or ""

        def _nm(e):
            return ("%s（%s）" % (e["name"], e["category"])) if e["category"] \
                else e["name"]

        desc = "%s处，%s与%s发生%s，%s。" % (
            loc_text if loc_text != "未提供位置" else "模型未知位置",
            _nm(elem_a), _nm(elem_b), clash_type, dev)
        if sev:
            desc += "严重程度：%s。" % sev

        items.append({
            "id": str(_pick(c, "clashId", "id", "number", "碰撞编号") or "未编号"),
            "type": clash_type,
            "severity": str(sev),
            "elemA": elem_a,
            "elemB": elem_b,
            "loc": loc,
            "loc_text": loc_text,
            "deviation": dev,
            "desc": desc,
        })
    return items


def format_results(items):
    """把解析结果排版成 Agent 可读的结构化块（与提示词字段一一对应）"""
    if not items:
        return "[碰撞解析Skill] 未解析到任何碰撞条目，请核对 JSON 结构。"
    blocks = []
    for it in items:
        block = ("【碰撞检测结果】\n"
                 "碰撞编号：%s\n"
                 "碰撞类型：%s\n"
                 "构件A：%s\n"
                 "构件B：%s\n"
                 "位置：%s\n"
                 "偏差值：%s" % (
                     it["id"], it["type"],
                     it["elemA"]["name"] + (("（" + it["elemA"]["category"] + "）")
                                            if it["elemA"]["category"] else ""),
                     it["elemB"]["name"] + (("（" + it["elemB"]["category"] + "）")
                                            if it["elemB"]["category"] else ""),
                     it["loc_text"], it["deviation"]))
        if it["severity"]:
            block += "\n严重程度：%s" % it["severity"]
        block += "\n归一化描述：%s" % it["desc"]
        blocks.append(block)
    return "\n\n".join(blocks)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) > 1:
        items = parse_bimface(sys.argv[1])
    else:
        print("用法：python skills/bimface_parse.py <BIMFACE碰撞JSON文件路径>")
        print("示例：python skills/bimface_parse.py inputs/bimface_sample.json")
        sys.exit(0)
    print(format_results(items))
    print("\n--- 共 %d 条碰撞 ---" % len(items))
