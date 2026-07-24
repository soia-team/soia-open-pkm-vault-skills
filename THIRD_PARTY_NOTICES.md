# THIRD_PARTY_NOTICES

> Last updated: 2026-07-24
> License values are metadata snapshots. Recheck the upstream source before reuse.

## Interface references (source read only; no code copied)

| Upstream | License snapshot | Used by | Relationship |
|---|---|---|---|
| [wnma3mz/wechat_articles_spider](https://github.com/wnma3mz/wechat_articles_spider) | Apache-2.0 | `soia-pkm-clip-wechat-account` | Checked `ArticlesUrls.py` for `searchbiz` / `appmsg` request parameters. |
| [cv-cat/WechatOAApis](https://github.com/cv-cat/WechatOAApis) | NOASSERTION | `soia-pkm-clip-wechat-account` | Checked `utils/wx_utils.py` for `appmsgpublish` / `searchbiz` parameters; no implementation copied. |
| [mcncarl/yichen-skills — yichen-douyin-fetcher](https://github.com/mcncarl/yichen-skills/tree/main/yichen-douyin-fetcher) | Personal Learning and Non-Commercial Use License | `soia-pkm-clip-douyin` | Checked the Playwright interception approach and response field names; the local implementation was independently written and verified. |
| [mcncarl/yichen-skills — yichen-xiaohongshu-fetch](https://github.com/mcncarl/yichen-skills/tree/main/yichen-xiaohongshu-fetch) | Personal Learning and Non-Commercial Use License | `soia-pkm-clip-rednote` | Checked `window.__INITIAL_STATE__` field paths; the local parser was independently written and verified against real pages. |

## Runtime tools and third-party skills

| Upstream | License snapshot | Used by | Relationship |
|---|---|---|---|
| [tickstep/aliyunpan](https://github.com/tickstep/aliyunpan) | Apache-2.0 | `soia-pkm-alipan-drive-ops`, `soia-pkm-alipan-curator` | External CLI invoked at runtime. |
| [baidu-netdisk/bdpan-storage](https://github.com/baidu-netdisk/bdpan-storage) | Apache-2.0 | `soia-pkm-baidu-netdisk-ops` | Official Baidu Drive skill and `bdpan` CLI runtime backend. |
| [mqhe2007/baidupan-cli](https://github.com/mqhe2007/baidupan-cli) | Apache-2.0 | `soia-pkm-baidu-netdisk-ops` | Optional community CLI backend. |
| [trafilatura](https://pypi.org/project/trafilatura/) | Apache-2.0 | `soia-pkm-clip-web` | Optional article body extractor. |
| [readability-lxml](https://pypi.org/project/readability-lxml/) | Apache-2.0 | `soia-pkm-clip-web` | Optional fallback article body extractor. |
| [Telethon](https://github.com/LonamiWebs/Telethon) | MIT | `soia-pkm-clip-x` | Optional Telegram MTProto synchronization dependency. |
| [teng-lin/notebooklm-py](https://github.com/teng-lin/notebooklm-py) | MIT | `soia-pkm-transform-article-notebooklm` and optional routes in the transform family | Unofficial NotebookLM API/CLI invoked at runtime. |
| [nexu-io/open-design](https://github.com/nexu-io/open-design) | Apache-2.0 | Optional routes in the transform family | External rendering engine invoked at runtime. |
| `weread-skills` — [Tencent/WeChatReading](https://github.com/Tencent/WeChatReading) | NOASSERTION | `soia-pkm-library-weread-sync`, `soia-pkm-reading-plan` | Hard dependency for WeChat Reading synchronization; optional enhancement for reading plans. |
| `huashu-weread-advisor` — [alchaincyf/huashu-weread](https://github.com/alchaincyf/huashu-weread) | MIT | `soia-pkm-reading-plan`, `soia-pkm-distill-article-opinion` | Optional methodology reference; third-party skill files are not modified. |

## Online services

| Service | Provider/project | License snapshot | Used by | Relationship |
|---|---|---|---|---|
| WeChat Reading API | Tencent | — | `soia-pkm-library-weread-sync` and related skills | Called through the official `weread-skills` package with the user's API key. |
| `api.fxtwitter.com` | [FxEmbed/FxEmbed](https://github.com/FxEmbed/FxEmbed) | MIT | `soia-pkm-clip-x` | Public API service used to fetch tweet JSON; project code is not distributed. |
| `cdn.syndication.twimg.com` | Twitter/X | — | `soia-pkm-clip-x` | Public fallback endpoint. |
| `mp.weixin.qq.com/cgi-bin/*` | Tencent | — | `soia-pkm-clip-wechat-account` | Reads data owned by the signed-in account; interface references are listed above. |

## Maintenance

- Third-party skills are declared dependencies or references only; this repository does not modify their files.
- NOASSERTION and non-commercial upstreams remain reference-only; do not copy their code.
- Record new upstream links, install commands, or API endpoints here when a skill adds them.
