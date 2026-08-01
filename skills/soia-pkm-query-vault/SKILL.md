---
name: soia-pkm-query-vault
description: 以只读方式检索 Markdown/Obsidian vault 的文件名、正文、frontmatter、标签、反向链接与分区清单，并按当前状态、稳定知识、冻结证据、历史归档排序。触发：「在知识库里找」「搜索 PKM」「从 vault 回答」「查反向链接」
version: 1.1.1
created_at: 2026-08-01 12:00:00
updated_at: 2026-08-01 12:00:00
created_by: gpt-5
updated_by: gpt-5
---

# soia-pkm-query-vault

面向 AI 和用户的 vault **只读查询层**。它找证据、排序和引用，不整理目录、不维护索引、不改状态；隐藏配置目录及所有文件/目录 symlink 均跳过，避免越出 vault 读取私密内容。

## 客户可读说明

### 这个技能可以做什么

- 按文件名、正文、frontmatter 字段或标签搜索 Markdown 与 Bases 定义。
- 查某个笔记的 wikilink 入链。
- 统计分区和文件类型，帮助 AI 先缩小范围再读取正文。
- 以 `10 当前 → 20 精选长期知识 → 30 证据 → 40/50/60 专项 → 20 待分流/历史导入 → 90 历史` 为默认排序，并明确标记来源层；20 区只有 `10_主题知识/`、`20_规范与手册/`、`30_学习指南/` 标为 `stable`，其余内容标为 `imported`，不因路径自动获得可信度。

### 客户如何使用

提供 vault 路径和问题/关键词。只要求回答时，Agent 不改任何文件。先读取根与命中区规则，再用脚本缩小候选，最后只打开足以回答问题的文件。

### 依赖与安装

只需 Python 3；无持久索引、无第三方数据库。推荐安装整个 `soia-pkm-vault@soia` 插件。

### 私密信息与中间数据

默认跳过所有隐藏目录、`.git`、`.obsidian`、凭据/配置目录和二进制正文。普通结果输出匹配行短片段；历史导入、账号、安全或其他敏感语料先加 `--no-snippets`，只返回路径与匹配元数据。脚本不写缓存。

### 日志与完成回执

结果必须包含查询时间、模式、检查文件数、匹配数、截断与不可读数量。最终回答按“当前状态 / 稳定知识 / 历史证据”组织，并给 vault 相对路径或 wikilink。

## 查询命令

```bash
# 综合搜索（文件名 + 正文 + frontmatter）
python3 scripts/query_vault.py --vault <vault-path> --query '<keyword>' --json

# 标签或字段
python3 scripts/query_vault.py --vault <vault-path> --mode tag --query '<tag>' --json
python3 scripts/query_vault.py --vault <vault-path> --mode frontmatter \
  --field status --query active --json

# 入链与清单
python3 scripts/query_vault.py --vault <vault-path> --mode backlinks --query '<note-name-or-path>' --json
python3 scripts/query_vault.py --vault <vault-path> --mode inventory --json

# 只查精选知识并避免输出正文片段
python3 scripts/query_vault.py --vault <vault-path> --query '<keyword>' \
  --path-prefix '20_资料库' --exclude-prefix '20_资料库/10_融合分类' \
  --no-snippets --json
```

`--path-prefix` 与 `--exclude-prefix` 可重复使用，且只接受 vault 相对路径；`--limit` 控制输出上限，超过时 `truncated=true`。查询强时效事实时，vault 只提供线索，仍要按任务要求核验外部最新来源。

## AI 读取流程

1. 读根 `AGENTS.md`，确认客户 vault 的分区语义。
2. 先按文件名/标签查窄，再读正文；不要一开始加载全库大文件。
3. 当前任务先看 10 区；方法和规范优先看 20 的精选目录；需要时间证据时补 30；专项阅读/写作/项目研究进入 40/50/60；历史导入子树与 90 只有追溯时才读。
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
- JSON 包含 `checked_at`、`matches`、`truncated`、`unreadable`、`scanned_files`、路径范围和 snippet 状态。
- 中文、路径过滤、inline/多行标签、frontmatter 和 backlinks fixture 均能命中。
- `--no-snippets` 的结果不含命中正文或 frontmatter 值。
- 最终回答能区分当前、稳定和历史来源，不把 90 区旧 status 当现状。
