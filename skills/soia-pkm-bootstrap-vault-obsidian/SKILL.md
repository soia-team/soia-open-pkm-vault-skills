---
name: soia-pkm-bootstrap-vault-obsidian
description: 以 dry-run 和保留未知配置的结构化合并方式，把已有 Markdown vault 配置为 Obsidian 消费端，启用 Bases 与可选宽页 CSS。触发：「配置 Obsidian vault」「启用 Obsidian Bases」「接入 Obsidian 消费端」
dependencies:
  hard: [soia-pkm-bootstrap-vault-base]
version: 2.1.1
created_at: 2026-07-16 16:00:31
updated_at: 2026-08-05 13:30:00
created_by: gpt-5.6-luna
updated_by: claude-opus-5
---

# soia-pkm-bootstrap-vault-obsidian

在 `soia-pkm-bootstrap-vault-base` 创建的本地 Markdown 知识库上安全合并 Obsidian 消费端配置。Markdown、YAML frontmatter 和 Git（若启用）仍是内容真源。

## 客户可读说明

### 这个技能可以做什么

- 检查 Obsidian 客户端是否可用；版本信息需以本机或官方当前信息为准。
- dry-run 预览并结构化合并 `core-plugins.json`、`appearance.json` 与可选 `app.json`，兼容新版对象和旧版列表两种核心插件格式。
- 保留未知核心插件、主题、snippet 和 JSON 键；启用 Bases 与宽页 CSS 时不覆盖客户现有配置。
- 为工作台、精选长期知识和工作台历史补充三个 create-only `.base` 视图；已有视图始终保留。
- apply 前备份将修改的现有文件；支持 `--check` 验收。

本 skill 不创建 PARA 骨架、不替代 base，也不把 Obsidian 数据反向写回其他云端知识库。

### 客户如何使用

其他可识别说法包括「配置 Obsidian」「装 Obsidian 插件」「Obsidian 特化配置」「启用 Bases」；从零建立通用 vault 骨架时先使用 `soia-pkm-bootstrap-vault-base`。

1. 先用 base 初始化或确认已有 Markdown vault；base 不写 `.obsidian`。
2. 提供 vault 路径，先运行脚本默认 dry-run。
3. 展示 JSON 合并和 CSS create/drift 清单，客户确认后加 `--apply`。
4. 运行 `--check`，再在 Obsidian 中打开 Bases 和普通笔记验证。

### 依赖与安装

安装本 skill（hard dependency 会同时要求 base）：

```bash
claude plugin marketplace add soia-team/soia-open-skills
```

```bash
claude plugin install soia-pkm-vault@soia
```

只要这一个技能时，可用 npx 路线。注意技能会落进共享真源 `~/.agents/skills`；若同时装了插件，同一技能会出现两份索引且各自漂移，建议二选一：

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s soia-pkm-bootstrap-vault-obsidian -y
```

本技能不需要凭据或私有配置；目标通过 CLI 传入。

外部安装入口：

- Obsidian 下载：https://obsidian.md/download
- 版本建议：1.9+，以当前官方版本和本机系统支持为准。

**WorkBuddy** 的装载单位是角色化专家而不是插件，`npx skills add -a '*'` 覆盖不到它，需要单独安装，见 [docs/install/workbuddy.md](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)。

### 日志与完成回执

回执至少说明：运行模式、备份类别、Bases/CSS/link format 的 create/update/skip/drift、`--check` 结果和客户端手动验证。不要打印账号、token 或 JSON 私有值。

### 私密信息与中间数据

本技能不需要账号或凭据。备份只包含本轮将修改的 Obsidian 配置文件，留在客户 vault 的隐藏平台目录；日志只报告键/列表类别和数量，不打印完整私有 JSON 值。

## 配置流程

### 1. 安装 Obsidian

从 [Obsidian 官方下载页](https://obsidian.md/download) 安装桌面客户端，并登录（若用户需要同步或社区插件等账号能力）。不需要为了打开本地 Markdown vault 而把账号凭据写入 vault 或 skill 配置。

### 2. 运行通用初始化

通用层命令：

```bash
python3 <path-to-base-skill>/scripts/init_vault.py <vault-path>
```

确认 plan 后：

```bash
python3 <path-to-base-skill>/scripts/init_vault.py <vault-path> --apply
```

base v2 永远不创建 `.obsidian`；平台配置只在本技能执行。

### 3. 预览并应用安全合并

```bash
# 默认 dry-run
python3 scripts/configure_obsidian.py <vault-path>

# 确认后应用；现有配置先备份
python3 scripts/configure_obsidian.py <vault-path> --apply

# 可选：显式设置 link format；不传则保留现值
python3 scripts/configure_obsidian.py <vault-path> --link-format relative --apply

# 验收
python3 scripts/configure_obsidian.py <vault-path> --check
```

脚本默认启用 Bases、三个 create-only `.base` 视图和 `wide-page` snippet。JSON 只增加缺失项，保留所有未知键/列表成员。已有 CSS 与 bundled 版本不同会报告 `drift` 并跳过；只有客户看过 overwrite plan 并明确授权后才能使用 `--force-managed --apply`。

默认清单：

| 类型 | 项目 | 必需? | 用途 |
|---|---|---|---|
| 本体 | Obsidian 1.9+ | 是 | 打开和编辑本地 Markdown vault |
| 核心插件 | Bases | 推荐/按视图需要 | 书库、文章库等数据库视图 |
| 内容视图 | 工作台/资料库/历史 `.base` | 推荐/按视图需要 | 从 frontmatter 聚合当前状态、长期知识与历史 |
| CSS snippet | `wide-page.css` | 推荐 | 撑满编辑器宽度；由本 Obsidian 特化技能提供 |
| AI CLI | Codex / Claude Code / Gemini CLI / Antigravity CLI / opencode / workbuddy | 推荐 | 直接读写本地 Markdown |
| 社区插件 | Tars | 可选 | 在 Obsidian 内调用 AI |
| 社区插件 | Terminal | 可选 | 在 Obsidian 内运行 AI CLI |
| 社区插件 | Obsidian Git | 可选 | 为 vault 提供 Git 版本控制 |

本体系不用 Dataview，不强依赖 Templater；默认模板和 frontmatter 足以运行通用闭环。安装社区插件前先核对作者、权限和本机安全策略。

### 4. 备份与回滚

修改前副本位于 `.obsidian/.soia-backups/<timestamp>/`，只包含本轮将修改的 Obsidian 配置文件。回滚时先关闭 Obsidian，再精确恢复该批次文件；不要删除整个 `.obsidian`。

### 5. 验证

先运行 `--check`；再在 Obsidian 中打开一篇 Markdown、一个 `.base` 视图，检查 frontmatter、wikilink、Bases 和宽页样式。最后确认未知插件、主题和设置仍保留。

## 完成后回执

执行完输出：

1. 已检查或安装的 Obsidian 版本。
2. Bases、CSS snippet 和可选插件的状态。
3. vault 内仅平台配置发生的文件变化。
4. 实际打开文章与视图的验证结果。
5. 需要用户按当前客户端界面补做的步骤；没有则写“无”。
