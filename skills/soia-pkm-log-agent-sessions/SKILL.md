---
name: soia-pkm-log-agent-sessions
description: 为 Claude Code、Codex 等本地 AI 接入最小化 vault 会话改动快照，支持去重、dry-run、既有 notify 合并和安全卸载。触发：「接入 AI 会话日志」「记录 Codex 改动」「配置 SessionEnd 日志」
version: 1.1.0
created_at: 2026-08-01 12:00:00
updated_at: 2026-08-01 12:00:00
created_by: gpt-5
updated_by: gpt-5
---

# soia-pkm-log-agent-sessions

只负责 AI 会话结束时的**最小改动快照**。不保存完整 prompt、对话或推理，不判断内容该归档到哪里。

## 客户可读说明

### 这个技能可以做什么

- 为 Claude Code `SessionEnd` 或 Codex `notify` 生成轻量日志。
- 用 git 状态、tracked diff 和 untracked 内容哈希去重，连续编辑同一文件仍会产生新快照。
- 保留客户已有 Codex notify 命令，并提供 dry-run、安装检查和卸载步骤。
- 报告旧日志数量/体量；默认不自动删除或轮转。

### 客户如何使用

提供 vault 路径、AI 名称和期望日志目录。Agent 先展示将修改的用户配置片段；只有客户明确同意后才合并写入。首次先手动 dry-run，再触发一次真实小改动验证。

### 依赖与安装

- Python 3 和 Git 是核心依赖；shell wrapper 需要 POSIX bash。
- 推荐安装整个 `soia-pkm-vault@soia` 插件。

私有配置：

```text
~/.config/soia-skills/soia-pkm-log-agent-sessions/config.yml
SOIA_PKM_AGENT_SESSION_CONFIG_FILE=<custom-config-path>
```

装整个域（Claude Code 与 Codex 共用同一份域插件）：

```bash
claude plugin marketplace add soia-team/soia-open-skills
claude plugin install soia-pkm-vault@soia
```

只装这一个技能：

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s soia-pkm-log-agent-sessions -y
```

**WorkBuddy** 的装载单位是角色化专家而不是插件，`npx skills add -a '*'` 覆盖不到它，需要单独安装，见 [docs/install/workbuddy.md](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)。

### 私密信息与中间数据

- 默认日志只写时间、agent、变更数量、按顶层分区统计和验证结果；不写 diff、正文、prompt、事件 JSON 或环境变量。
- 去重状态在 `$XDG_STATE_HOME/soia-pkm-log-agent-sessions/`（无则 `~/.local/state/...`），不写 `.git`，兼容 git worktree。
- 默认不列单个文件路径；只有客户明确选择 `--include-paths` 才写 git status 路径。

### 日志与完成回执

回执包含配置是否变更、快照是否写入/去重跳过、日志相对目录、变更数量、状态目录类别、验证和卸载方法。

## 手动验证

```bash
python3 scripts/session_log.py --vault <vault-path> --agent Codex --dry-run
python3 scripts/session_log.py --vault <vault-path> --agent Codex
```

默认日志目录：`30_日志与思考/20_Agent工作日志/10_自动快照/<年>/<agent>/`。可用 `--log-dir` 或 `SOIA_SESSION_LOG_DIR` 覆盖；路径必须在 vault 内。agent 仅允许安全 slug。`--vault` 必须是 Git worktree 根；嵌在更大仓库中的子目录会拒绝运行，避免记录 vault 外改动。

## 接入流程

完整配置片段、合并与卸载规则见 [references/session-log-setup.md](references/session-log-setup.md)。硬门：

1. 修改 `.claude/settings.json` 或 Codex `config.toml` 前必须得到客户明确同意。
2. 先备份原配置，结构化合并；已有 hook/notify 不覆盖。
3. 路径使用安装后真实脚本绝对路径，不把维护者路径写进 skill。
4. 触发两次：第一次应写快照；无实质变化的第二次应 `deduplicated`。
5. 再编辑同一 tracked 文件，必须产生新快照，证明去重含内容而不只是文件名。

## 边界与保留

- 不做工作台/Inbox 分流；转 `soia-pkm-manage-vault-lifecycle`。
- 不做 vault 健康检查或知识检索。
- 不执行 add/commit/push，不读取 git 对象正文到日志。
- 不自动删除旧日志。需要清理时先输出按月份的数量/体量预览，再让客户单独确认。
- 配置缺失、vault 非 git 仓库、路径越界或 agent 非安全 slug 时明确失败；hook 调用可选择吞掉失败以免阻断主工具，但安装验收不能忽略失败。

## 验收

- 日志 frontmatter 使用 `tags: [Agent日志, 自动快照]`。
- 状态不在 `.git`，worktree fixture 可运行。
- 连续编辑同一路径的内容能产生不同 digest；无变化会去重。
- 日志无完整 prompt/diff/正文/事件 JSON/秘密值。
- 配置卸载后原有 hook/notify 仍完整。
