---
name: soia-pkm-bootstrap-vault-ima
description: 把已有本地 Markdown vault 接入腾讯 ima 知识库消费端：安装客户端、建立目录映射、用 ima 官方 Skills 配置本地文件夹监控同步并验证检索。Triggers：「接入 ima」「同步到 ima 知识库」「配置 ima」「让 ima 监控 vault」
dependencies:
  hard: [soia-pkm-bootstrap-vault-base, soia-pkm-query-vault]
version: 1.1.2
created_at: 2026-07-16 16:00:31
updated_at: 2026-08-05 13:30:00
created_by: gpt-5.6-luna
updated_by: claude-opus-5
---

# soia-pkm-bootstrap-vault-ima

把已有本地 Markdown vault 接入腾讯 ima（[ima.qq.com](https://ima.qq.com/)）作为云端消费端。同步方向是 **vault → ima**；本地 Markdown、frontmatter、目录和 Git（若启用）是唯一真身，ima 中的内容不反向覆盖 vault。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 在 ima 中检索 vault 内容 | 建立同步范围和目录映射，接入指定 ima 知识库 | 映射表、同步范围和验证结果 |
| 新文章自动进入 ima | 引导使用 ima 官方 Skills 的本地文件夹监控能力 | 监控源目录、目标知识库和首次同步回执 |
| 保持本地内容为真源 | 明确单向同步与排除项 | 不会执行 ima → vault 反向同步 |

本 skill 不负责从零创建 vault，也不编造 ima 客户端的按钮名称、菜单路径或未公开 API。ima 具体 UI 操作未经本次实测，首次执行时必须以客户端实际界面为准并校正本文档。

### 客户如何使用

1. 提供已有 vault 路径、希望同步的相对目录、目标 ima 知识库和一篇用于验证的文章标题。
2. 安装并登录 ima 客户端。
3. 先确定**不能是 vault 根或整个 20 区**的目录 allowlist，并完成敏感级别预检，再在 ima 官方 Skills 中配置本地文件夹监控。
4. 首次同步只选一篇或一个小目录，确认层级、标题和正文后再扩大范围。
5. 在 ima 搜索验证文章；任何冲突都以本地 Markdown 为准，不从 ima 反向写回。

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
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s soia-pkm-bootstrap-vault-ima -y
```

配置约定：

```text
~/.config/soia-skills/soia-pkm-bootstrap-vault-ima/config.yml
SOIA_PKM_BOOTSTRAP_VAULT_IMA_CONFIG_FILE=<custom-config-path>
```

官方入口：

- ima 官网与客户端下载入口：https://ima.qq.com/
- ima 的 Skills、本地文件夹监控和知识库界面会随客户端版本变化；未实测部分标注为“以 ima 客户端实际界面为准，首次执行时校正本文档”。

**WorkBuddy** 的装载单位是角色化专家而不是插件，`npx skills add -a '*'` 覆盖不到它，需要单独安装，见 [docs/install/workbuddy.md](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)。

### 日志与完成回执

回执至少包含：客户端登录检查、目标知识库和本地 allowlist（只写相对目录）、首次同步范围、成功/跳过/失败数量、检索验证结果和仍需用户手动校正的 UI 步骤。不得打印账号、token、私有文件内容或本机绝对路径。

## 接入流程

### 1. 安装客户端并登录

打开 [ima 官方入口](https://ima.qq.com/)，安装电脑端客户端并登录。官网当前提供“打开电脑版”和客户端下载入口；具体安装提示以官方页面和本机系统为准。

### 2. 创建知识库并制定目录映射

在 ima 客户端创建一个用于消费 vault 内容的知识库。具体创建动作和字段名称未经实测，**以 ima 客户端实际界面为准，首次执行时校正本文档**。

只允许用户明确选择、并能持续保证不混入敏感笔记的子目录 allowlist。整个 vault、整个 `20_资料库/` 或历史导入树都不是合法同步源：

| vault 相对目录/类别 | 默认建议 | 原因 |
|---|---|---|
| `20_资料库/<精选子目录>/<明确云端范围>/` | 条件同步 | 目录内每篇 Markdown 都有 `sensitivity: public` 或 `internal`，且用户确认可上传 |
| `20_资料库/`、`20_资料库/90_历史导入/`、其他历史导入目录 | 禁止 | 根范围过宽；导入语料可能含凭据、个人路径和未核验内容 |
| `40_图书视频馆/` | 默认排除 | 可能含个人阅读记录、家庭信息或受版权约束的原文 |
| 已确认可上传的发布留底子目录 | 可选同步 | 只同步用户明确选择且完成隐私/版权复核的内容 |
| `00_Obsidian系统/`、`.obsidian/` | 排除 | 平台配置不是知识正文 |
| `30_日志与思考/`、`10_工作台/` | 默认排除 | 可能包含会话、草稿和临时私密内容 |
| `.git/`、`.env`、配置/凭据类文件 | 必须排除 | 版本数据、密钥和本机状态不应上传 |

路径允许不等于内容允许。先运行 fail-closed 预检；它只输出相对路径、计数与风险代码，不输出命中值：

```bash
python3 scripts/preflight_sync.py --vault <vault-path> \
  --path-prefix '20_资料库/<精选分类>/<明确云端范围>'
```

缺少/非法 `sensitivity`、值为 `private/restricted`、疑似凭据/私有绝对路径、symlink 或无法分类的附件都会使 `ready=false`。版权和业务授权仍需人工复核。没有明确范围或无法保证未来新增文件遵守同一规则时暂停，不要开启监控。

映射记录至少包含：

```text
本地 vault/<相对目录>  →  ima/<知识库>/<对应目录>
同步方向：vault → ima
排除：.obsidian/、.git/、.env、私密目录、未确认的日志/草稿
```

### 3. 配置 ima 官方 Skills 的本地文件夹监控

在 ima 的官方 Skills 能力中选择本地文件夹监控/知识库导入类能力，将上一步的本地 allowlist 目录映射到目标知识库。具体 Skill 名称、授权提示、监控开关、知识库选择和目录映射 UI **未经实测，必须以 ima 客户端实际界面为准，首次执行时校正本文档**；不要根据本 skill 猜测按钮或菜单路径。

首次配置硬门：

1. 运行预检并输出相对目录 allowlist、文件数、敏感级别分布与拒绝项；必须 `ready=true`，报告不得含正文或秘密值。
2. 只选择一个已通过预检的测试子目录，不选择 `20_资料库/` 根目录。
3. 先导入一篇 `sensitivity: public` 的 Markdown，再观察 ima 是否保留标题、正文、相对层级和可检索文本。
4. 确认监控范围、目标知识库和同步方向后，才扩大到完整 allowlist；扩大时重新预检。
5. 若官方 Skills 在当前客户端不可用，记录版本和缺失能力并停止自动同步；不要擅自改用第三方 watcher 或自建反向同步。

### 4. 验证检索

选择一篇本地 vault 文章，记录其标题和一个不敏感的独特短语。等待首次导入/索引完成后，在 ima 目标知识库中检索标题或短语，核对命中内容与本地 Markdown 一致。若未命中，按“监控范围 → 目标知识库 → 索引等待 → 文件格式/权限”的顺序排查，并把未实测的 UI 差异写入回执。

### 5. 边界与冲突处理

- 本地 Markdown vault 是唯一真身；ima 只是云端消费端。
- 只允许 vault → ima 的同步约定；本 skill 不做 ima → vault 反向同步。
- ima 中的摘要、标签、重排或 AI 生成内容不能自动覆盖本地正文。
- 变更同步范围前先暂停监控并复核排除清单，尤其是 `.env`、私密目录、会话日志和未发布草稿。
- 目录监控开启后，新增笔记也会进入云端范围；该目录的最近 `AGENTS.md` 必须明确只允许 `public/internal`，否则不启用持续监控。

## 完成后回执

执行完输出：

1. 客户端登录和目标知识库状态。
2. 本地相对目录到 ima 知识库的映射及排除项。
3. 官方 Skills 监控配置是否完成；未实测 UI 步骤逐项标注。
4. 一篇文章在 ima 中的检索验证结果。
5. 残余风险：索引延迟、权限、版本差异和未执行的反向同步；没有则写“无”。
