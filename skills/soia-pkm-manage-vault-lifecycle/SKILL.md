---
name: soia-pkm-manage-vault-lifecycle
description: 规划并安全执行整个 Markdown/Obsidian 知识库，或知识库中指定模块的盘点、整理、改名、迁移、归档与清理。触发：「整理知识库」「整理知识库的某个模块」「治理资料库」「整理工作台/资料库/日志/归档」
version: 1.4.2
created_at: 2026-08-01 12:00:00
updated_at: 2026-08-05 13:30:00
created_by: gpt-5
updated_by: claude-opus-5
---

# soia-pkm-manage-vault-lifecycle

把 vault 内容从“临时捕获”推进到“活跃控制面、冻结证据、稳定知识或历史归档”。任何文件或对象都必须遵循 `captured → organized → MOC/导航 → map → Base` 五段入库合同；详细状态、对象路由与回执格式见 [references/knowledge-intake-five-stage-contract.md](references/knowledge-intake-five-stage-contract.md)。默认只生成 manifest；移动前必须确认，绝不自动删除，删除只能由用户确认的结构 manifest 执行。

## 客户可读说明

### 这个技能可以做什么

- 盘点整个知识库或指定模块，识别当前源、被取代材料、冻结证据、稳定知识与可归档内容。
- 生成含 source/target/SHA-256/入链/冲突/阻断/回滚信息的迁移 manifest。
- 用户确认后执行无覆盖移动，并验证数量与哈希；结构整理另有独立的目录编号/空对象 manifest，支持在目标未漂移时 rollback。

### 客户如何使用

用户只需说明“整理整个知识库”或指定模块（例如 `20_资料库`、`10_工作台/某项目`、某个 Inbox/归档区）以及目标；Agent 先读根与目标区规则，再查已有控制面、内容层级和引用关系，生成精确清单。客户确认 manifest 后才 apply；删除只能来自结构 manifest 中明确列出的 `.DS_Store`、无正文 Markdown 或最终空目录，不能用裸 `rm`/`find -delete`。

### 依赖与安装

只需 Python 3。建议安装整个 `soia-pkm-vault@soia` 插件。本技能不读取私有配置；vault 与 manifest 路径均由 CLI 显式传入。

装整个域（Claude Code 与 Codex 共用同一份域插件）：

```bash
claude plugin marketplace add soia-team/soia-open-skills
claude plugin install soia-pkm-vault@soia
```

只装这一个技能：

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s soia-pkm-manage-vault-lifecycle -y
```

**WorkBuddy** 的装载单位是角色化专家而不是插件，`npx skills add -a '*'` 覆盖不到它，需要单独安装，见 [docs/install/workbuddy.md](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)。

### 私密信息与中间数据

manifest 可保存 vault 相对路径和哈希，不保存正文、凭据或环境变量。含私人文件名的 manifest 应留在客户 vault 的受控证据区，不进入公开仓库。

### 日志与完成回执

回执包含：候选数、每个去向及理由、阻断/冲突、apply/verify/rollback 状态、链接修复清单和未获授权的动作。

## 路由合同

| 内容性质 | 目标 |
|---|---|
| 当前状态、下一步、阻塞、待用户确认 | 工作台（10） |
| 一次调研、审计、评审、决策、执行、验收、复盘 | 时间证据（30） |
| 去掉当前状态后仍可长期复用 | 资料库（20） |
| 结束、被取代、仅供追溯 | 归档（90） |

专项阅读、写作与项目研究继续服从客户 vault 的区域规则，不由数字前缀猜测。

### 历史证据与过期判定

- `90_系统归档` 里的迁移、审计、回补、核对和交接记录属于 `history/evidence`，不是当前状态源，也不是稳定知识。
- 先按证据角色分区：迁移执行、资料库重组、资源与引用、核对与清理、交接与专项、历史版本；记录混放时先建立导航和模块 `AGENTS.md`，再执行移动。
- `v1 → v2 → v3`、`初版 → 修正版 → 全量` 是可审计版本链。旧版默认保留在 `90_历史版本`，在导航中标 `superseded_by`；不能因文件名带“旧/无用/过期”直接删除。
- 机器清单（CSV/TSV/JSON）只说明生成时的输入和输出。计划必须重新检查路径存在性、当前数量、入链和敏感字段；历史正文中的旧路径快照不批量改写。
- “删除候选”与“移动到历史版本”分开建表。删除候选必须有精确路径、SHA-256、入链、替代证据、风险和用户授权；没有 0 字节或明确无正文证据时不删除。

### 20 区目录编号合同

精选目录固定为 `20_资料库/10_主题知识/`、`20_资料库/20_规范与手册/`、`20_资料库/30_学习指南/`。历史导入目标为 `20_资料库/90_历史导入/`；若盘点时仍发现 `20_资料库/10_融合分类/`，它只能作为待清理 legacy 源，不得继续写入。其一级分类目标固定为 `10_保险`、`20_读书`、`30_工作`、`40_技术`、`50_日记`、`60_生活`、`70_写作`、`80_学习`、`90_资源`，不接受无编号新分类。

“去状态后可复用”表示应当**提炼出新知识**，不是把 30 区冻结证据直接搬进 20。来源需保留时转 `soia-pkm-extract-vault-knowledge`；只有文件本身已经是稳定知识、仅路径放错时才用本技能 move。

## 执行流程

0. 为每个对象建立五段状态回执。MOC 或 Base 没有适用对象时必须写 `not_applicable` 及理由，不能省略字段或把上游技能调用当作完成证明。

1. 读取根 `AGENTS.md` 与所有目标区 `AGENTS.md`。
2. 搜索同名文件、现行控制面、frontmatter、开放 checkbox、wikilink 入链和替代关系。
3. 对目录改名或编号迁移，先生成旧路径→新路径的逐目录/逐文件清单，统计文件数、总字节、SHA-256、入链文件和需要重建的地图；不得用裸 `mv`。
4. 对每个候选写清“为什么移动、移动后谁是当前源、哪些链接要改”。历史证据再补 `evidence_class`、`canonical`、`superseded_by`、`deletion_candidate` 和理由。
5. 生成 manifest（`::` 分隔 source/target）：

   ```bash
   python3 scripts/vault_lifecycle.py plan \
     --vault <vault-path> \
     --manifest <vault-relative-manifest.json> \
     --move '<source>::<target>'
   ```

   大批量目录编号迁移使用一次性 tree-plan，避免把数千个 `--move` 参数塞进 shell：

   ```bash
   python3 scripts/vault_lifecycle.py tree-plan \
     --vault <vault-path> \
     --manifest <vault-relative-manifest.json> \
     --source-root '20_资料库/10_融合分类' \
     --target-root '20_资料库/90_历史导入'
   ```

   已有人工审核清单也可用 `plan --moves-file <UTF-8清单>`，每行一个 `SOURCE::TARGET`；空行和整行 `#` 注释会跳过。`tree-plan` 只生成逐文件 manifest，不移动文件。

