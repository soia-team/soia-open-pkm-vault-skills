---
name: soia-pkm-maintain-vault-health
description: 只读检查整个 Markdown/Obsidian 知识库或指定模块的健康状态，审计死链、歧义文件名、标签策略与过期内容，并按授权重建地图或健康简报。触发：「检查知识库健康」「检查知识库某个模块」「维护知识库」「重建知识库地图」「vault 周维护」
dependencies:
  optional: [soia-pkm-organize-article-moc]
version: 1.1.2
created_at: 2026-08-01 12:00:00
updated_at: 2026-08-02 15:20:00
created_by: gpt-5
updated_by: gpt-5
---

# soia-pkm-maintain-vault-health

负责 vault 的**健康诊断与地图**。它不移动、删除或归档笔记，不配置 AI hook，也不替代面向内容问题的检索技能。

## 客户可读说明

### 这个技能可以做什么

| 客户目标 | 技能行为 | 默认是否写文件 |
|---|---|---|
| 检查 vault 健康 | 扫描死链、重复文件名、主标签漂移、未打标、过期文章、读取失败，并报告 20 区目录编号漂移 | 否 |
| 重建知识库地图 | 先生成临时预览；用户明确要求后覆盖配置的地图文件 | 预览否，确认后是 |
| vault 周维护 | 运行健康检查，汇总近 7 天变化；按授权写周简报 | 默认否 |

### 客户如何使用

提供 vault 路径；若要检查主标签，再提供白名单或在私有配置中设置。只说“检查”时输出 stdout/JSON，不落盘。只有用户明确要求“保存周报”或“重建地图”才写对应产物。

### 依赖与安装

- Python 3（纯 stdlib）是脚本强依赖。
- `soia-pkm-organize-article-moc` 是可选后续：发现需要归类/MOC 合并时转交，不由本技能执行。
- 推荐安装整个 `soia-pkm-vault@soia` 插件；单技能可从本仓安装。

私有配置：

```text
~/.config/soia-skills/soia-pkm-maintain-vault-health/config.yml
SOIA_PKM_VAULT_HEALTH_CONFIG_FILE=<custom-config-path>
```

### 私密信息与中间数据

扫描只读取目标 vault；默认跳过 `.git`、`.obsidian`、`.trash`、隐藏目录与所有 symlink。报告不得打印文件正文、凭据或环境变量值。临时预览放系统临时目录，完成后可删除；默认地图输出若经 symlink 逃出 vault 会拒绝写入。

### 日志与完成回执

回执必须包含扫描文件数、排除/不可读数量、各类发现数量、是否写了地图/周报、实际验证与仍需人工判断的问题。

## 工作流 A：健康检查（默认只读）

```bash
python3 scripts/lint_vault.py --vault <vault-path> --json
```

标签策略默认**未配置**，此时 `tag_policy_configured=false` 且不把任意首标签判为漂移。需要标签检查时传：

```bash
python3 scripts/lint_vault.py --vault <vault-path> --json \
  --tags "<primary-tag-a>,<primary-tag-b>"
```

检查结果只说明结构风险：重复文件名不自动等于错误；只有短 wikilink 实际产生歧义时才优先修复。链接索引覆盖 Markdown、附件、`.base` 和其他真实文件，不能按扩展名跳过附件死链。

链接判定有两个固定例外：

- 文件名先按完整名称解析，再判断扩展名；`[[持续交付2.0]]`、`[[Fastjson-1.2.83]]` 这类带小数点的笔记不能被当成缺失附件。
- frontmatter 的 `topics` / `people` 是分类与署名词表，不要求每个词都有同名笔记；这些字段中的双链不计为死链。`book`、`source`、正文和显式附件链接仍须指向真实文件。

发现不存在的分类/署名时，整理技能应保留纯文本并说明“尚无对应笔记”，不要为了让 lint 通过而批量创建空笔记。

能唯一对应的拼写错误可在用户要求修复时单独列 plan；有多个候选、语义归类或删除需求时只报告。

### 20 区结构检查

健康回执必须额外报告：精选一级目录是否只有 `10_主题知识`、`20_规范与手册`、`30_学习指南`；这三个目录下所有语义二级/三级模块的未编号数、重复编号数；是否仍存在 legacy `10_融合分类`；历史导入一级分类是否使用 `10_保险`、`20_读书`、`30_工作`、`40_技术`、`50_日记`、`60_生活`、`70_写作`、`80_学习`、`90_资源`。年份/月份/日期、明确资源目录和隐藏插件状态目录应单独列为例外，不计入未编号。发现重复或无编号时只生成整改清单，不在健康检查中自动改名，转 `soia-pkm-manage-vault-lifecycle`。

## 工作流 B：重建地图

先预览：

```bash
python3 scripts/gen_vault_map.py --vault <vault-path> --output <temporary-preview.md>
```

用户确认后才省略 `--output`，写入 `SOIA_VAULT_MAP_OUTPUT` 或默认 `<vault>/20_资料库/OB知识库地图.md`。写后重新运行 lint，并确认地图中的文件/目录统计与实际扫描一致；若 vault 有 `20_资料库/资料库.base`，再运行生命周期技能的 `vault_index_verify.py` 核对 `file.inFolder` 根路径。完整门禁见 [index-sync-contract.md](references/index-sync-contract.md)。

## 工作流 C：周维护

1. 只读运行 lint，并用 git history 或文件时间统计近 7 天变化。
2. 明确区分：可确定的结构问题、设计性重复、需要用户判断的内容问题。
3. 仅在用户要求保存时写周简报；路径由客户 vault 规则或配置决定。
4. 简报固定包含：范围与时间、近 7 天变化、健康发现、已执行修复、人工处理项、验证。
5. 本技能不移动 Inbox/工作台内容；生命周期分流转 `soia-pkm-manage-vault-lifecycle`。

## 边界

- 不删除、移动、改名或归档笔记。
- 不把 PDF/Word/图片附件当作可直接读取的 Markdown；附件正文完整性转 `soia-pkm-clip-drive` 或显式 OCR 流程核验。
- 不接入 Claude/Codex 会话日志；转 `soia-pkm-log-agent-sessions`。
- 不回答“知识库里关于 X 有什么”；转 `soia-pkm-query-vault`。
- 不使用个人 vault 的标签表作为公开默认；标签策略由客户配置。

## 验收

- 只读运行前后除用户授权产物外的树哈希不变。
- JSON 可解析，包含 `tag_policy_configured`、五类发现与 unreadable 汇总。
- 地图预览不触碰 vault；正式地图仅在明确授权后写入。
- 最终回执列出真实运行的命令和结果，不把“脚本 exit 0”当作唯一证据。
- 若重建地图涉及 20 区，回执必须同时列出 Base 是否存在、每个根路径是否存在以及地图统计；未配置 Base 时明确写“未配置”，不冒充验证通过。
