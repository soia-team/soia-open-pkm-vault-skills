---
name: soia-pkm-library-book-catalog
description: 纯本地、幂等、可重复运行地维护 Obsidian 书库：补建待读记录并重新生成图书馆、阅读记录和按类型总览，不依赖微信读书。Triggers：「重新生成图书馆总览」「更新阅读记录总览」「补建待读记录」「书库整理」
version: 1.0.5
created_at: 2026-07-16 18:01:32
updated_at: 2026-11-18 10:35:00
created_by: gpt-5.6-luna
updated_by: gemini-4-hydrogen
---

# soia-pkm-library-book-catalog

PKM 书库的本地 catalog 层：只读写 vault 内 Markdown 与 YAML frontmatter，补建缺失待读记录并生成三份 Obsidian 总览（不调用微信读书 API、不依赖外部 sync 技能）。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 为有书卡但无记录的书补待读条目 | `backfill_reading_records.py` 幂等新建缺失记录（已有跳过） | 新建/跳过/失败数 |
| 更新图书馆 / 7 态阅读记录 / 类型总览 | `gen_library_md.py`、`gen_records_md.py`、`gen_genre_library_md.py` 生成分类视图 | 输出路径与书目统计（支持 `--output` 预览） |

### 客户如何使用

给出 `--vault <path>`（或配置 `OBSIDIAN_VAULT`）与可选 `--base <relpath>`，先可用 `--output <preview-path>` 预览总览，确认后省略 `--output` 写回书库（重复运行幂等安全）。

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-library-book-catalog`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。纯 Python 3 stdlib；不依赖微信读书 API、网络或 `WEREAD_API_KEY`。

### 私密信息与中间数据

纯本地运行，不创建网络缓存或外部状态；可选私有配置存 `~/.config/soia-skills/soia-pkm-library-book-catalog/config.yml` 或 `$SOIA_PKM_LIBRARY_BOOK_CATALOG_CONFIG_FILE`（兼容 `ENV_FILE` / `SOIA_PKM_LIBRARY_*`，仅存 `OBSIDIAN_VAULT`），日志仅报告泛化目录类别，不泄露不必要绝对路径。

### 日志与完成回执

汇报运行脚本与范围、新建/更新/跳过/失败数、资源类别、预览/写回检验结果、全库地图统计及各 `.base` 验证结果（无 Base 写 `not_applicable`）。

## 脚本入口与目录契约

1. **命令列表**（`scripts/` 下运行，共享 `--vault` / `--base <relpath>` / `--config <json>`；`--output <path>` 预览，省略则写回）：
   ```bash
   python3 backfill_reading_records.py --vault <vault-path> [--base <rel>]
   python3 gen_library_md.py --vault <vault-path> [--base <rel>] [--output <preview>]
   python3 gen_records_md.py --vault <vault-path> [--base <rel>] [--output <preview>]
   python3 gen_genre_library_md.py --vault <vault-path> --base <rel> [--output <preview>]
   ```
2. **结构与 Base 门禁**：`<base>/00_图书馆/`（`图书馆.base`、`书目/<分类>/<书名>.md`，`category`/`subcategory` 为权威源）与 `<base>/阅读记录/`（`阅读记录.base`、`想读/待读/计划读/在读/暂停/搁置/完成`、`阅读记录-总览.md`，通过 `book: "[[书名]]"` 反查）。现存 `.base` 必须在同一 `filters.and` 同时带 `file.inFolder(...)` 与标签过滤（禁 tag-only）；增删移动后须重建地图并用 `vault_index_verify.py` 验证全部 Base 根路径。

## 验证与前向测试

先用 `--output` 或测试 vault fixture 前向核验输出标题/统计与 Base 根路径校验（不以退出码 0 充当内容验收），并运行 `audit_skills.py --strict` 与库单测。
