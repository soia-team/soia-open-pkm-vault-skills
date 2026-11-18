---
name: soia-pkm-manage-vault-lifecycle
description: 规划并安全执行整个 Markdown/Obsidian 知识库，或知识库中指定模块的盘点、整理、改名、迁移、归档与清理。触发：「整理知识库」「整理知识库的某个模块」「治理资料库」「整理工作台/资料库/日志/归档」
version: 1.4.5
created_at: 2026-08-01 12:00:00
updated_at: 2026-11-18 10:20:00
created_by: gpt-5
updated_by: gemini-4-hydrogen
---

# soia-pkm-manage-vault-lifecycle

把 vault 内容从临时捕获推进到活跃控制面、冻结证据、稳定知识或历史归档。全对象遵循 `captured → organized → MOC/导航 → map → Base` 五段入库合同（细则与回执模板见 [references/knowledge-intake-five-stage-contract.md](references/knowledge-intake-five-stage-contract.md)）。默认只产出 manifest，确认后无覆盖执行并复核地图与 Base。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 盘点并分流工作台/历史证据/稳定知识 | 按 10/20/30/90 层级路由、冲突排查与入链核对生成逐文件 SHA-256 迁移 manifest | 去向建议、冲突阻断、回滚键与验收结果 |
| 规范目录编号与清理明确空壳 | 用 `vault_structure_plan.py` 规范语义编号，并仅删除已列清单的 `.DS_Store`/无入链空正文/最终空目录 | 逐项结构清单、编号验收与前后统计 |
| 闭环收官五段入库 | 修复精确 `incoming_refs`、校验知识库地图统计与目标 `.base` 根范围 | 地图重建统计、`vault_index_verify.py` 通过证明与入库状态表 |

### 客户如何使用

说明「整理整个知识库」或指定模块（如 `20_资料库`、`10_工作台/某项目`、收件箱/归档区）及目标；Agent 先生成 manifest 给客户过目确认再 apply，绝不用裸 `rm` 或 `find -delete`。

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-manage-vault-lifecycle`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。纯 Python 3；vault 与 manifest 路径通过 CLI 显式传入。

### 私密信息与中间数据

manifest 只记录相对路径与 SHA-256，不含正文或凭据；含私人文件名的 manifest 仅留在客户 vault 受控证据区，不进公开仓。

### 日志与完成回执

汇报候选数、去向与理由、阻断/冲突、apply/verify/rollback 状态、wikilink 修复数、地图与 Base 验证结果及五段入库逐段状态（无 MOC/Base 时写 `not_applicable` 与理由）。

## 分区路由与编号规则

1. **核心层路由（政策基线见 [references/lifecycle-policy.md](references/lifecycle-policy.md)）**：当前状态/下一步/阻塞 → `10` 工作台；冻结调研/审计/决策/验收 → `30` 时间证据；去状态可长期复用知识（须提炼而非直搬证据，见 `soia-pkm-extract-vault-knowledge`）→ `20` 资料库；结束/被取代/仅追溯 → `90` 归档（`90_系统归档` 版本链在导航标 `canonical`/`superseded_by`，删除候选另表附 SHA-256/入链与授权，不凭“旧”字直删）。
2. **20 区目录编号**：精选一级目录固定 `20_资料库/10_主题知识/`、`20_规范与手册/`、`30_学习指南/`；历史导入为 `90_历史导入/`（一级固定 `10_保险`、`20_读书`、`30_工作`、`40_技术`、`50_日记`、`60_生活`、`70_写作`、`80_学习`、`90_资源`）；`10_融合分类/` 为 legacy 待清源。同父目录语义子区唯一编号 `10/20/.../90`（`99_本地补录`，溢出 `98..91`），年月/资源目录/隐藏插件目录例外；`.Archive` 等隐藏子树与 `.metion` 原样随行。
3. **30/40/50 接缝**：30 区按日期冻结且空壳单列清理清单；40 区文章移位后运行 `rebuild_moc.py --article <path>` 增量更新（全库重建仅限审阅完报告后）；50 区冲突只报不擅改 frontmatter；二进制仅核哈希搬运。

## CLI 执行与验收流程

1. 读根与目标区 `AGENTS.md`，排查同名、入链、开放 checkbox 与控制面状态，生成逐文件 manifest：
   ```bash
   python3 scripts/vault_lifecycle.py plan --vault <vault> --manifest <rel.json> --move '<src>::<dst>'
   python3 scripts/vault_lifecycle.py tree-plan --vault <vault> --manifest <rel.json> --source-root '<src-root>' --target-root '<dst-root>'
   python3 scripts/vault_lifecycle.py apply --vault <vault> --manifest <relative.json>
   python3 scripts/vault_lifecycle.py verify --vault <vault> --manifest <relative.json>
   python3 scripts/vault_lifecycle.py rollback --vault <vault> --manifest <relative.json>
   ```
   - 也支持 `--moves-file <UTF-8清单>`；存在开放项或未知状态须用户明确授权后传 `--allow-open-items --allow-unknown-status`（正文/frontmatter 哈希仍守恒）。
   - `rollback` 仅在目标哈希一致且源为空时生效，不得在客户真库演示回滚，验收须在临时 fixture 完成。
2. 目录改名、编号规范与授权空对象清理走 `vault_structure_plan.py`（有入链的无正文笔记自动阻断，`--preserve-empty-dirs` 可保留空目录，`--cleanup-file` 只接受单个显式 `.DS_Store`）：
   ```bash
   python3 scripts/vault_structure_plan.py plan|apply|verify --vault <vault> --manifest <manifest> [--scope <scope>] [--cleanup-root <root>]
   ```
3. 修复 `incoming_refs`（不改历史日志纯文本路径快照）；只要路径变化或 20 区增删文件，立即触发健康技能重建地图并运行：
   ```bash
   python3 scripts/vault_index_verify.py --vault <vault> --base '20_资料库/资料库.base' --map '20_资料库/OB知识库地图.md'
   ```
   缺“地图已重建 + Base 已验证”回执不得宣称整理完成（契约见 `soia-pkm-maintain-vault-health/references/index-sync-contract.md`）。
