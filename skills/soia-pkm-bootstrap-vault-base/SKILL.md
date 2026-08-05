---
name: soia-pkm-bootstrap-vault-base
description: 以 plan-first、create-only、可检查的方式初始化平台中立的 AI-native Markdown vault 基座，包含分区下钻规则、工作台生命周期、模板与多 AI 适配层。触发：「初始化知识库」「新建 Markdown vault」「搭建 AI-native PKM」
dependencies:
  external:
    - name: weread-skills
      required: false
      install: "npx skills add Tencent/WeChatReading -g -y"
    - name: huashu-weread-advisor
      required: false
      install: "npx skills add alchaincyf/huashu-weread -g -y"
version: 2.2.2
created_at: 2026-07-02 16:45:19
updated_at: 2026-08-05 13:30:00
created_by: claude opus 4.6
updated_by: claude-opus-5
---

# soia-pkm-bootstrap-vault-base

创建平台中立的 Markdown 内容骨架与 AI 协作规则。`.obsidian/`、ima 或其他消费端配置由各自特化技能负责。

## 客户可读说明

### 这个技能可以做什么

- 创建 00/10/20/30/40/50/60/90 分区、下钻 `AGENTS.md`、工作台 Schema v2、长期知识 Schema 与对应模板；20 区精选目录固定为 `10_主题知识`、`20_规范与手册`、`30_学习指南`，历史导入使用 `90_历史导入`。
- 建立 `AGENTS.md` 唯一规则源及 Claude/Gemini/opencode/workbuddy 适配层。
- 支持 JSON/YAML 自定义、默认 plan、显式 `--apply`、create-only 幂等和 `--check`。
- 不创建 `.obsidian`、不安装插件、不配置 hook、不删除或覆盖现有文件。

### 客户如何使用

1. 提供目标目录、语言/命名偏好和是否继承默认结构。
2. 先运行 plan，逐项审查 create/skip/conflict/drift。
3. 客户确认后加 `--apply`；已有文件默认跳过。
4. 再运行 `--check`，确认必需目录和种子文件存在。

### 依赖与安装

Python 3 是强依赖，JSON 配置零第三方依赖；YAML 配置额外需要 PyYAML。推荐安装整个 `soia-pkm-vault@soia` 插件。

装整个域（Claude Code 与 Codex 共用同一份域插件）：

```bash
claude plugin marketplace add soia-team/soia-open-skills
claude plugin install soia-pkm-vault@soia
```

只装这一个技能：

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s soia-pkm-bootstrap-vault-base -y
```

**WorkBuddy** 的装载单位是角色化专家而不是插件，`npx skills add -a '*'` 覆盖不到它，需要单独安装，见 [docs/install/workbuddy.md](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)。

### 私密信息与中间数据

默认资产不含个人资料、账号、凭据、绝对路径或私有项目事实。自定义配置由客户自行保管；含私人内容时不要提交到公开技能仓。

### 日志与完成回执

回执必须列出 plan/apply/check 模式、create/skip/conflict/drift 数量、目标类别、未覆盖文件和下一步平台特化技能。

## 命令

```bash
# 默认只输出 JSON plan，不创建目标目录
python3 scripts/init_vault.py <vault-path>

# 确认后执行 create-only 初始化
python3 scripts/init_vault.py <vault-path> --apply

# 验证必需骨架；缺失或 managed drift 时非 0
python3 scripts/init_vault.py <vault-path> --check

# 自定义
python3 scripts/init_vault.py <vault-path> --config <config.json>
python3 scripts/init_vault.py --print-default-config
```

`--force --apply` 会覆盖种子文件，属于高风险兼容选项：必须先显示逐文件 overwrite plan 并获得明确授权。正常增量升级应使用生命周期/文档同步方案，不用 force 重灌整个 vault。

## 默认结构与生命周期

- `10_工作台` 只保留当前状态/下一步：Inbox、唯一总控、按项目控制面。
- 一次性调研/审计/决策/执行/验收冻结到 30。
- 去状态后仍可复用的知识以“来源保留、create-only 提炼”进入 20 的主题知识、规范手册或学习指南；历史导入语料不自动视为精选知识。
- 已结束或被取代的工作台材料移到 `90_系统归档/10_工作台历史`。
- 20 区历史导入目标为 `90_历史导入/`；其一级分类采用 `10_保险`、`20_读书`、`30_工作`、`40_技术`、`50_日记`、`60_生活`、`70_写作`、`80_学习`、`90_资源`。已有旧 `10_融合分类/` 只能通过生命周期 manifest 迁移，不得初始化时裸改名。
- Agent 日志分为 `10_自动快照 / 20_精选复盘 / 90_历史导入`，默认不存完整聊天。

默认配置和种子资产是一个可修改的起点，不声称数字分区适合所有客户。若客户已有 `AGENTS.md` 或不同分区，先读取并用自定义 config 扩展；create-only 会保留现有规则。

## 配置 Schema v2

```json
{
  "schema_version": 2,
  "extends_default": true,
  "directories": {"add": ["20_资料库/10_主题知识/40_扩展主题"], "remove": []},
  "files": {
    "add": [
      {"path": "20_资料库/10_主题知识/40_扩展主题/AGENTS.md", "mode": "create_only", "content": "# 规则\n"}
    ]
  }
}
```

- 所有目标必须是 vault 相对路径；绝对路径、`..` 和 symlink 逃逸立即失败。
- `mode: create_only`：存在即跳过；`managed`：check 时报告内容漂移，但仍不自动覆盖。
- 自定义配置新增 `20_资料库/` 语义目录时必须使用唯一数字前缀；不要用 `20_资料库/主题` 这类无编号路径。已有目录改名应转生命周期 manifest，并在完成后刷新地图、验证 Base。
- CLI > custom config > bundled defaults。配置扩展不要求改公开脚本。
- schema v1 仍可读取一个兼容周期，并在合并后按 v2 行为执行。

## 与其他技能的边界

- Obsidian 设置、`.base` 视图、Bases 核心插件和 CSS → `soia-pkm-bootstrap-vault-obsidian`。
- 健康检查/地图 → `soia-pkm-maintain-vault-health`。
- 工作台/Inbox/归档迁移 → `soia-pkm-manage-vault-lifecycle`。
- 会话日志 hook → `soia-pkm-log-agent-sessions`（改用户配置前必须确认）。
- 只读搜索/回答 → `soia-pkm-query-vault`。
- PDF、Word、表格等附件提取后再检索 → `soia-pkm-clip-drive` → `soia-pkm-query-vault`；图片正文需要显式 OCR，不能把文件名命中当正文。
- 从日志、报告或历史语料提炼长期知识 → `soia-pkm-extract-vault-knowledge`。

## 验收

在两个临时目录做 forward test：

1. 默认调用只输出 plan 且目录不存在。
2. `--apply` 创建骨架，但不存在 `.obsidian/`。
3. 修改一个 create-only 文件后再次 `--apply`，内容保持不变。
4. `--check` 能报告缺失与 managed drift。
5. `../escape`、绝对路径和目标类型冲突均失败。
