# 房建监理智能 Agent（课程演示原型）

面向"施工现场隐患描述 + BIMFACE 碰撞 JSON → 规范化监理整改意见"的演示级智能体。
基于 **DeepSeek Harness（DSH）** 的 **Agent 预设（persona）+ Skill 技能**搭建；因该部署无平台级 RAG，
知识库采用 **本地条文摘录库 + 检索 Skill**，检索结果以【检索片段】注入对话，
Agent 输出固定三段：【问题归纳】【规范依据】【监理整改意见】，并以硬约束**只引用检索片段、不编造条文**。

> ⚠️ 知识库含两类内容：**演示占位条目**（自编示意文字，非规范原文）与**规范条文摘录**（如 GB 55034-2022）。
> 版权与使用限制请先读 [`NOTICE.md`](NOTICE.md)；正式使用请购买正版标准并人工复核输出。

## 快速开始（下载后 3 步）

**环境要求**：Python 3.8+；DSH（DeepSeek Harness，本机 Web 版）。核心脚本只用标准库，无需装包；
PDF/Word 入库等增强功能按需：`pip install -r requirements.txt`。

```bash
# ① 本地验证链路（无需 DSH，30 秒；退出码 0 表示健康）
python demo_pipeline.py         # 检索 + 碰撞解析 + 消息组装
python evals/eval_run.py        # 检索评测：Hit@1/Hit@3/MRR/拒答率 + 库体检

# ② 一键装进本机 DSH（写入预设与技能，自动替换技能内的项目路径）
python install.py               # 只看环境与安装状态：python install.py --check

# ③ 打开 DSH → 设置 →「Agent 预设」（或新建会话界面的模式 chip）→ 选「房建监理模式」→ 开始对话
```

装完不用重启 DSH；预设名单会在重开设置页/新建会话时重新读取。

**第一次试什么**：把这句话发给"房建监理模式"会话 ——
「二层剪力墙拆模后表面多处蜂窝麻面，局部钢筋外露，请给出整改意见。」
（先不带检索片段，可观察防幻觉行为；再让 Agent 用 `jianli-kb-retrieval` 技能查依据，观察引用。）

## 目录结构

```
jianli-supervisor-agent/
├── install.py                # 一键安装：预设 + 技能 写入本机 DSH
├── system_prompt.md          # 监理人设文本源（install.py 会写入预设 persona）
├── demo_pipeline.py          # 本地链路自检脚本（无需 LLM）
├── kb_ingest.py              # 规范入库工具：docx/PDF/文字 → 切分查重追加（含质量闸门）
├── requirements.txt          # 可选依赖（PDF/Word 入库、流程图）
├── NOTICE.md / LICENSE       # 数据来源与版权声明 / MIT 许可
├── deploy/
│   ├── dsh-preset/jianli-supervisor/   # DSH 预设文件（含 persona 人设）
│   └── dsh-skills/                     # 两个技能（SKILL.md，装时替换 <PROJECT_DIR>）
├── skills/
│   ├── jianli_retrieve.py    # Skill 1：条文摘录库检索（输出【检索片段】）
│   └── bimface_parse.py      # Skill 2：BIMFACE 碰撞 JSON 解析
├── kb/
│   └── jianli_kb.txt         # 条文摘录库（UTF-8，# 开头为注释）
├── evals/
│   ├── eval_cases.py         # 评测用例集（10 正例 + 3 负例）
│   └── eval_run.py           # 检索评测：Hit@1/Hit@3/MRR/拒答率 + 库体检
└── inputs/
    ├── demo_cases.py         # 演示用例（唯一数据源）
    ├── bimface_sample.json   # 自检用模拟碰撞导出（2 条，demo_pipeline 依赖）
    ├── pz5.json              # 模拟碰撞导出（2 条，含字段变体：elements / componentA+B）
    └── pz8.json              # 展示用模拟碰撞导出（14 个点位）
```

## 一、本地自检（不依赖 DSH，30 秒验证全部链路）

