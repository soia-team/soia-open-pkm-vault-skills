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
version: 2.2.3
created_at: 2026-07-02 16:45:19
updated_at: 2026-11-18 10:40:00
created_by: claude opus 4.6
updated_by: gemini-4-hydrogen
---

# soia-pkm-bootstrap-vault-base

初始化平台中立的 AI-native Markdown vault 骨架与 `AGENTS.md` 多 AI 适配层；默认 plan-first、create-only 幂等，**不创建 `.obsidian/`**、不覆盖已有文件（消费端配置交给 `soia-pkm-bootstrap-vault-obsidian` 等特化技能）。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 初始化中立 PKM 骨架与规则层 | 创建 00–90 分区（20 精选固定 `10_主题知识`/`20_规范与手册`/`30_学习指南`、历史导入 `90_历史导入`，默认 `00_Obsidian系统/` 与 `10_工作台/00_Inbox/`）及模板 | json `plan`、逐文件 create/skip/conflict/drift 与 `--check` 结果 |

### 客户如何使用

提供目标目录及可选自定义 `config.json`（Schema v2 支持 `extends_default`、`directories`、`files`），先跑默认 plan 审查 create/skip/drift，再 `--apply` 与 `--check`。

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-bootstrap-vault-base`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。依赖 Python 3 stdlib；YAML 配置额外需 `PyYAML`。

### 私密信息与中间数据

默认资产不含个人路径、账号或凭据；自定义含私人配置时由客户自行保管，不回交公开仓库。

### 日志与完成回执

汇报 plan/apply/check 模式、create/skip/conflict/drift 计数、目标类别、未覆盖文件及后续消费端特化技能建议。

## CLI、Schema v2 与生命周期约束

```bash
python3 scripts/init_vault.py <vault-path>                         # 1. 只输出 JSON plan
python3 scripts/init_vault.py <vault-path> --apply                 # 2. create-only 初始化
python3 scripts/init_vault.py <vault-path> --check                 # 3. 校验骨架与 drift
python3 scripts/init_vault.py <vault-path> --config <config.json>  # 或 --print-default-config
```

- **绝对红线**：所有自定义路径须为 vault 相对路径，禁止 `..` / 绝对路径 / symlink 逃逸（CLI > custom config > 默认）；`20_资料库/` 新增语义目录须带唯一数字前缀，已有 `10_融合分类/` 等迁移转 `soia-pkm-manage-vault-lifecycle` manifest；`--force --apply` 须先展示逐文件 overwrite plan 并获明确授权。
- **分区职责**：`10_工作台` 仅存当前状态；`30` 存冻结证据；去状态知识提炼至 `20` 精选（转 `soia-pkm-extract-vault-knowledge`）；历史入 `90`；Agent 日志分 `10_自动快照`/`20_精选复盘`/`90_历史导入`；接入会记 hook 转 `soia-pkm-log-agent-sessions`。Schema v2 保留一个周期对 v1 的兼容读取。

## 验证与前向测试

在两个临时目录实测：默认调用仅出 plan 不建目录、`--apply` 不产 `.obsidian/`、修改 `create_only` 文件重跑保持不变、`--check` 能报 drift、`../escape` 必失败。
