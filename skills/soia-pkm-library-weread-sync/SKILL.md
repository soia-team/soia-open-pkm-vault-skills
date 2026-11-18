---
name: soia-pkm-library-weread-sync
description: 同步微信读书已读书目与划线到 Obsidian 书库，并调用微信读书 API 补单本书详情。Triggers：「同步微信读书」「同步划线」「同步已读书目」「补一下这本书的详情」「补书详情」
dependencies:
  external:
    - name: weread-skills
      required: true
      install: "npx skills add Tencent/WeChatReading -g -y"
version: 2.0.4
created_at: 2026-07-06 11:12:07
updated_at: 2026-11-18 10:30:00
created_by: claude opus 4.6
updated_by: gemini-4-hydrogen
---

# soia-pkm-library-weread-sync

PKM 书库的数据同步层：将微信读书已读书架、划线想法写入 Obsidian 书卡与阅读记录，并调微信读书 API 补充单书详情（本地目录总览与补建交给相邻 `soia-pkm-library-book-catalog`）。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 同步微信读书书架与状态 | 运行 `sync_weread_to_library.py` 幂等新建/更新书卡与阅读记录 | 新增/更新/跳过/失败统计 |
| 同步划线与想法 | 运行 `sync_weread_highlights.py` 覆盖机器段同时保留 `### 用户笔记` | 每本书同步进度与写入结果 |
| 补充单本书详情与章节 | 运行 `enrich_book_details.py` 拉简介/目录/进度/相似书回填 | API 阶段、更新数量与失败原因 |

### 客户如何使用

说明要同步书架、划线或补详情书名，并提供 `--vault <path>`（或私有配置 `OBSIDIAN_VAULT`）；划线同步先默认预览或指定单本再 `--all` 全量。

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-library-weread-sync`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。**强制外部依赖**：微信读书官方 `weread-skills`（`npx skills add Tencent/WeChatReading -g -y`）与从 <https://weread.qq.com/r/weread-skills> 获取的 `WEREAD_API_KEY`。

### 私密信息与中间数据

`WEREAD_API_KEY` 与 `OBSIDIAN_VAULT` 仅存 `~/.config/soia-skills/soia-pkm-library-weread-sync/config.yml` 或 `$SOIA_PKM_LIBRARY_WEREAD_SYNC_CONFIG_FILE`（兼容 `$SOIA_PKM_LIBRARY_WEREAD_SYNC_ENV_FILE` / `$SOIA_PKM_LIBRARY_CONFIG_FILE` / `$SOIA_PKM_LIBRARY_ENV_FILE`，示例见 [assets/config.example.yml](assets/config.example.yml)，进程 env 优先且绝不回显 key/cookie；勿拿旧 Cookie 冒充 Bearer key）。

### 日志与完成回执

汇报同步范围、成功/跳过/失败计数、书卡与阅读记录变更及下游刷新建议；缺 `weread-skills`/`WEREAD_API_KEY` 时立刻停止 API 调用并输出获取指引。

## 脚本入口与目录契约

1. **常用命令**（`scripts/` 目录执行；共享 `--vault <path>`、`--base <relpath>`、`--config <json>`）：
   ```bash
   python3 sync_weread_to_library.py --vault <vault-path>
   python3 sync_weread_highlights.py [--all | <书名>]    # 默认预览 noteCount 前 30 本
   python3 enrich_book_details.py [<书名> | --all | --refresh-chapters]
   ```
2. **目录与笔记守恒**：书卡在 `<base>/00_图书馆/书目/<分类>/<书名>.md`（`category`/`subcategory` 为权威源），阅读记录在 `<base>/阅读记录/<状态>/<书名>.md`（通过 `book: "[[书名]]"` 绑定；划线匹配优先 `bookId`）。手写笔记必须放在 `## 📌 划线`/`## 💭 想法` 下的 `### 用户笔记` 子区块，避免下次同步被机器段覆盖。缺依赖/缺 key/缺 vault 均 fail-closed 退出；批量缺少本地书卡则跳过并告警。

## 验证与前向测试

复杂同步先以单本、前 30 本或仓库 `tests/` 离线 fixture 做前向核验，再全量同步；运行 `audit_skills.py --strict` 与库回归测试验证字段与脱敏。