```bash
cd jianli-supervisor-agent
python demo_pipeline.py
```

预期输出：环节1 五个用例 **PASS**、环节2 两条碰撞解析成功、环节3 两段
"组装好的 Agent 输入样例"；退出码 0。该脚本验证：检索命中正确性、
BIMFACE 容错解析、消息组装格式——**不含 LLM 调用**。

单独冒烟：`python skills/jianli_retrieve.py`、`python skills/bimface_parse.py inputs/bimface_sample.json`

## 二、在 DSH 里运行（预设已建好，只需点选）

DSH 的机制与常见"新建 Agent"不同：**一个会话 = 一个"模式（Agent preset）"**，
人设文本写在预设 `agent.cordis.yml` 的 persona 字段里，会话创建时挂载、之后固定。
本项目已把随附"标准模式"复制成自定义预设并写入人设，无需你编辑 YAML：

- 预设目录：`D:\.dsh\.agent-presets\jianli-supervisor\`
  （persona = `system_prompt.md` 全文；`preset.yml` 是显示名"房建监理模式"）
- 用户技能（DSH 原生 Skill = 指导文档，自动进技能目录）：
  `D:\.dsh\skills\jianli-kb-retrieval\` 与 `D:\.dsh\skills\bimface-collision-parse\`
  两个 SKILL.md 教 Agent 何时、如何运行本项目的检索/解析脚本。

Web 界面操作（任选其一，推荐第 1 种）：
1. **新建会话时选择**：新建会话界面，在工作区选择器旁的"模式"chip 里选
   **房建监理模式**，再确定工作区并新建；会话标题旁会出现只读模式标签。
2. **设为默认**：设置 → 常规（General）→ Agent 预设行 → 选"房建监理模式"，
   之后新建会话默认使用它。
3. **管理入口**：设置 → Agent 预设 分区（位于"模型"之后）：卡片可见、
   可设默认；复制/删除/查看预设文件都在这里。名单重读时机：重开设置页或
   重连后刷新，外部编辑的文件即被重新发现。

注意：预设**创建时固定**，运行中的会话不能换模式；修改预设文件后需**新建**会话生效。

## 三、两类输入的对话流程

> 两种取片段方式任选：①本机跑脚本手动粘贴（下列命令）；
> ②直接请会话里的 Agent "运行 jianli-kb-retrieval 技能检索一下"——
> Agent 会按 SKILL.md 自己执行脚本并带回【检索片段】。

### A. 土建隐患文本
```text
1) 本机运行： python -c "import sys;sys.path.insert(0,'skills');from jianli_retrieve import retrieve;print(retrieve('你的现场描述'))"
2) 把返回的【检索片段】整段复制，与现场描述一起发给 Agent：
   [现场输入]
   地下车库顶板后浇带两侧混凝土接茬处渗漏水……
   [知识库检索片段]
   【检索片段】演示教材《……》第X章 PXX……
```
也可直接在 DSH 内用工具调用 `retrieve(description="……")` 获取片段。

### B. BIMFACE 碰撞 JSON
```text
1) 解析： python skills/bimface_parse.py 你的碰撞结果.json
   （或直接调用 parse_bimface('文件路径或JSON字符串')）
2) 把输出（含【碰撞检测结果】结构化块 + 【归一化描述】）发给 Agent，
   并附上以归一化描述检索得到的【检索片段】，发问即可。
