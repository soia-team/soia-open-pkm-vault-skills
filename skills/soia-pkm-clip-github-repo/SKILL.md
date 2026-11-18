---
name: soia-pkm-clip-github-repo
description: 将 GitHub 开源仓库归档为 Obsidian vault 的项目卡和调研笔记。触发：「归档这个项目 URL」「clip 这个 repo」「刷新项目卡」
version: 2.0.5
created_at: 2026-07-07 15:58:57
updated_at: 2026-11-18 10:15:00
created_by: claude opus 4.6
updated_by: gemini-4-hydrogen
---

# soia-pkm-clip-github-repo

将 GitHub 仓库克隆到本机 `upstream` 目录（源码不进 vault），并在 Obsidian vault 生成/刷新项目卡、调研笔记骨架与双向链接。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 归档单个 GitHub 仓库 | 克隆/复用本地 upstream 仓库，调用 `gen_repo_catalog.py --add` 建更新项目卡并起研读笔记骨架 | 项目卡、带双链的 `YYYY-MM-DD-调研-<仓名>.md` 骨架与同步索引 |
| 批量刷新已克隆仓库字段 | 扫描 `--upstream` 子目录幂等更新项目卡自动字段（不覆盖人工笔记） | 新增/刷新仓库数、失效/未核实提交提醒 |

### 客户如何使用

- 「归档这个项目 URL：`https://github.com/<owner>/<repo>`」
- 「扫描 upstream 目录，批量刷新所有开源项目卡的自动字段。」

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-clip-github-repo`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。依赖 Python 3 stdlib 与 Git；配置 `$SOIA_PKM_CLIP_GITHUB_REPO_CONFIG_FILE`（兼容 `$SOIA_PKM_CLIP_REPO_CONFIG_FILE`/`$SOIA_PKM_CLIP_REPO_ENV_FILE`）或 `~/.config/soia-skills/soia-pkm-clip-github-repo/config.yml`。

### 私密信息与中间数据

仅克隆用户指定公开仓库至 `SOIA_REPO_UPSTREAM_DIR`（代码本体不进 vault），不写入或回显 GitHub token 与个人绝对路径配置。

### 日志与完成回执

先落盘再回执：列出项目卡与调研笔记路径，标明非 git 目录缺失字段为`未核实`并提醒回填人工字段；项目卡落盘仅代表 `captured`，默认交给生命周期管理完成 `organized → MOC/导航 → map → Base`（不适用写 `not_applicable`）。

## 运行机制与字段边界

1. **路径解析（缺参 fail-closed 报错，不猜默认路径）**：vault 取 `--vault` > `OBSIDIAN_VAULT` > 私有 `config.yml`；upstream 取 `--upstream` > `SOIA_REPO_UPSTREAM_DIR`。卡片默认写 `60_开源项目/00_图书馆/项目卡/<仓名>.md`，调研笔记写 `60_开源项目/10_调研笔记/`（支持 `--notes-dir <相对路径>` 覆盖）。
2. **命令行入口**：
   ```bash
   python3 scripts/gen_repo_catalog.py --add https://github.com/<owner>/<repo> --upstream <upstream目录> --vault <vault路径>
   python3 scripts/gen_repo_catalog.py --upstream <upstream目录> --vault <vault路径> [--notes-dir <相对路径>]
   ```
   clone 失败时跳过代码拉取仅以 URL 建最小卡；已有调研笔记不重复创建，深度代码精读另由单独调研流程完成。
3. **自动字段 vs 人工字段（幂等重跑核心）**：
   - **自动刷新**：`tags: [开源项目]`、`仓名`、`github`、`分类`（`REPO_CATEGORY_MAP` / README 启发式 / 兜底「工具其他」）、`语言`、`本地路径`、`访问链接`、`最近提交`（非 git 留空）、正文首段简介及 `## 关联调研` 双向匹配。
   - **永久保留（严禁覆盖）**：`用途`、`状态`、`stars` 及正文 `## 我的笔记`。不打算克隆的仓不适用本技能。

## 验证与前向测试

离线 fixture 与前向测试覆盖参数解析、去重、自动/人工字段保留、落盘结构与回执字段；改后运行仓库 `unittest` 与 `audit_skills.py --strict`。
