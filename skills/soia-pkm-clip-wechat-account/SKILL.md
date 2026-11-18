---
name: soia-pkm-clip-wechat-account
description: 批量归档用户自己管理的微信公众号已发文章到 Obsidian vault。支持官方 API、公众号后台接口、登录态 Cookie 三条路线，并按 url 去重。Triggers：「同步我的公众号」「批量拉取我公众号历史文章」「批量归档我的公众号」「导入公众号已发文章」「clip 我的公众号」
version: 2.1.2
created_at: 2026-07-08 14:30:37
updated_at: 2026-11-18 10:05:00
created_by: claude opus 4.6
updated_by: gemini-4-hydrogen
---

# soia-pkm-clip-wechat-account

`clip` 家族的**公众号批量归档成员**：把**用户自己管理的公众号**历史文章拉入 vault 暂存区并按 `url` 去重（与单篇抓取 `soia-pkm-clip-wechat-article` 互补），绝不用于抓取他人账号。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 盘点多账号及路线就绪度 | 运行 `--list-accounts` 脱敏显示各 alias、显示名与 API / 后台 / Cookie 就绪态 | 多账号脱敏清单 |
| 预览待归档历史文章 | 执行 `--dry-run --limit N` 只拉列表并按 vault 已有 `url` 比对去重 | 待新增标题、日期与 URL 预览 |
| 批量归档自己公众号的历史文章 | 按 `--account <alias>` 走指定路线抓取并写 `<出版日期>-公众号-<显示名>-<标题>.md` | 新增/跳过篇数、文件路径与缺口标记 |

### 客户如何使用

- 「先 `--list-accounts` 看看我配置了哪些公众号账号，哪个路线通着。」
- 「用 `--dry-run` 看下 `<alias>` 最近还有几篇没归档进知识库。」
- 「批量同步我 `<alias>` 公众号的历史文章到收件箱目录。」

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-clip-wechat-account`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。纯 Python 3 stdlib 实现。

### 私密信息与中间数据

凭据与多账号文件只存 `${XDG_CONFIG_HOME:-~/.config}/soia-skills/soia-pkm-clip-wechat-account/`（`config.yml`、`config.<alias>.yml`、`accounts/<alias>.yml`、`consent.json`，权限 `0600`，环境变量 `$SOIA_PKM_CLIP_WECHAT_ACCOUNT_CONFIG_FILE` 或兼容 `$SOIA_PKM_CLIP_GZH_CONFIG_FILE`，示例见 `assets/config.example.yml`）；未设 `default_account` 且未传 `--account`/`--config` 时 fail-closed 报错防串号；异常信息自动脱敏 `secret` 与 `access_token`。

### 日志与完成回执

**先全量落盘再回执**：汇报账号/路线、新增/跳过/失败数、落盘路径及 `author` 兜底/`content_complete: false` 等未核实字段；批量抓取仅代表 `captured`，须继续走生命周期管理完成 `organized → MOC/导航 → map → Base`（不适用写 `not_applicable`）。

## 三路线路由与授权门禁

| 路线 | 脚本 | 适用场景与边界 |
|---|---|---|
| 路 A · 官方 API | `scripts/fetch_api.py` | 仅限**已认证号**且只返回草稿箱「发布」的文章（`freepublish` + `material` 互补非全量）；免 `consent` |
| 路 C · MP 后台接口（推荐历史） | `scripts/fetch_mp.py` | 仅需地址栏 `token` + `Cookie`，不传 `--name`/`--fakeid` 默认 `appmsgpublish` 读自己当前号 |
| 路 B · 登录态 Cookie | `scripts/fetch_cookie.py` | `profile_ext` 备选（需 `__biz`/`key`/`pass_ticket`/`appmsg_token` + `Cookie`），`--dry-run` 仍拉正文 |

1. **非官方接口 Consent 门禁**：首次跑路 B/C 或声明版本升级时，须展示非官方 ToS 风险说明并将客户确认写入 `consent.json`（v1）；拒绝即止。
2. **范围确认**：正式抓取前先 `--dry-run --limit 3` 探路报告预计数量级并确认范围（仅客户本次明确说“直接抓”才跳过）。

API 字段、凭据抓取步骤与 `ret` 错误码详见 [路线与认证参考](references/routes-and-auth.md)。

## 落地规范与归档后

- **中转输出**：默认落 `Inbox/gzh-articles/<年>/`（可用 `--out` 或 `env.OBSIDIAN_GZH_OUT` 覆盖），文件名 `<日期>-公众号-<显示名>-<标题>.md`；按 `url` 递归去重，`--force` 才覆盖。
- **Frontmatter**：`tags:[公众号原创, 待归位]`、`source: 公众号自有`、`url`、`title`、`author`、`published_at`、`captured_at`、`route`、`content_complete`、`topics: []`。
- **归档后**：AI 补 30–80 字 `## 摘要` 与 `topics`，随后交 `soia-pkm-organize-article-moc` 归位。

## 验证与前向测试

```bash
python3 -m unittest tests.test_clip_wechat_account
```

离线 fixture 与前向测试覆盖多账号 `config.yml#accounts` / 分账号文件解析、fail-closed 阻断、`--list-accounts` 脱敏、去重与回执字段。