```

> 若检索返回"未命中：知识库未检索到直接适用的规范条文"，属**正常防幻觉行为**：
> 把该提示一并粘给 Agent，它会按硬约束只给管理性意见，不会编条文。
> 演示开场请说明：知识库为教学资料模拟，仅演示检索-引用链路。

## 四、输出校验点（演示时对照）

1. 三段标题齐全：【问题归纳】【规范依据】【监理整改意见】；
2. 【规范依据】只含消息内【检索片段】出现的内容，且格式带来源；
3. 无片段/片段不相关时，明确写"知识库未检索到直接适用的规范条文"；
4. 整改意见为工地书面语、分条编号、有复查闭环，无 AI 腔。

## 五、检索参数调优

| 参数 | 默认 | 说明 |
|---|---|---|
| `top_k` | 3 | 依据总缺关键条目→加到 5 |
| `min_bigram_hits` | 2 | 无关条目多→调大；该命中没命中→调 1 |
| `min_ratio` | 0.45 | 低于最强命中 45% 的尾部弱命中被裁掉（防噪声） |
| `min_score` | 5.0 | **绝对分数下限**：低于此分判为"未命中"，防止闲聊/合同类输入硬凑出条文 |
| `keywords=` | 空 | 自动抽取跑偏时手动指定，如 `keywords="后浇带 渗漏"` |
| `include_debug` | False | 调参时开 True 看匹配度与命中词 |
| 库内标签权重 | 内置 6.0 | 标签命中加分，强化"主题归属"（改代码 LABEL_BONUS） |

## 六、故障排查

| 现象 | 排查方向 |
|---|---|
| 幻觉：依据栏出现片段外的条文/编造编号 | 检查是否按"未命中"口径注入；调高检索命中率后重测 |
| 检索总"未命中" | `include_debug=True` 看最接近三条的词差；检查描述用词与库标签是否同词 |
| 检索带入无关条目 | 调大 `min_bigram_hits`/`min_ratio`；核对条目标签准确性 |
| 工具报读取文件失败 | 库文件须为 UTF-8；改用 `lib_text=` 字符串直传兜底 |
| BIMFACE 解析字段为空 | 字段命名与库不匹配：把真实 JSON 结构贴出，按 `_pick` 键清单补键名 |

## 七、扩充知识库：入库工具 kb_ingest.py

新增规范条文不用手改文件，用入库工具自动"切分条文号 + 生成条目 + 查重 + 追加"：

```powershell
pip install pypdf          # 仅"喂 PDF"需要，装一次即可
cd "D:\claude code\DeepSeek-Balance-Whale-Widget-main\agent"

# 方式1：文本型 PDF
python kb_ingest.py --pdf "某规范(文字版).pdf" --source "混凝土结构工程施工质量验收规范" --code "GB 50204-2015" --tags "后浇带/混凝土/养护"

# 方式2：Word 文件（.docx，推荐——文字层完整、不必 OCR）
python kb_ingest.py --file "某规范.docx" --source "砌体结构工程施工质量验收规范" --code "GB 50203-2011" --tags "砌体/拉结筋"

# 方式3：已整理的文本文件（大段粘贴建议先存成 .txt）
python kb_ingest.py --file "摘录.txt" --source "砌体结构工程施工质量验收规范" --code "GB 50203-2011" --tags "砌体/拉结筋"