6. 检查 `ready_to_apply`。目标存在、源漂移、路径越界、未知 status 或开放项均阻断；客户明确授权迁移历史材料时，可重做 plan 并显式加 `--allow-open-items --allow-unknown-status`。这两个开关只放行计划检查：原有 checkbox 原文和 `status` 值仍按 SHA-256 守恒，不在迁移中改正文或 frontmatter。
7. 用户确认 manifest 后执行并验证：

   ```bash
   python3 scripts/vault_lifecycle.py apply --vault <vault-path> --manifest <relative.json>
   python3 scripts/vault_lifecycle.py verify --vault <vault-path> --manifest <relative.json>
   ```

8. 按 manifest 的 `incoming_refs` 精确修复路径 wikilink；不要改历史日志里的纯文本路径快照。
9. 只要发生目录或文件路径变化，或在 `20_资料库/` 新建/删除文件，必须立即调用健康技能重建 [[20_资料库/OB知识库地图|OB知识库地图]]，再逐条验证目标区 `.base` 的 `file.inFolder` 范围；把地图统计、Base 范围和 lint 结果写入 30 区回执。内容-only 修改且路径未变时可不重建统计地图，但涉及 MOC、导航或 Base 定义仍必须复核。完整门禁见 `soia-pkm-maintain-vault-health/references/index-sync-contract.md`。没有“地图已重建 + Base 已验证（或明确记录未配置 Base）”不能宣称完成。

   ```bash
   python3 scripts/vault_index_verify.py \
     --vault <vault-path> \
     --base '20_资料库/资料库.base' \
     --map '20_资料库/OB知识库地图.md'
   ```

## 结构整理与编号规范

目录重复、三级编号混用和空对象清理使用独立的结构 manifest，不用裸 `mv`、`find -delete` 或按文件夹名猜分类：

```bash
python3 scripts/vault_structure_plan.py plan \
  --vault <vault-path> \
  --manifest '30_日志与思考/30_对话纪要与决策/YYYY/YYYY-MM-DD-计划-结构整理.manifest.json' \
  --scope '20_资料库/90_历史导入' \
  --cleanup-root '20_资料库/10_融合分类'

# 只删除一个已经核对过的 OS 元数据文件；不会扫描并删除其他正文
python3 scripts/vault_structure_plan.py plan \
  --vault <vault-path> \
  --manifest '<manifest>' \
  --scope '20_资料库/90_历史导入' \
  --cleanup-file '20_资料库/.DS_Store'

python3 scripts/vault_structure_plan.py apply \
  --vault <vault-path> \
  --manifest '<manifest>'

python3 scripts/vault_structure_plan.py verify \
  --vault <vault-path> \
  --manifest '<manifest>'
```

