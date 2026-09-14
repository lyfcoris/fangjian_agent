---
name: bimface-collision-parse
description: 解析 BIMFACE 碰撞检测 JSON（文件路径或 JSON 字符串）为结构化碰撞块（碰撞编号/类型/构件A/B/位置/偏差值）。用户提供碰撞 JSON 文件或文本并要求分析整改时使用。
---

# BIMFACE 碰撞 JSON 解析（bimface-collision-parse）

供"房建监理模式"预设使用。解析脚本位于：
`<PROJECT_DIR>\skills\bimface_parse.py`
（`install.py` 安装时已把上面的占位符替换为本机实际路径；纯标准库，入口函数 `parse_bimface` / `format_results`）

## 何时使用
用户上传或指向 BIMFACE 碰撞检测导出的 JSON（仓库内 `inputs\pz8.json` 为 14 个点位的演示样例），要求分析碰撞并给整改意见。

## 使用方法（Windows / pwsh）
```powershell
$env:PYTHONIOENCODING='utf-8'
python "<PROJECT_DIR>\skills\bimface_parse.py" "<PROJECT_DIR>\inputs\pz8.json"
```

## 输出契约（重要）
- 每条碰撞输出一个【碰撞检测结果】结构化块：碰撞编号/碰撞类型/构件A/构件B/位置/偏差值，末尾附"归一化描述"；
- 解析后：把结构化块作为输入交给监理人设作答；需要规范依据时，把某条"归一化描述"再交给 `jianli-kb-retrieval` 技能检索，命中片段一并附上；
- 字段容错：支持中英文常见键名（clashId/id、elements/componentA|B、location/position、clearance/distance 等）；拿到真实导出文件后若字段解析为空，请把 JSON 结构交给用户核对映射。
