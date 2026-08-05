---
name: soia-pkm-extract-vault-knowledge
description: 从整个 Markdown/Obsidian 知识库或指定模块的工作台、冻结证据、文章、项目研究与历史语料中，提炼去状态、可复用且带来源的长期知识，同时保留原始证据并隔离敏感信息。触发：「从知识库提炼长期知识」「把这份材料沉淀为知识」「从指定模块提炼」「从这份报告抽方法」
dependencies:
  hard: [soia-pkm-query-vault]
  optional: [soia-pkm-manage-vault-lifecycle, soia-pkm-maintain-vault-health]
version: 1.0.3
created_at: 2026-08-01 16:30:00
updated_at: 2026-08-05 13:30:00
created_by: gpt-5
updated_by: claude-opus-5
---

# soia-pkm-extract-vault-knowledge

把带时间、任务状态或来源噪声的材料提炼成 20 区长期知识。新建知识，不搬走证据；原始报告、文章、日志和历史导入语料继续留在各自证据层。

## 客户可读说明

### 这个技能可以做什么

- 先查重，再从一个或多个来源提炼概念、指南、参考、检查表或通用模式。
- 删除当前进度、责任人、下一步和一次性环境值，保留适用边界、反例、时效说明与来源 wikilink。
- 在写入前识别账号、密码、token、cookie、个人路径、客户数据等敏感内容；知识笔记只保留抽象方法，不复制秘密值。
- 盘点 20 区时区分“精选长期知识”和“历史导入/来源语料”，不把旧语料的目录位置当成可信度。
- 处理 PDF、Word、表格或图片来源时，先标记原始附件类型和提取/OCR 状态；没有正文提取证据时只能引用文件名/路径，不能把附件标题当成结论。

### 客户如何使用

提供 vault 路径以及来源笔记、主题或待整理的 20 区范围。Agent 先给候选与去向；单篇且目标明确时可直接 create-only，新建超过 3 篇、存在重名或涉及敏感内容时必须先确认逐项计划。

### 依赖与安装

需要 soia-pkm-query-vault 做查重与来源定位。移动误放文件时转 soia-pkm-manage-vault-lifecycle；完成后可用 soia-pkm-maintain-vault-health 检查链接和地图。推荐安装整个 soia-pkm-vault@soia 插件。

装整个域（Claude Code 与 Codex 共用同一份域插件）：

```bash
claude plugin marketplace add soia-team/soia-open-skills
claude plugin install soia-pkm-vault@soia
```

只装这一个技能：

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s soia-pkm-extract-vault-knowledge -y
```

**WorkBuddy** 的装载单位是角色化专家而不是插件，`npx skills add -a '*'` 覆盖不到它，需要单独安装，见 [docs/install/workbuddy.md](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)。

### 私密信息与中间数据

默认不把历史导入语料的正文片段写进终端或会话日志；先用路径过滤和 --no-snippets 找候选，再只读必要文件。不得把凭据、真实账号、私有绝对路径、客户身份或家庭信息复制到知识笔记、manifest 或公开 skill 仓库。

### 日志与完成回执

回执包含：来源、来源 SHA-256、查重结果、创建/跳过文件、剥离的状态类别、敏感信息处理、来源是否保留、链接验证和待人工判断项。

## 执行流程

1. 读取根 AGENTS.md、来源区与 20_资料库/AGENTS.md。
2. 用查询技能先查目标标题、主题和反向链接；精选区优先，历史语料只作来源。
3. 把候选分成：
   - extract：有可复用结论，创建新的长期知识；
   - move：内容本身稳定，只是路径错，转生命周期技能；
   - evidence_only：只有时间线、任务状态或个人经历，保留证据；
   - needs_review：重名、冲突、过时或含敏感信息。
4. 对 extract 写计划：来源路径与 SHA-256、目标路径、知识类型、拟保留结论、拟删除状态、敏感级别、重复候选和来源链接。用脚本生成 create-only manifest：

   ```bash
   python3 scripts/knowledge_manifest.py plan --vault <vault-path> \
     --manifest <vault-relative-manifest.json> \
     --source <source.md> --target <20-target.md> \
     --type guide --sensitivity internal
   ```

5. 检查 `ready_to_write` 并让客户确认；create-only 写入目标。目标已存在时停止并比较，不覆盖、不生成“最终版/新版”副本。
6. 用脚本验证来源未漂移、目标 schema、精确来源 wikilink、开放项、私有绝对路径和秘密值候选。只要目标在 `20_资料库/` 或本次创建了新文件，立即按 `soia-pkm-maintain-vault-health/references/index-sync-contract.md` 重建地图；目标落在已有 Base 范围内时运行 `vault_index_verify.py`，不要为了单个文件重复维护列表：

   ```bash
   python3 scripts/knowledge_manifest.py verify --vault <vault-path> \
     --manifest <vault-relative-manifest.json>

   python3 <health-skill>/scripts/gen_vault_map.py --vault <vault-path>
   python3 <lifecycle-skill>/scripts/vault_index_verify.py --vault <vault-path>
   ```

详细判定和字段合同见 [references/knowledge-contract.md](references/knowledge-contract.md)。

## 内容合同

长期知识正文至少回答：

- 结论或方法是什么；
- 适用于什么条件，不适用于什么；
- 依据来自哪里，哪些内容仍待核验；
- 如何执行或复用；
- 常见失败方式、风险或时效性。

不要复制整份报告，不保留 owner/status/priority/next_action，不要把旧命令、端口、产品版本或组织事实写成永恒结论。

## 与其他技能的边界

| 意图 | 负责技能 |
|---|---|
| 查找已有知识或来源 | soia-pkm-query-vault |
| 新建来源保留的长期知识 | 本技能 |
| 移动 Inbox、误放笔记或历史文件 | soia-pkm-manage-vault-lifecycle |
| 死链、重复名、地图和周健康 | soia-pkm-maintain-vault-health |
| 文章主题/MOC 整理 | soia-pkm-organize-article-moc |

不得用 move 把 30 区冻结证据迁到 20；应保留 30 原件并新建 20 区提炼稿。

20 区目标目录遵循 `10_主题知识/`、`20_规范与手册/`、`30_学习指南/`；历史导入迁移目标为 `90_历史导入/`，其分类使用编号目录。目录改名属于生命周期迁移，不由本技能直接执行。

## 验收

- 来源保留且 SHA-256 与计划一致。
- 目标是新文件，frontmatter 完整，首标签为 资料库，含 长期知识 与来源 wikilink。
- 正文没有当前任务状态、开放待办或可识别秘密值。
- 同主题已有笔记已合并或明确说明为何并存。
- 自动 fixture 前向测试“30 区审计 → 20 区指南”：原证据不变、目标新建、目标冲突和来源漂移均停止。
- 若创建了 20 区文件，回执包含地图 `updated`、文件/目录统计和相关 Base 验证；没有 Base 时明确记录未配置，不把跳过写成通过。
