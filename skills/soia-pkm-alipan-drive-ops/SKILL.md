---
name: soia-pkm-alipan-drive-ops
description: 执行阿里云盘登录、浏览与文件操作，并为资源整理提供底层能力。触发：「登录阿里云盘」「下载阿里云盘文件」「全盘扫描阿里云盘」
version: 2.2.8
created_at: 2026-07-02 23:02:39
updated_at: 2026-11-18 10:20:00
created_by: claude opus 4.6
updated_by: gemini-4-hydrogen
---

# soia-pkm-alipan-drive-ops — 阿里云盘原子操作层

阿里云盘原子操作层：封装官方 `aliyunpan` CLI 的登录、双盘操作、目录读写、下载与多线程全盘 JSONL 扫描，作为 `soia-pkm-alipan-curator` 的底层引擎，不越权做业务整理或学习计划决策。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 安装、登录或远程续期阿里云盘 | 用包装器 `run_with_env.py` 检查状态；支持非交互 pty 拉出 5 分钟扫码链接远程恢复 | UID、容量配额与双盘空间摘要 |
| 只读浏览或全盘 JSONL 扫描 | 显式 `--driveId` 列目录，或跑 `scan_drive.py` 输出断点续扫 JSONL 与 sidecar | JSONL 快照、目录/文件数与同名歧义告警 |
| 按批准计划执行安全读写与下载 | 在批准清单内限流节拍运行 `mv`/`rename`/`mkdir`/`download`/`rm` 并回读验证 | 账本记录、逐项 `✓/✗` 回读与交付路径 |

### 客户如何使用

- 「只读扫描阿里云盘备份盘的 `/某个目录`，输出 JSONL 快照。」
- 「按已批准的迁移清单预览 `mv`/`rename`，不要删除任何文件。」
- 「从资源库把 `<远端路径>` 下载到指定本地目录。」

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-alipan-drive-ops`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。依赖 macOS `brew install aliyunpan` 及 Python 3 stdlib。

### 私密信息与中间数据

官方登录态留在 provider `~/.config/aliyunpan/`，如需隔离目录仅把 `ALIYUNPAN_CONFIG_DIR` 写入 `~/.config/soia-skills/soia-pkm-alipan-drive-ops/config.yml` 或 `$SOIA_PKM_ALIPAN_DRIVE_OPS_CONFIG_FILE`（模板 [assets/config.example.yml](assets/config.example.yml)）。严禁执行 `cat config.yml`、`env`/`printenv` 或在日志回执中输出 token、cookie 或任何 env 值；扫描 JSONL 与账本仅放私有 state/temp 目录。

### 日志与完成回执

汇报登录/盘空间 check（无秘密值）、操作范围、账本与成功/跳过/失败数、独立只读回读核对结果及需人工确认项（含跨盘手移与 429 等待建议）。

## 操作规范与硬门禁

1. **包装器启动与配置隔离**：优先 `python3 scripts/run_with_env.py -- aliyunpan <cmd>`（仅放行 `aliyunpan`/`aliyunpan.exe`，拒绝 `env`/shell），避免与系统默认 `~/.config/aliyunpan/` 串会话。`alipan_env.py` 仅作模块导入，直跑不输出配置。
2. **双盘与显式 `--driveId`**：备份盘/资源库共享配额，跨盘不可用 CLI 移动；**严禁用 `aliyunpan drive <id>` 全局切换**（防多并发污染上下文），每条命令必须显式传入 `--driveId`。
3. **非交互远程登录恢复**：报登录失效时以 pty 保活 stdin（禁 `</dev/null`，用法见 [ops-playbook §1.4](references/ops-playbook.md#14-非交互环境取登录链接标准恢复流程)），按空格截出含 `:`,`,` 的 `scope` 完整链接发授权用户本人（5 分钟有效），确认扫码后再喂 Enter 并用 `who` 验证，同时清理辅助保活进程。
4. **脚本解析与高危红线**：`ls` 解析保留尾空格特征并统一加 `</dev/null`；`rm`（进回收站 30 天）/清空/覆盖先列清单并先 `ls` 防产生 `(1)` 重名；输出物理不可能时疑似污染须换通道核对；写操作按 **200–300ms** 节流，批量 listing **≥300ms**，遇 `429` 按 `x-retry-after` 退避绝不盲重试。
5. **全盘扫描与实战手册**：`scripts/scan_drive.py` 保留原始空格与 SHA-1/file_id，同名兄弟目录标 `ambiguous_name: true` + `AMBIGUOUS_NAME` sidecar 并阻断不下钻；`.errors`/`.progress`/`.done` 刻意与主产出同目录实现 `--resume`（不挪至 tmp）。详见 [实战手册](references/ops-playbook.md)。

## 验证与前向测试

改后运行仓库 `unittest` 与 `audit_skills.py --strict`；离线 fixture 与前向测试覆盖环境变量包装器白名单、JSONL 扫描解析、同名歧义阻断与回执字段验证。
