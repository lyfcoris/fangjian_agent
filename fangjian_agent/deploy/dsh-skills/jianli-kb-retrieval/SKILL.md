---
name: jianli-kb-retrieval
description: 房建监理演示知识库检索。当用户描述现场隐患/质量问题、安全防护缺陷、BIMFACE 碰撞结果，或要求"找依据/查条文/按规范出整改意见"时，检索条文摘录库并输出【检索片段】格式的命中条目。
---

# 条文摘录库检索（jianli-kb-retrieval）

供"房建监理模式"预设使用。知识库与检索脚本位于项目：
`<PROJECT_DIR>`
（`install.py` 安装时已把上面的占位符替换为本机实际路径）

- 知识库：`kb\jianli_kb.txt`（UTF-8，# 开头为注释；条目以【检索片段】开头）
- 检索脚本：`skills\jianli_retrieve.py`（纯标准库，入口函数 `retrieve`）

## 何时使用
用户给出施工现场隐患描述、质量/安全缺陷描述、或碰撞检测归一化描述，且要输出三段式整改意见时，先检索、再把命中片段与输入一起用于作答。

## 使用方法（Windows / pwsh）
```powershell
$env:PYTHONIOENCODING='utf-8'
python -c "import sys; sys.path.insert(0, r'<PROJECT_DIR>\skills'); from jianli_retrieve import retrieve; print(retrieve('在这里粘贴用户的现场描述', top_k=3))"
```
自测：`python "<PROJECT_DIR>\skills\jianli_retrieve.py"`

## 输出契约（重要）
- 返回文本以【检索片段】开头，包含来源、主题标签、正文。**原样保留**，作为后续作答的规范依据；
- 返回"未命中：知识库未检索到直接适用的规范条文"时，如实告知用户未命中，只给管理性处置建议，禁止凭记忆补条文；
- 调参：描述太口语时可加 `keywords="后浇带 渗漏"`；无关条目多时加 `min_bigram_hits=3` 或提高 `min_score`；
- 扩充知识库用仓库自带工具：`python "<PROJECT_DIR>\kb_ingest.py" --file "某规范.docx" --source "规范全称" --code "GB XXXXX-XXXX" --tags "标签A/标签B" --dry-run`（先预览，确认后把 `--dry-run` 换成 `--yes`）；
- 脚本被沙盒禁止读文件时，改用 `lib_text=` 直传库内容。