结构规划器的固定规则：

- 同一父目录下的语义目录使用唯一编号；优先 `10/20/.../90`，重复编号保留 `99_本地补录`，溢出使用 `98..91`，不再产生第二个相同数字前缀。
- `1.主题`、`2.主题` 等旧样式规范化为 `10_主题`、`20_主题`；所有知识语义目录（包括精选区二级/三级模块）都必须编号。只有年份、月份、日期、明确的 `_resources`、`_image`、`images`、`attachments` 等资源目录和隐藏插件状态目录是例外。
- 只删除 manifest 中明确列出的 `.DS_Store`、无正文 Markdown 和最终为空的目录；无正文笔记一旦有入链就阻断计划，生成地图的自动入链不作为阻断依据。
- 隐藏插件状态目录/文件（例如 `.metion`、`.icon.png`）随所属语义目录一起移动，不单独编号；含这些状态或资源文件的目录不是“空目录”，不会被清理。`--cleanup-file` 仅允许显式存在的 `.DS_Store`。
- 文件内容按 SHA-256 守恒移动；该工具不改正文、不覆盖目标。链接修复、地图重建和 Base 验证必须作为单独、可审计的后续动作。

### 30/40/50 分区整理接缝

- 30 区只保留按日期冻结的证据；Agent 日志按自动快照、精选复盘、历史导入分层，历史/运行时附件可保留在资料包内，但空壳目录必须单独列入清单，不因 Git 不跟踪就当作已删除。
- 40 区文章按 `<年>/<月>/` 归位；文章路径变化后必须重跑 MOC，再重建地图并验证 Base。主题/署名词没有对应笔记时用纯文本，不批量造占位页。
- 50 区按 `10_草稿 → 15_待审核 → 20_发布 → 90_归档` 流转；目录与 `status` 冲突时只报告冲突，除非用户明确指定真实状态，不凭目录名改 frontmatter。
- 派生物缺失附件时保留缺失证据，不创建假资源；完成声明必须同时给出迁移清单、SHA-256 守恒、地图统计、Base 验证和剩余空目录/冲突。

## Rollback

```bash
python3 scripts/vault_lifecycle.py rollback --vault <vault-path> --manifest <relative.json>
```

仅当目标仍与 manifest 哈希一致、原路径为空时回滚；任何漂移都停止。正文或链接在移动后另有编辑时，先人工评估，不强行覆盖。

## 安全边界

- 默认 plan；未经明确确认不 apply。
- `vault_lifecycle.py` 默认只移动、不删除；`vault_structure_plan.py` 仅在用户明确授权且 manifest 已列出哈希时删除空对象，不覆盖目标、不跨 vault、不接受 symlink 路径。
- 当前脚本只接受逐文件 manifest，不把目录树当成一个 move；大型历史导入树须先分批盘点，不能用裸 `mv` 绕过逐文件 hash、冲突和确认门。
- 目录编号迁移即使源目录为空也必须记录实际检查结果；只有用户明确授权才可删除空壳，不能把 Git 不跟踪空目录当作“无需记录”。`cleanup-file` 只用于把单个已核对的 OS 元数据纳入同一份清单。
- 已有 manifest、重复 source/target、manifest 与迁移路径重合均拒绝；apply 中途失败会尽力自动恢复已完成动作。
- 同一主线只有一个当前状态源；`done` 不能长期沉积在工作台。
- 无法判断“证据还是知识”时保留原位并报告，不用自动分类制造确定性。
- 二进制只移动并核对哈希，不尝试改写。

## 验收

- manifest 路径、source/target、size、SHA-256、open_items、status、incoming_refs 完整。
- 历史证据计划另外提供 `evidence_class`、版本链/替代关系和删除候选原因的伴随清单；机器 manifest 仍由脚本负责路径、哈希、入链和阻断检查，不能只用目录名推断“最新”。
- apply 后源不存在、目标存在且哈希守恒；verify 通过。
- 链接和 Bases 复核后无新增死链；地图必须在路径变化或 20 区新增/删除文件后重建，所有相关 `.base` 的 `file.inFolder` 路径必须存在且覆盖目标模块。
- `vault_index_verify.py` 必须通过；它核对地图的文件/目录统计与当前 vault，并核对 Base 的每个 `file.inFolder` 根路径。
- rollback 在临时 fixture 中验证，不在客户真实 vault 上为了演示来回搬动。
- 目录编号验收：没有重复一级 `10_`；历史导入一级分类均为目标编号；若 legacy 路径存在，必须有清晰迁移状态，完成后应由 verify 证明路径不存在。
- 批量 dry-run 验收：manifest 包含 `plan_type`、`summary.batches`、总字节、引用扫描统计和 blocker；tree-plan 未改变源树。
