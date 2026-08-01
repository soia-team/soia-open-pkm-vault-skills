---
name: soia-pkm-manage-vault-lifecycle
description: 规划并安全执行 Markdown/Obsidian vault 的 Inbox、工作台、冻结证据、长期知识与历史归档分流。触发：「整理工作台」「清理 Inbox」「归档已完成项目」「做 vault 生命周期迁移」
version: 1.1.0
created_at: 2026-08-01 12:00:00
updated_at: 2026-08-01 12:00:00
created_by: gpt-5
updated_by: gpt-5
---

# soia-pkm-manage-vault-lifecycle

把 vault 内容从“临时捕获”推进到“活跃控制面、冻结证据、稳定知识或历史归档”。默认只生成 manifest；移动前必须确认，永不自动删除。

## 客户可读说明

### 这个技能可以做什么

- 盘点 Inbox 和工作台，识别当前源、被取代材料、冻结证据与可提炼知识。
- 生成含 source/target/SHA-256/入链/冲突/阻断/回滚信息的迁移 manifest。
- 用户确认后执行无覆盖移动，并验证数量与哈希；支持在目标未漂移时 rollback。

### 客户如何使用

提供 vault 路径和整理范围。Agent 先读根与目标区规则，再查已有控制面和引用关系，给逐文件建议。客户确认 manifest 后才 apply；删除请求不属于本技能。

### 依赖与安装

只需 Python 3。建议安装整个 `soia-pkm-vault@soia` 插件。本技能不读取私有配置；vault 与 manifest 路径均由 CLI 显式传入。

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

“去状态后可复用”表示应当**提炼出新知识**，不是把 30 区冻结证据直接搬进 20。来源需保留时转 `soia-pkm-extract-vault-knowledge`；只有文件本身已经是稳定知识、仅路径放错时才用本技能 move。

## 执行流程

1. 读取根 `AGENTS.md` 与所有目标区 `AGENTS.md`。
2. 搜索同名文件、现行控制面、frontmatter、开放 checkbox、wikilink 入链和替代关系。
3. 对每个候选写清“为什么移动、移动后谁是当前源、哪些链接要改”。
4. 生成 manifest（`::` 分隔 source/target）：

   ```bash
   python3 scripts/vault_lifecycle.py plan \
     --vault <vault-path> \
     --manifest <vault-relative-manifest.json> \
     --move '<source>::<target>'
   ```

5. 检查 `ready_to_apply`。目标存在、源漂移、路径越界、未知 status 或开放项均阻断；开放项确为历史证据时可在客户确认后重做 plan 并显式加 `--allow-open-items`。
6. 用户确认 manifest 后执行并验证：

   ```bash
   python3 scripts/vault_lifecycle.py apply --vault <vault-path> --manifest <relative.json>
   python3 scripts/vault_lifecycle.py verify --vault <vault-path> --manifest <relative.json>
   ```

7. 按 manifest 的 `incoming_refs` 精确修复路径 wikilink；不要改历史日志里的纯文本路径快照。
8. 用健康技能复查死链与地图，把执行回执冻结到 30 区。

## Rollback

```bash
python3 scripts/vault_lifecycle.py rollback --vault <vault-path> --manifest <relative.json>
```

仅当目标仍与 manifest 哈希一致、原路径为空时回滚；任何漂移都停止。正文或链接在移动后另有编辑时，先人工评估，不强行覆盖。

## 安全边界

- 默认 plan；未经明确确认不 apply。
- 不删除文件或目录，不覆盖目标，不跨 vault，不接受 symlink 路径。
- 当前脚本只接受逐文件 manifest，不把目录树当成一个 move；大型历史导入树须先分批盘点，不能用裸 `mv` 绕过逐文件 hash、冲突和确认门。
- 已有 manifest、重复 source/target、manifest 与迁移路径重合均拒绝；apply 中途失败会尽力自动恢复已完成动作。
- 同一主线只有一个当前状态源；`done` 不能长期沉积在工作台。
- 无法判断“证据还是知识”时保留原位并报告，不用自动分类制造确定性。
- 二进制只移动并核对哈希，不尝试改写。

## 验收

- manifest 路径、source/target、size、SHA-256、open_items、status、incoming_refs 完整。
- apply 后源不存在、目标存在且哈希守恒；verify 通过。
- 链接和 Bases 复核后无新增死链；地图按授权重建。
- rollback 在临时 fixture 中验证，不在客户真实 vault 上为了演示来回搬动。