# 方式4：直接传一段文字（自动按 8.2.1 这类条文号切分）
python kb_ingest.py --text "8.2.1 后浇带封闭时间应符合设计要求……"
```

- 自动行为：条文号行首切分 → 生成【检索片段】条目（含来源、主题标签）→ 与库内按正文查重 → UTF-8 追加写回，不破坏现有条目；
- 常用参数：`--num "8.2.1"`（没识别到条文号的单条补号）、`--dry-run`（先预览不写入）、`--yes`（跳过确认）、`--kb`（默认自动定位 kb\jianli_kb.txt）；
- 未带 `--source` 会报错提示所需参数；在真实终端里可加 `--interactive` 逐项提问填写；
- 支持 **.docx（推荐）**、文字层 PDF、纯文本三种输入；**扫描件 PDF 会被自动识别并中止**，提示改用 OCR 或文字版（`--force` 可强行继续）；
- **排版空格自动归一**：中文之间的空格会被去掉（`安 全` → `安全`），否则检索词会被拆散、匹配不到；章节标题行（`3.2 高处坠落`）不会混进条文正文；
- 仅支持"文字层"PDF：扫描版先 OCR 或另存文本再 `--file`；
- **入库质量闸门（重要）**：自动跳过正文 < `--min-body`（默认 8 字）的表格碎片；检测乱码（全角字母数字、康熙部首区字符、汉字占比过低）；疑似问题条目占比过高时**中止写入**并提示改用清楚的版本；确认无误可用 `--force` 放行；
- 只收某一主题时用 `--require-keyword 验收 --require-keyword 施工`（可重复）做白名单过滤；
- **按章节分组入库（推荐做法）**：整本规范一次入库时，同一批标签会加到每条上，通用词（如"安全"）容易污染检索；按章节拆开、每章配**专属多字标签**（如 `高处坠落防护 / 临边洞口防护 / 安全带`）效果最好——GB 55034-2022 就是这样入的（20 个章节分 20 批）；
- **知识库分层约定**：`kb/jianli_kb.txt` 只放**监理整改主题**条文；批量灌入的离题/低质内容移到 `kb/archive_ingested_raw.txt` 留档（不被检索读取）。教训：曾一次性灌入 5 份材料类标准 335 条，其中约 50 条是表格碎片/乱码，直接导致检索噪声与误命中——**入库前务必先 `--dry-run` 看预览**；
- 入库后建议照旧跑一次 `evals\eval_run.py`（或带 `include_debug=True` 检索用例），确认新条文可命中；
- 替换占位条目：加真实条文时直接覆盖同主题的模拟占位条目，避免"模拟/真实"混库导致引错。

## 八、检索评测（evals/eval_run.py）

离线评测检索质量，给出可用于答辩/简历的三个数字：

```powershell
python evals\eval_run.py        # 达标退出码 0，退化退出码 1（可挂进回归流程）
```

- 用例集 `evals/eval_cases.py`：10 个正例（土建质量 5 + 碰撞 1 + 施工安全 4）+ 3 个负例（闲聊/商务合同/无关创作，要求"未命中"）；
- 指标：**Hit@1 / Hit@3 / MRR / 拒答正确率**，另附知识库体检（条目数、重复正文、缺标签、来源行缺编号）；
- 结果同时写入 `evals/report.json`，便于对比版本变化；
- 当前基线（库内 144 条）：Hit@1 = 0.90，Hit@3 = 1.00，MRR = 0.950，拒答 = 1.00，库体检无重复/无缺标签/无缺编号。

## 九、待办清单

1. **继续扩充知识库**：已入库《建筑与市政施工现场安全卫生与职业健康通用规范》
   GB 55034-2022（127 条，覆盖 6 章 / 15 类事故防范）；仍待入库
   （建议：后浇带/渗漏/混凝土缺陷→GB 50204-2015；砌体→GB 50203-2011；
   抹灰→GB 50210-2018；验收程序→GB 50300-2013；监理闭环→GB/T 50319-2013），
   优先找 **.docx 或文字层 PDF** 版本，按第七章流程入库。
2. **BIMFACE 真实字段对齐**：拿到真实导出文件后核对 `bimface_parse.py`
   中 `_pick` 键清单，必要时补键名（结构与解析逻辑无需大改）。
3. **机电条目扩充**：碰撞场景当前仅 2 条占位，正式演示建议按演示模型
   补风管/桥架/给排水专业净距与管线综合条目。
4. **预设/技能部署位置**（本机版已就位）：预设文件在
   `D:\.dsh\.agent-presets\jianli-supervisor\`，技能在 `D:\.dsh\skills\`；
   迁移到其他机器时把这两个目录连同本项目一起拷贝即可。

## 十、边界说明

- 本原型不消费任何 LLM API：本地脚本只验证检索/解析/组装链路；
  "对话大脑"是 DSH 里的 Agent，需在 DSH 新建会话并选择"房建监理模式"
  预设后运行（见第二节）。
- 平台无 RAG 知识库功能 → 检索由 Skill 承担；平台有则可用其注入，
  检索片段标记【检索片段】不变，提示词无需改动。
