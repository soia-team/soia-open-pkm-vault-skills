# THIRD_PARTY_NOTICES

> Last updated: 2026-07-28
> License values are metadata snapshots. Recheck the upstream source before reuse.

## Runtime tools and third-party skills

| Upstream | License snapshot | Used by | Relationship |
|---|---|---|---|
| [teng-lin/notebooklm-py](https://github.com/teng-lin/notebooklm-py) | MIT | `soia-pkm-transform-article-notebooklm` and optional routes in the transform family | Unofficial NotebookLM API/CLI invoked at runtime. |
| [nexu-io/open-design](https://github.com/nexu-io/open-design) | Apache-2.0 | Optional routes in the transform family | External rendering engine invoked at runtime. |
| `weread-skills` — [Tencent/WeChatReading](https://github.com/Tencent/WeChatReading) | NOASSERTION | `soia-pkm-library-weread-sync`, `soia-pkm-reading-plan` | Hard dependency for WeChat Reading synchronization; optional enhancement for reading plans. |
| `huashu-weread-advisor` — [alchaincyf/huashu-weread](https://github.com/alchaincyf/huashu-weread) | MIT | `soia-pkm-reading-plan`, `soia-pkm-distill-article-opinion` | Optional methodology reference; third-party skill files are not modified. |
| `slide-maker` — [addsumtech/slides_maker](https://github.com/addsumtech/slides_maker) | MIT | `soia-pkm-transform-article-ppt` | Methodology reference for source-traced planning, signature proof and independent review. No third-party runtime or component library is bundled. |

## Online services

| Service | Provider | Used by | Relationship |
|---|---|---|---|
| WeChat Reading API | Tencent | `soia-pkm-library-weread-sync` and related skills | Called through the official `weread-skills` package with the user's API key. |

## Maintenance

- Third-party skills are declared dependencies or references only; this repository does not modify their files.
- Record new upstream links, install commands, or API endpoints here when a skill adds them.
