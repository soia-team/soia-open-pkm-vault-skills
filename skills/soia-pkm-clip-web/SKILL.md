---
name: soia-pkm-clip-web
description: 归档网页、博客文章或公开播客节目到 Obsidian vault；可同时保留 shownotes 与本地音频。触发：「归档这个网页」「clip 这个链接」「存这篇博客或播客」
version: 1.1.2
created_at: 2026-07-02 17:57:11
updated_at: 2026-11-18 10:30:00
created_by: claude opus 4.6
updated_by: gemini-4-hydrogen
---

# soia-pkm-clip-web

`clip` 家族的**通用网页与公开播客成员**：使用 `trafilatura`/`readability-lxml` 抽取正文，或解析公开 `PodcastEpisode` JSON-LD 提取 shownotes 与音频，按统一规范沉淀进 Obsidian vault。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 归档网页、博客或外文长文 | 抓取标题/作者/时间与完整正文；非中文正文自动补充意译 `## 中文译文`，默认随手交 `organize` 增量整理 | `<articles>/YYYY/MM/` Markdown 笔记与分步入库回执 |
| 归档公开播客单集（小宇宙/Apple Podcasts 等） | 调 `archive_podcast.py` 剥离分享 query、收 shownotes、按需下载音频落 `_attachments/podcasts/` 并嵌 `![[...]]` 播放器 | 播客笔记、音频本地路径/SHA-256 或 `--metadata-only` 纯文本 |
| 归档后转 PDF | 完成归档整理后按 [references/obsidian-pdf-export.md](references/obsidian-pdf-export.md) 走 Obsidian 原生导出 | 同目录 PDF 产物 |

### 客户如何使用

- 「归档这个网页链接到知识库，并同步更新文章 MOC。」（加“仅归档/不要整理”则停在 clip）
- 「存一下这期播客节目，保留 shownotes 并下载本地音频。」

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-clip-web`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。网页提取可选 `trafilatura`/`readability-lxml`（受 PEP 668 限制时用 `venv`/`--break-system-packages`）；播客脚本纯 Python 3 stdlib；可选配置 `~/.config/soia-skills/soia-pkm-clip-web/config.yml` 或 `$SOIA_PKM_CLIP_WEB_CONFIG_FILE`。

### 私密信息与中间数据

持久化前清除 URL 分享 query/fragment（带 query 媒体直链只在当次下载内存中使用，不进 vault/日志）；`.part` 临时下载失败清理、成功原子落盘；播客音频默认放 `<vault>/_attachments/podcasts/<episode-id>/`。

### 日志与完成回执

**先落盘后汇报**，必须分别报告 `captured`、`organized`、`moc_synced`、`map_synced`、`base_verified` 五段结果与未核实元数据；音频未嵌 `![[相对路径]]` 记 `audio_embedded: false`，任一整理步骤失败严禁宣称“已整理完成”。

## 抓取质量、播客与闭环规范

1. **抓取质量强制复核**：Cloudflare 等受保护站点缺浏览器时可退回 `r.jina.ai` 并在来源标明；写入后**必须亲读正文**排查登录墙（“请先登录”“verify you are human”）、几十字截断或全链接导航壳，失败则切备用引擎或标 `content_complete: false`，绝不交付拦截页。
2. **非中文意译与结构**：`language != zh` 在 `## 关联` 前补自然完整 `## 中文译文`（保留专有名词/命令/代码英文）；`## 我的看法` 留空；播客无逐字稿须标 `transcript_status: not_provided_by_source`（细则见 [播客网页归档](references/podcast-capture.md)）。
3. **五段闭环与长期提炼**：单篇归档成功后默认接 `soia-pkm-organize-article-moc` 做最小增量整理（严禁调全量重建），批量链接先报清单等确认；若要沉淀长期复用知识再转 `soia-pkm-extract-vault-knowledge`（回执与归档分开报告）。

## 验证与前向测试

播客解析、去参数、命名与 SSRF 门禁回归见 `tests/test_archive_podcast.py`；修改或真实交付前须跑 `audit_skills.py --strict` 并端到端实测节目页与音频容器。
