---
name: soia-pkm-baidu-netdisk-ops
description: 百度网盘原子操作与只读 JSONL 扫描适配。触发：「看下百度网盘」「登录百度网盘」「扫描百度网盘」
dependencies:
  external:
    - name: baidu-drive
      required: true
      install: "npx skills add https://github.com/baidu-netdisk/bdpan-storage/skills --skill baidu-drive"
version: 2.1.8
created_at: 2026-07-15 18:27:15
updated_at: 2026-11-18 10:20:00
created_by: claude opus 4.6
updated_by: gemini-4-hydrogen
---

# soia-pkm-baidu-netdisk-ops — 百度网盘原子操作层

PKM 层的百度网盘原子适配器：对接官方 `baidu-drive` Skill（`bdpan`）或社区 `baidupan-cli`，执行登录态核对、只读列表/搜索、授权读写传输与标准化 JSONL 扫描。不做业务重分类规划，也不绕过官方刻意禁用的删除能力或使用网页 Cookie/BDUSS。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 登录或检查百度网盘态 | 检查 `bdpan` 版本/登录态；支持设备码则生成授权链接与解码二维码交客户扫码 | 官方授权地址、非敏感状态与 `whoami` 核对 |
| 浏览、搜索与全盘 JSONL 扫描 | 运行 `ls --json`/`search --json` 或 `scan_drive.py` 多线程只读扫盘生成 sidecar | 远端清单、扫描统计、`.errors`/`.done` 与路径 |
| 按授权传输或建目录/移动/分享 | 先核父目录与冲突策略（`share` 单独确认），执行后回读验证 | 操作前范围确认与终态核实结果 |

### 客户如何使用

说明目标并给出远端虚拟路径（如 `/资料`）和本地路径；Agent 先查登录态，写操作/分享/覆盖先列出精确范围与冲突策略，确认后执行并回读验证。

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-baidu-netdisk-ops`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。依赖上游 `baidu-drive`（`npx skills add https://github.com/baidu-netdisk/bdpan-storage/skills --skill baidu-drive`）及其 `bdpan` CLI（或社区 `mqhe2007/baidupan-cli`）；后端差异见 [provider-cli.md](references/provider-cli.md)。

### 私密信息与中间数据

私有配置放 `~/.config/soia-skills/soia-pkm-baidu-netdisk-ops/config.yml` 或 `$SOIA_PKM_BAIDU_NETDISK_OPS_CONFIG_FILE`（模板 [assets/config.example.yml](assets/config.example.yml)，含 `provider: official|community`、`binary` 与社区 `BAIDUPAN_APP_*`）。绝不读取、复制或覆盖 `bdpan` 自有的 `~/.config/bdpan/config.json`，不打印 token/AppSecret/授权码；禁止路径含 `..`/`~`，对外隐藏 `/apps/bdpan/` 前缀。

### 日志与完成回执

汇报 `CLI`/`whoami` 核对、远端范围、变更与冲突、校验（本地大小/`ls` 回读/sidecar 状态）及未核实/待确认项（扫描含错误标为“部分扫描”）。

## 标准工作流与硬约束

1. **安装与设备码登录（门禁见 [login-playbook.md](references/login-playbook.md)）**：缺失上游 Skill 时先提示确认安装；支持 `--device-code` 时走 `scripts/device_login.py`（自动传 `--accept-disclaimer`）并用 `scripts/decode_qr.py` 解出浏览器授权链给客户完成；仅旧版回退 `scripts/login.sh --yes`（需客户确认）。登录后核 `whoami` 与 `--json ls`。
2. **包装器命令入口**：
   ```bash
   python3 <skill-path>/scripts/run_with_env.py -- whoami
   python3 <skill-path>/scripts/run_with_env.py -- --json ls [资料]
   python3 <skill-path>/scripts/run_with_env.py -- --json search "关键词"
   python3 <skill-path>/scripts/run_with_env.py -- mkdir|mv|cp|rename|upload|download|share|transfer ...
   ```
   - `LIST_FAIL` / 权限不足 / 非零退出绝不当作空目录。写操作与上传遇业务 JSON 错误（如 `errno=-10`）停止重试并回读，提示核对容量与开放平台权限；`share` 触发潜在计费须单独确认；终端超时先查目标状态再重传；json 解析以 `fs_id`/`server_filename`/`isdir`/`size`/`md5`/`server_mtime` 为准，禁解析人类表格。
3. **全盘 JSONL 扫描**：`python3 <skill-path>/scripts/scan_drive.py --root / --out <out.jsonl> --workers 4 --resume`（支持多 `--root`、`--no-descend`），收敛必查退出码、`.errors` 与 `.done`。
4. **记忆备份边界**：仅环境明确为 `KimiClaw`/`MaxClaw`/`QClaw`/`OpenClaw` 时，方可通过已安装的官方 `baidu-drive` 上游 `scripts/memory-backup.sh` 处理 `backup`/`list`/`restore`（恢复须明确日期，禁默认最新，禁裸 `bdpan` 替代），其它环境明确不支持；本技能亦不越界替代 `alipan-curator` 做高级目录整理。

## 验证与前向测试

运行 `python3 -m unittest tests.test_baidupan_scan` 与 `python3 scripts/audit_skills.py --strict`（验证 JSON 字段归一化、`.errors`/`.done` sidecar、provider 解析与秘密脱敏）；真实网盘写操作仍须走人工确认与回读核验。
