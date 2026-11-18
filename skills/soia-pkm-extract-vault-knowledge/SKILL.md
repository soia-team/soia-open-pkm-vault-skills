---
name: soia-pkm-extract-vault-knowledge
description: 从整个 Markdown/Obsidian 知识库或指定模块的工作台、冻结证据、文章、项目研究与历史语料中，提炼去状态、可复用且带来源的长期知识，同时保留原始证据并隔离敏感信息。触发：「从知识库提炼长期知识」「把这份材料沉淀为知识」「从指定模块提炼」「从这份报告抽方法」
dependencies:
  hard: [soia-pkm-query-vault]
  optional: [soia-pkm-manage-vault-lifecycle, soia-pkm-maintain-vault-health]
version: 1.0.4
created_at: 2026-08-01 16:30:00
updated_at: 2026-11-18 10:45:00
created_by: gpt-5
updated_by: gemini-4-hydrogen
---

# soia-pkm-extract-vault-knowledge

从带任务状态或来源噪声的材料中**提炼去状态、可复用的 20 区长期知识（create-only 新建）**，绝不搬走或改写 30/40/60/90 原有证据层（文件误放走 `soia-pkm-manage-vault-lifecycle`，死链地图走 `soia-pkm-maintain-vault-health`，查找靠 `soia-pkm-query-vault`）。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 把报告/日志/历史语料沉淀为 20 区知识 | 查重、去状态、剥离凭据/身份等敏感信息，create-only 新建带来源 wikilink 笔记 | 去向候选清单、manifest 验证与新建文件路径 |

### 客户如何使用

给出 vault 路径及来源笔记/模块（20 区新建须落 `10_主题知识`/`20_规范与手册`/`30_学习指南` 唯一编号子目录，历史导入仅作来源）；单篇且明确可直接建，超 3 篇、重名或涉敏感须先确认清单。

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-extract-vault-knowledge`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。依赖 `soia-pkm-query-vault`。

### 私密信息与中间数据

查历史导入优先用 `--no-snippets` 按路径筛选；写前过滤账号、密码、token、cookie、私有绝对路径、客户/家庭身份（只留抽象方法）；PDF/Word/图片仅在有显式提取/OCR 证据时引用正文结论。

### 日志与完成回执

汇报来源与 SHA-256、查重结果、新建/跳过文件、剥离状态与敏化项、原件保留确认，及 20 区地图 `updated`、统计与 `.base` 根校验结果（无 Base 写明未配置）。

## 提取流程与内容合同

1. 读根与 20 区 `AGENTS.md`，用 `soia-pkm-query-vault` 查重（同主题并存须说明理由，不覆盖生成副本），区分 `extract`（新建知识）、`move`（转生命周期）、`evidence_only`、`needs_review`。
2. 运行 create-only manifest 计划、写入与校验（细节与字段标准见 [references/knowledge-contract.md](references/knowledge-contract.md)）：
   ```bash
   python3 scripts/knowledge_manifest.py plan --vault <vault> --manifest <rel.json> --source <src.md> --target <20-target.md> --type guide --sensitivity internal
   python3 scripts/knowledge_manifest.py verify --vault <vault> --manifest <rel.json>
   ```
3. **内容与索引门槛**：frontmatter 含 `tags: [资料库, 长期知识]` 及精确来源 wikilink；正文必答「是什么 / 适用与边界 / 依据与待核验 / 如何复用 / 风险与时效」，禁留 `owner`/`status`/`next_action` 或一次性环境值。凡在 `20_资料库/` 新建文件，立即运行 `gen_vault_map.py` 与 `vault_index_verify.py`（契约见 `soia-pkm-maintain-vault-health/references/index-sync-contract.md`）。

## 验证与前向测试

用 fixture 前向核验「30 区审计 → 20 区指南」场景（原证据不变、新建目标、目标冲突与来源漂移均 fail-closed），并跑 `audit_skills.py --strict`。
