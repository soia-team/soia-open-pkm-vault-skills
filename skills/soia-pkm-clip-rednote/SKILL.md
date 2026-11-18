---
name: soia-pkm-clip-rednote
description: 将单篇小红书图文或视频笔记归档到 Obsidian vault。触发：「归档这条小红书」「clip 小红书笔记」「存这篇 rednote」
version: 1.0.5
created_at: 2026-07-21 14:40:40
updated_at: 2026-11-18 10:10:00
created_by: claude fable 5
updated_by: gemini-4-hydrogen
---

# soia-pkm-clip-rednote

将单篇小红书（rednote）图文或视频笔记沉淀为 Obsidian vault 笔记；媒体二进制下载至 `~/Downloads/soia-pkm-clip-rednote/<note_id>/`，笔记只记 `media_local_path`，保持知识库轻量。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 归档小红书单篇图文/视频笔记 | 解析完整分享链（须含 `xsec_token`），提取正文、作者、话题标签与互动数写 vault，媒体落本地 Downloads | vault Markdown 笔记与本地媒体路径 |
| 只抓元数据与文案 | `--metadata-only` 跳过下载并在正文 `## 媒体候选（未下载）` 保留直链 | 轻量笔记与可重下候选直链 |
| 重抓或去重 | 按 `note_id` 去重默认 `SKIP`；`--force` 覆盖更新同时保留 `topics`/`people`/`## 摘要` | 更新状态与核验回执 |

### 客户如何使用

- 「归档这条小红书：`<App 复制的完整分享链接>`」（须保留完整 `xsec_token`）
- 「先用 `--metadata-only` 抓这篇小红书文案和直链，不用下载视频」

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-clip-rednote`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。纯 Python 3 stdlib；公开笔记零配置，需登录态时可选配置 `XHS_COOKIE`。

### 私密信息与中间数据

仅接受 `xiaohongshu.com` / `xhslink.com` 域名（**先于 URL 解析校验域名**，防止把 `XHS_COOKIE` 漏发给恶意主机；媒体下载请求不附带 cookie）。可选配置 `$SOIA_PKM_CLIP_REDNOTE_CONFIG_FILE`（兼容 `$SOIA_PKM_CLIP_REDNOTE_ENV_FILE`）或 `~/.config/soia-skills/soia-pkm-clip-rednote/config.yml`（模板见 [assets/config.example.yml](assets/config.example.yml)），环境变量脚本对 cookie/secret 自动脱敏，不写入 vault 或日志。

### 日志与完成回执

先落盘再回执：汇报实际目录（走 `Articles/` 兜底须提示配置正式目录）、vault 笔记与媒体目录（或未下载）、脚本检验及`未核实`字段；落盘只代表 `captured`，默认接生命周期完成 `organized → MOC/导航 → map → Base`。

## 运行机制与规范

1. **路径优先级**：`--vault`/`--articles-dir` > `OBSIDIAN_VAULT`/`OBSIDIAN_ARTICLES` > 私有 `config.yml` > cwd 向上发现 > `Articles/` 兜底（stderr 警告，退出 0）。
2. **抓取与异常门禁**：
   - `python3 scripts/archive_rednote.py <URL> [--force] [--vault <p>] [--articles-dir <d>] [--metadata-only]`
   - 提取 `note_id`（`/explore/`、`/discovery/item/`、`note_id=`），带着 `xsec_token` GET 页面，解析 `window.__INITIAL_STATE__`（`html.unescape` + `undefined -> null` → `noteDetailMap`）；缺失状态报错提示检查登录态或失效 token，**不写半成品**。
   - 视频按 `h264 -> h265 -> av1` 尝试下载，全败记候选继续写文；`--force` 下载失败时若本地已有 `video.mp4` 保留原路径不清空；`interactInfo` 全空/0 标注「互动数据未公开」。
3. **落盘结构**：文件 `<YYYY-MM-DD>-rednote-<作者前20字>-<标题前50字>.md`（同日同作者同题加 `-<note_id 后6位>`），保留原始 `#tag[话题]#` 标签，`tags:[视频摘抄]`、`source: 小红书`；归档后 AI 补 1 句 `## 摘要`、`topics`/`people` 双链，`## 我的看法` **永远留空**。

## 验证与前向测试

改后跑 `audit_skills.py --strict` 及真实端到端/安全前向验证（验证非允许域名如 `evil.example` 在请求前被拒绝、env 脚本脱敏、`media_local_path` 失败回退保留与重复 `SKIP`）。
