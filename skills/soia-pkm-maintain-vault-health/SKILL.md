---
name: soia-pkm-maintain-vault-health
description: 只读检查整个 Markdown/Obsidian 知识库或指定模块的健康状态，审计死链、歧义文件名、标签策略与过期内容，并按授权重建地图或健康简报。触发：「检查知识库健康」「检查知识库某个模块」「维护知识库」「重建知识库地图」「vault 周维护」
dependencies:
  optional: [soia-pkm-organize-article-moc]
version: 1.2.4
created_at: 2026-08-01 12:00:00
updated_at: 2026-11-18 10:40:00
created_by: gpt-5
updated_by: gemini-4-hydrogen
---

# soia-pkm-maintain-vault-health

负责 vault 的**只读健康诊断与全库地图重建**：审计死链、重名歧义、主标签与 20/50 区编号漂移；绝不直接移动、删改笔记，不设 AI hook，不替查询技能回答内容问题。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 默认是否写文件 |
|---|---|---|
| 检查全库或指定模块健康度 | 运行 `lint_vault.py` 查死链（含附件/`.base`）、重名歧义、标签漂移、过期与 20/50 编号 | 否 |
| 重建 `OB知识库地图.md` | 先用 `gen_vault_map.py --output` 预览，获确认后再写入默认地图（或 `$SOIA_VAULT_MAP_OUTPUT`）并复核 `.base` | 预览否，确认后是 |
| 执行「vault 周维护」简报 | 运行只读检查并统计近 7 天变化，仅用户要求保存时落周简报 | 默认否 |

### 客户如何使用

提供 vault 路径及可选标签白名单/模块路径；默认只输出结果不落盘，仅在明确要求「保存周报」或「重建地图」时写入相应文件。

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-maintain-vault-health`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。纯 Python 3 stdlib；可选私有配置 `~/.config/soia-skills/soia-pkm-maintain-vault-health/config.yml` 或 `$SOIA_PKM_VAULT_HEALTH_CONFIG_FILE`（支持 `SOIA_LINT_50_ROOTS_ADD`/`SOIA_LINT_50_ROOTS`）。

### 私密信息与中间数据

默认跳过 `.git`/`.obsidian`/`.trash`/隐藏目录与 symlink，拒绝经 symlink 逃出 vault 的地图写入，报告严禁印出正文或环境变量；临时预览放系统临时目录后清理。

### 日志与完成回执

汇报扫描/排除/不可读计数、六类发现、结构漂移、是否写入地图或周报、真实命令验证；重建涉及 20 区时必须同时列出 `OB知识库地图` 统计与相关 `.base` `file.inFolder` 根路径验证（未配 `.base` 写明“未配置”）。

## 三类工作流与边界

1. **A · 健康检查**：`python3 scripts/lint_vault.py --vault <vault> [--tags "<t1>,<t2>"] [--50-roots-add ...] --json`。未配 `--tags` 时置 `tag_policy_configured=false` 不误报漂移；带小数点笔记（如 `[[持续交付2.0]]`）按完整名匹配；`topics`/`people` 为词表不判死链，不造空占位页；MOC 审计只允许 `rebuild_moc.py --full-rebuild --dry-run` 预检。20/50 区按目标 vault `AGENTS` 报编号问题不强改名（迁移转 `soia-pkm-manage-vault-lifecycle`）。
2. **B · 重建地图（门禁见 [index-sync-contract.md](references/index-sync-contract.md)）**：先 `python3 scripts/gen_vault_map.py --vault <vault> --output <tmp.md> [--full]`，确认后省略 `--output` 落盘，随后重跑 `lint` 与生命周期 `vault_index_verify.py` 核对 `20_资料库/资料库.base`。
3. **C · 周维护**：结合 git/mtime 统计 7 日变更，区分可确定结构问题与需人工裁决项；查 `90_系统归档/60_整理与迁移记录` 时单列直属混放、无编号子目录、canonical/被取代链、失效机器清单与敏感字段候选（只报不删）。

## 验证与前向测试

只读运行前后除明确授权产物外文件树哈希不变；核验 JSON 含 `tag_policy_configured`、`20_structure`/`50_structure`、地图预览不写库，并在回执只报告真实命令结果。
