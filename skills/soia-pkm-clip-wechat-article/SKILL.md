---
name: soia-pkm-clip-wechat-article
description: 归档单篇微信公众号文章到 Obsidian vault：抓取静态 HTML，提取标题、作者、正文、发布时间和配图，按 clip 家族规范落地；需要 PDF 时优先用 Obsidian 导出。Triggers：「归档这篇公众号」「clip 这个公众号文章」「存这篇微信文章」
version: 2.2.1
created_at: 2026-07-02 17:57:11
updated_at: 2026-11-18 10:35:00
created_by: claude opus 4.6
updated_by: gemini-4-hydrogen
---

# soia-pkm-clip-wechat-article

`clip` 家族的**公众号单篇成员**：抓取公众号文章静态 HTML 提取正文、元数据与配图链接，按规范落地 vault 并随手交 `organize` 增量收口（需要 PDF 走 Obsidian 原生导出）。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 归档单篇微信公众号链接 | 跑 `archive_wechat.py` 按标准化 URL 去重、解析 `#js_content` 与元数据，按默认五段收口整理 MOC | `<articles>/YYYY/MM/` Markdown 笔记与分步入库回执 |
| 归档后导出 PDF | 先完成 Markdown 归档与月份归位，再按 [references/obsidian-pdf-export.md](references/obsidian-pdf-export.md) 原生导出 | Markdown 与同目录 PDF 路径 |

### 客户如何使用

- 「归档这篇公众号文章 `https://mp.weixin.qq.com/s/...` 到知识库。」（明确说“仅归档”则停在 clip）
- 「存这篇微信文章并导出 PDF。」

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-clip-wechat-article`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。纯 Python 3 stdlib；公开 URL 无需凭据（当前脚本不解析 YAML `config.yml`，通过 `--vault`/`--articles-dir` 或 `OBSIDIAN_VAULT`/`OBSIDIAN_ARTICLES` 配置）。

### 私密信息与中间数据

仅拉取目标公开网页 HTML，无账号、Cookie 或 API key；除目标 vault 归档路径外不写其他私有目录。

### 日志与完成回执

**先落盘后汇报**，分别报告 `captured`、`organized`、`moc_synced`、`map_synced`、`base_verified`、实际落盘路径及`未核实`元数据；走 `Articles/` 兜底须提示配置正式目录，后置步骤失败严禁宣称“已整理完成”。

## 抓取与闭环规范

1. **预览与正文质量门**：先 `python3 scripts/archive_wechat.py <url> --vault <path> [--articles-dir <rel>] --dry-run --json` 核查标题/作者/`body_chars`/图片数；去重剥离 `?click_id=`/`scene=`/`poc_token=` 等跟踪参数同时保留 `__biz=&mid=&idx=&sn=`。缺 `#js_content`、截断或命中反爬提示时拒写并报 `block_reason`（验证码/参数错时提示改用可读 `/s/` 链接或手动粘贴；仅客户明确接受才加 `--allow-incomplete`）。
2. **落地与五段收口**：写入 `<articles>/<年>/<月>/YYYY-MM-DD-公众号-<作者>-<标题>.md`（`tags:[文章摘抄]`、`source: 公众号`、`url`、`author`、`publisher`、`published_at`、`captured_at`、`topics:[]`、`content_complete`；配图目前保留 `data-src` 外链；`## 我的看法` 留空）。落盘后默认调 `soia-pkm-organize-article-moc` 用 `rebuild_moc.py --article` 增量同步（禁单篇全量重建），批量文章先报清单确认。

## 验证与前向测试

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m py_compile scripts/archive_wechat.py
```

仓库内测试与 fixture 校验 URL 归一化去重、质量门拦截原因与五段回执字段（在 repo 根可将路径指向 `skills/soia-pkm-clip-wechat-article/...`）。
