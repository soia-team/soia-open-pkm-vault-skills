---
name: soia-pkm-query-vault
description: 以只读方式搜索整个 Markdown/Obsidian 知识库或指定模块，检索文件名、正文、frontmatter、标签、反向链接、代码与附件，并按来源层级返回可核验结果。触发：「搜索知识库」「搜索知识库某个模块」「在知识库里找」「从知识库回答」「查需求/代码/PDF/Word/图片」「查反向链接」
version: 1.6.0
created_at: 2026-08-01 12:00:00
updated_at: 2026-08-04 12:00:00
created_by: gpt-5
updated_by: gpt-5
---

# soia-pkm-query-vault

面向 AI 和用户的 vault **只读查询层**。它找证据、排序和引用，不整理目录、不维护索引、不改状态；隐藏配置目录及所有文件/目录 symlink 均跳过，避免越出 vault 读取私密内容。查询结果若涉及入库状态，必须区分 `captured`、`organized` 与五段合同的完整回执；搜索命中本身不是整理完成证明。

## 客户可读说明

### 这个技能可以做什么

- 按文件名、正文、frontmatter 字段或标签搜索 Markdown、Bases、需求和常见 UTF-8 代码文件。
- 对 PDF、DOC/DOCX、PPT/PPTX、XLS/XLSX、图片和音视频做文件名、路径、扩展名与入链检索；附件正文优先通过已验证的 Omnisearch/Text Extractor 或 `obsidian-mcp-server` 检索，无法连接时才走显式 OCR/转换流程。
- 查某个笔记的 wikilink 入链。
- 统计分区和文件类型，帮助 AI 先缩小范围再读取正文。
- 以 `10 当前 → 20 精选长期知识 → 30 证据 → 40/50/60 专项 → 20 历史导入 → 90 历史` 为默认排序，并明确标记来源层；20 区只有 `10_主题知识/`、`20_规范与手册/`、`30_学习指南/` 标为 `stable`，`90_历史导入/` 标为 `imported`，不因路径自动获得可信度。
- `90_系统归档/60_整理与迁移记录/` 再细分为 `history/evidence`：先读该区导航识别 canonical 版本和 `superseded_by`，旧报告、机器清单和旧路径只用于解释当时过程。

### 客户如何使用

提供 vault 路径和问题/关键词。只要求回答时，Agent 不改任何文件。先读取根与命中区规则，再按下面的搜索手册缩小候选，最后只打开足以回答问题的文件。

### 依赖与安装

本地确定性后端只需 Python 3；它不建立持久索引。附件全文后端推荐 Obsidian 的 Omnisearch + Text Extractor；AI 接入可选 `obsidian-mcp-server`。语义召回可选 QMD，但不能代替精确搜索。

装整个域（Claude Code 与 Codex 共用同一份域插件）：

```bash
claude plugin marketplace add soia-team/soia-open-skills
claude plugin install soia-pkm-vault@soia
```

只装这一个技能：

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s soia-pkm-query-vault -y
```

**WorkBuddy** 的装载单位是角色化专家而不是插件，`npx skills add -a '*'` 覆盖不到它，需要单独安装，见 [docs/install/workbuddy.md](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)。

### 私密信息与中间数据

默认跳过所有隐藏目录、`.git`、`.obsidian`、凭据/配置目录和二进制正文。附件正文优先报告外部后端的命中；若后端不可用，必须明确回退为文件名/路径命中，再按需在临时运行目录提取并保留来源与哈希。普通结果输出匹配行短片段；历史导入、账号、安全或其他敏感语料先加 `--no-snippets`，只返回路径与匹配元数据。脚本不写持久缓存。

### 日志与完成回执

结果必须包含查询时间、模式、检查文件数、匹配数、截断与不可读数量。最终回答按“当前状态 / 稳定知识 / 历史证据”组织，并给 vault 相对路径或 wikilink。

## 查询命令

```bash
# 综合搜索（文件名 + 正文 + frontmatter）
python3 scripts/query_vault.py --vault <vault-path> --query '<keyword>' --json

# 文档地址/文件名：先用 filename，避免被正文重复命中淹没
python3 scripts/query_vault.py --vault <vault-path> --mode filename --query '<document-name>' --json

# 标签或字段
python3 scripts/query_vault.py --vault <vault-path> --mode tag --query '<tag>' --json
python3 scripts/query_vault.py --vault <vault-path> --mode frontmatter \
  --field status --query active --json

# 入链与清单
python3 scripts/query_vault.py --vault <vault-path> --mode backlinks --query '<note-name-or-path>' --json
python3 scripts/query_vault.py --vault <vault-path> --mode inventory --json

