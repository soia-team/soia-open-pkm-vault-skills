# 微信公众号批量抓取路线与认证参考

> 本参考承接 [SKILL.md](../SKILL.md) 的三条抓取路线、非官方接口限制、`consent.json` 与 `ret` 错误码细节。

## 一、路线对比与脚本参数

| | 路 A · 官方 API (`fetch_api.py`) | 路 C · MP 后台接口 (`fetch_mp.py`，读历史首选) | 路 B · 登录态 Cookie (`fetch_cookie.py`) |
|---|---|---|---|
| 覆盖范围 | 仅草稿箱「发布」的文章（自 2025-07 起仅限已认证号） | 全部历史（含手动群发老文）；2026-07 实测 `appmsgpublish` 通过 | 全部历史（每页 10 条） |
| 凭据与失效 | `WECHAT_APP_ID` / `WECHAT_APP_SECRET` + IP 白名单 | 地址栏 `WECHAT_MP_TOKEN` + `WECHAT_MP_COOKIE`（几小时过期） | `__biz`/`key`/`pass_ticket`/`appmsg_token` + `Cookie` |
| 子模式 / 限制 | `--dry-run --limit N`；`freepublish` 与 `material` 互补非全量 | 默认不传 `--name`/`--fakeid` 读自己当前号 (`appmsgpublish`)；传参才走 `searchbiz`+`appmsg` | `--dry-run` 仍抓正文；仅作路 C 备选 |

通用参数（三条脚本均支持）：`--vault <path>`、`--out <vault-relative-dir>`（或 `env.OBSIDIAN_GZH_OUT`，缺省写 `Inbox/gzh-articles/<年>/`）、`--account <alias>`、`--config <path|name>`、`--list-accounts`、`--account-name <显示名>`、`--limit N`、`--dry-run`、`--force`、`--sleep <秒>`。

## 二、使用前同意声明（路 B / 路 C）

首次走路 B/C 或声明版本变更时，须向客户展示并确认：

> 本技能部分路线（路 B / 路 C）使用公众号后台非官方接口，非微信官方文档收录，存在 ToS 风险；仅限归档你自己管理的账号，不得用于抓取他人公众号。（声明版本 v1）

确认后写入 `~/.config/soia-skills/soia-pkm-clip-wechat-account/consent.json`：`{"accepted": true, "acceptedAt": "<ISO>", "disclaimerVersion": "v1"}`。拒绝即停止。

## 三、接口字段、凭据抓取与常见错误

### 路 A · 官方 API

- `GET /cgi-bin/token?grant_type=client_credential&appid=&secret=`
- `POST /cgi-bin/freepublish/batchget` 与 `POST /cgi-bin/material/batchget_material`（`type:"news"`, `count<=20`）
- 凭据与 IP 白名单配法同 `soia-media-publish-wechat-draft`。

### 路 C · MP 后台接口

- **取数方法**：登录 `mp.weixin.qq.com` 进编辑/列表页 → F12 网络面板 → 从**浏览器地址栏 URL** 复制 `token`（数字串，非请求中的 `appmsg_token`）与请求头 `Cookie`。
- **响应与限制**：`appmsgpublish` 返回两层 JSON 字符串（`publish_page` → `publish_list[].publish_info` → `appmsgex[]`）；与 `appmsg?action=list_ex`（不含 author）不混用，默认 `--sleep 3` 防 `freq control`。
- **错误码 `base_resp.ret`**：`200003` invalid session（过期重抓）、`200013` freq control（限流暂停）、`200040` invalid csrf token（token 与 Cookie 非同次登录）。

### 路 B · profile_ext

- 请求 `GET /mp/profile_ext?action=getmsg&__biz=&f=json&offset=&count=10&is_ok=1&scene=124&uin=777&key=&pass_ticket=&appmsg_token=&x5=0` + `Cookie`。默认 `--sleep 1.5`。
- 每条 `link` / `content_url` 的正文解析均走 stdlib `html.parser` 解析 `#js_content`；失败标记 `content_complete: false`。
