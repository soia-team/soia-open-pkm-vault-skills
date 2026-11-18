---
name: soia-pkm-distill-article-opinion
description: 通过苏格拉底式逐问，把用户对 vault 文章的回答整理成其本人观点，并写入「我的看法」或主题综述。触发：「补我的看法」「炼成观点」「主题观点综述」
version: 2.0.3
created_at: 2026-07-02 16:41:13
updated_at: 2026-11-18 10:25:00
created_by: claude opus 4.6
updated_by: gemini-4-hydrogen
---

# soia-pkm-distill-article-opinion

PKM 闭环 `收 → 整理 → ★点 → 写 → 发` 的**提炼观点环节**（方法借鉴阅读线炼金术，不依赖/调用第三方包）：通过逐问引导把文章沉淀为用户自己的立场，绝不代写或虚构。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 给单篇文章补「我的看法」 | 读原文后按三角度**一次只抛一个问题**（带回答示例），根据用户回答整理成第一人称视图 | 仅填入原文 `## 我的看法` 段，其余段落保持不变 |
| 跨同主题多篇文章聚合观点 | 读取 `_MOC/<分类>/<主题>.md` 下各篇「我的看法」，不足先提示逐篇提炼，素材够后综合综述 | `<vault-drafts-dir>/YYYY-MM-DD-<主题>-观点综述.md`，供 `compose` 成文 |

### 客户如何使用

- 「帮我给《xxx》补『我的看法』，一次问一个问题引导我。」
- 「把 MOC 里『某主题』下这几篇我的观点汇成一份主题综述。」

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-distill-article-opinion`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。纯 LLM 工作流，可选配置 `~/.config/soia-skills/soia-pkm-distill-article-opinion/config.yml` 或 `$SOIA_PKM_DISTILL_ARTICLE_OPINION_CONFIG_FILE`。

### 私密信息与中间数据

仅读写用户指定的 vault 笔记，不联网、不读凭据；用户未回答前绝不写入「我的看法」。

### 日志与完成回执

写完立即汇报：写入文件/段落路径、提炼出的 1–2 句观点核心摘要，并邀请用户微调（主题综述汇报草稿路径与核心论点）。

## 提问与写入规则

1. **铁律：绝不代笔**：AI 只负责提问与口语整理，不加入用户未表达过的判断；用户没想法时可跳过，绝不编造。
2. **模式 A（单篇提炼）**：定位文章 → 读 `## 原文` → 1–2 句对齐骨架 → 按**立场（买账与否）/ 经验检验 / 对你的意义**三角度用大白话提问，**每次只抛一个问题 + 给一句回答示例**（严禁一次抛多题/表格淹没用户），等用户回答后再下一题 → 整理为第一人称写入 `## 我的看法`（若已有非占位内容先问追加/替换，严禁动 frontmatter/`摘要`/`原文`）。
3. **模式 B（主题聚合）**：读 `_MOC/<分类>/<主题>.md` 汇总各篇 `## 我的看法`；多数为空则先劝补跑模式 A；足够后落 `<vault-drafts-dir>/YYYY-MM-DD-<主题>-观点综述.md`（`tags:[草稿]`），对接上游 `clip-*` 与下游 `soia-media-compose-article-draft`。