# 只查精选知识并避免输出正文片段
python3 scripts/query_vault.py --vault <vault-path> --query '<keyword>' \
  --path-prefix '20_资料库' --exclude-prefix '20_资料库/90_历史导入' \
  --no-snippets --json

# 需求：先查精选区，排除历史导入；需要时再进入 90_历史导入
python3 scripts/query_vault.py --vault <vault-path> --mode content --query '<需求关键词>' \
  --path-prefix '20_资料库' --exclude-prefix '20_资料库/90_历史导入' --json

# 代码：默认支持常见 UTF-8 代码/配置扩展；罕见扩展用 --include-ext 加入
python3 scripts/query_vault.py --vault <vault-path> --mode content --query '<class-or-symbol>' \
  --path-prefix '60_开源项目' --include-ext .feature --json

# PDF / Word / 图片：优先走 Omnisearch/MCP；不可用时再提取/OCR
python3 scripts/query_vault.py --vault <vault-path> --mode filename --query '<file-or-topic>' --json
python3 scripts/query_vault.py --vault <vault-path> --mode content --query '<extracted-keyword>' \
  --path-prefix '20_资料库' --exclude-prefix '20_资料库/90_历史导入' --json
```

`--path-prefix` 与 `--exclude-prefix` 可重复使用，且只接受 vault 相对路径；`--limit` 控制输出上限，超过时 `truncated=true`。查询强时效事实时，vault 只提供线索，仍要按任务要求核验外部最新来源。

## 搜索手册（回答前必须遵循）

### 1. 先判断问题类型

| 问题 | 首选模式 | 首选范围 | 说明 |
|---|---|---|---|
| “文档地址/文件在哪” | `filename` | 10 → 20 精选 → 90 | 先给路径，再读导航或正文 |
| “规范/怎么做” | `all` / `content` | 20 精选 | 稳定知识优先，返回来源与适用边界 |
| “当前进展/下一步” | `all` | 10 工作台 | 以最新 `updated` 的控制面为准 |
| “这次执行/审计结论” | `all` | 30 日志与思考 | 只把日期证据当冻结事实 |
| “需求/验收/接口” | `content` + `frontmatter` | 20 精选 → 10 项目 | 识别状态、范围、验收标准和来源 |
| “代码/类/配置/SQL” | `filename` → `content` | 60 / 指定项目 | 先查符号或文件名，再读最小上下文 |
| “谁引用了它” | `backlinks` | 全库或指定范围 | 路径重名时必须使用完整路径 |
| “PDF/Word/图片里有没有这句话” | `Omnisearch/MCP` → 临时提取/OCR → `content` | 指定附件目录 | 先区分文件名命中、插件正文命中、提取正文命中、OCR 命中；未连接后端不能声称正文命中 |

### 2. 再按层级排序，不按命中数量排序

`10 当前状态 → 20 精选长期知识 → 30 冻结证据 → 40/50/60 专项 → 20 历史导入 → 90 归档`。`20_资料库/90_历史导入` 默认只作为 imported 线索，不能因为命中次数多就升级为稳定结论；90 区整理记录还要按 canonical/历史版本链排序。

### 3. 需求和代码的具体步骤

1. 用需求中的专有名词、接口名、类名或错误码做 `filename`/`content` 精确搜索。
2. 若没有命中，拆成 2–3 个短关键词，分别查询，不把整句自然语言当成文件名。
3. 对代码先查定义符号，再查调用符号、配置键和测试名；按路径限定项目，避免跨项目同名误判。
4. 对 `.java`、`.py`、`.ts`、`.yaml`、`.json` 等常见 UTF-8 文件默认搜正文；罕见扩展用 `--include-ext <.ext>`。
5. 最终只打开能支持答案的最小文件集合，并标出版本、来源和是否需要核验。

对“找某组件文档地址并简介用法”这类问题，固定按以下顺序执行：

1. `filename` 搜索组件名、中文别名和 `使用手册`，先锁定 20 区导航与实际附件路径。
2. 打开 20 区稳定导航，确认链接目标；带小数点的文件名先按完整文件名匹配，不把版本号当扩展名。
3. 对 PDF/DOCX 等附件报告 `filename_hit`；只有 Omnisearch/Text Extractor、MCP 或临时提取成功，才追加 `content_hit`，并记录页码/提取器/哈希。
4. 返回“文档地址 + 用法简介 + 来源层级 + 命中类型”；若只有文件名命中，明确写“正文尚未解析”，不以 RAG 或语义候选冒充事实。

### 3.1 附件搜索支持矩阵

| 类型 | 文件名/路径 | 正文 | 默认处理 |
|---|---|---|---|
| PDF | 支持 | Omnisearch/Text Extractor 或显式 PDF 提取/OCR | 扫描 PDF 必须标记 OCR 和位置 |
| DOCX | 支持 | Omnisearch/Text Extractor 或 Word 提取器 | 保留原 DOCX 与来源哈希 |
| DOC（旧格式） | 支持 | 需外部转换器；当前 query 技能不直接解析 | 转换失败时只能报告文件名命中 |
| PPT/PPTX、XLS/XLSX | 支持 | 需相应转换器或提取流程 | 不把表格/幻灯片二进制当 UTF-8 读取 |
| PNG/JPG/GIF/WebP 等图片 | 支持 | Omnisearch/Text Extractor 或显式 OCR | OCR 结果必须标注 `ocr` 并允许人工核对 |
| 音视频 | 支持 | 需转写技能生成文本 | query 技能只检索文件名或转写稿 |

`soia-pkm-query-vault` 本身不上传文件、不维护插件缓存、不把 OCR/提取结果覆盖回原附件。没有可用 Omnisearch/MCP/提取器时，回执必须明确写“仅文件名/路径命中”。

多媒体选型、sidecar 字段、插件借鉴和分阶段落地见 [references/multimedia-search-options.md](references/multimedia-search-options.md)。

### 4. 结果解释与安全边界

- `layer=current/stable/evidence/specialized/imported/history` 是来源层，不是事实真伪的自动证明。
- `needs_review`、`deprecated`、`superseded_by`、旧日期或历史路径必须在回答中明确提示。
- 命中 `90_系统归档/60_整理与迁移记录` 时，结果必须附 `evidence_class`（迁移/重组/资源引用/核对清理/交接/历史版本）和“仅代表当时状态”提示；v1/v2/v3 同时命中时优先给 canonical 版本，再列被取代版本。
- 涉及历史导入、安全、账号或私人语料时使用 `--no-snippets`，先只返回路径和元数据。
- 本技能的确定性后端默认是关键词/结构检索；不上传内容、不启用 RAG。只有用户明确启用本地语义检索时，才增加 QMD/Smart Connections 等独立索引层，并把向量结果降级为候选召回。
- 搜索永远只读，不移动、删除、改 frontmatter、更新地图或创建待办。
- 查询“是否已整理/归档”时，读取管理技能生成的五段回执；缺少 `MOC/导航`、`map` 或 `Base` 证据时，只能报告为部分完成或未知，不能推断已完成。
- 目录编号或 legacy 路径迁移转 `soia-pkm-manage-vault-lifecycle`；不得在查询时自行重命名目录。

## AI 读取流程

1. 读根 `AGENTS.md`，确认客户 vault 的分区语义。
2. 先按文件名/标签查窄，再读正文；不要一开始加载全库大文件。
3. 当前任务先看 10 区；方法和规范优先看 20 的精选目录；需要时间证据时补 30；专项阅读/写作/项目研究进入 40/50/60；`20_资料库/90_历史导入` 与 90 只有追溯时才读。
4. 命中多个同名文件时使用路径，不用模糊短链猜测。
5. 比较 `updated`、日期、`superseded_by`、归档标签和正文更正说明；搜索排序不等于事实优先级。
6. 回答中引用真正支持结论的文件，并明确旧材料、草稿、待确认或冲突。

## 边界

- 不改 Markdown、frontmatter、Bases、地图或 git 状态。
- 不保存索引到 vault 或用户目录。
- 不把健康风险判断混入普通查询；死链/标签审计转健康技能。
- 不因搜索命中自动创建待办或归档；生命周期动作转生命周期技能。
- 用户要求完整文档时仍遵守权限、隐私和版权边界。

## 验收

- 运行前后 vault 文件树内容哈希一致。
- JSON 包含 `checked_at`、`matches`、`truncated`、`unreadable`、`scanned_files`、`searchable_extensions`、路径范围和 snippet 状态。
- 中文、路径过滤、inline/多行标签、frontmatter 和 backlinks fixture 均能命中。
- 需求/代码 fixture 能命中 `.java`、`.yaml` 等正文，罕见扩展能通过 `--include-ext` 加入。
- 附件验收必须区分文件名命中与正文命中；PDF/DOCX/OCR 的正文命中需要提取流程证据，缺少后端时稳定返回“不可解析/仅文件名”。
- `--no-snippets` 的结果不含命中正文或 frontmatter 值。
- 最终回答能区分当前、稳定和历史来源，不把 90 区旧 status 当现状。
