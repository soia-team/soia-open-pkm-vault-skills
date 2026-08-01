# SOIA Open Skills Catalog

> Generated from `skills/*/SKILL.md` and optional `agents/openai.yaml`.
> Do not edit by hand. Run `python3 scripts/generate_skill_catalog.py`.
> Discoverable by `npx skills add soia-team/soia-open-pkm-vault-skills -l`: 30 skills.

## Source Fields

- `SKILL.md` is the canonical cross-agent instruction file. Capabilities, dependencies, setup, workflow steps, logs, and completion summaries must live there.
- `agents/openai.yaml` is optional UI/catalog metadata for OpenAI/Codex-style surfaces and SOIA registry display: `display_name`, `short_description`, and `default_prompt`.
- Claude Code and generic skills.sh-compatible agents must be assumed to consume `SKILL.md`; do not put required workflow steps only in `agents/openai.yaml`.
- Legacy `metadata.json` files are not used to generate this catalog.

## PKM

| Skill | Description | Default Prompt |
|---|---|---|
| [`soia-pkm-alipan-curator`](./soia-pkm-alipan-curator/) | 阿里云盘资源顾问：盘点、整理、生成 Obsidian 馆藏、增量 Excel 总索引与家庭课程导航 | Use soia-pkm-alipan-curator: 盘点或整理阿里云盘，生成 Obsidian 馆藏、分区缓存式增量 Excel 总索引或家庭课程导航，或基于本次用户提供的学情生成学习计划 |
| [`soia-pkm-alipan-drive-ops`](./soia-pkm-alipan-drive-ops/) | 阿里云盘原子操作层：安装/登录 aliyunpan、显式 driveId 双盘操作、目录浏览、移动/重命名/删除、下载上传、容量查询、全盘 JSONL 扫描。作为 curator 的底层依赖 | Use soia-pkm-alipan-drive-ops: 阿里云盘原子操作层：安装/登录 aliyunpan、显式 driveId 双盘操作、目录浏览、移动/重命名/删除、下载上传、容量查询、全盘 JSONL 扫描。作为 curator 的底层依赖 |
| [`soia-pkm-baidu-netdisk-ops`](./soia-pkm-baidu-netdisk-ops/) | 百度官方 bdpan Skill 适配：浏览、搜索、传输、管理与只读 JSONL 扫描 | Use soia-pkm-baidu-netdisk-ops: 通过百度官方 bdpan Skill 登录、浏览或安全操作百度网盘，并在需要时生成只读 JSONL 扫描。 |
| [`soia-pkm-bootstrap-vault-base`](./soia-pkm-bootstrap-vault-base/) | 先预览、再 create-only 初始化 AI-native Markdown vault | Use $soia-pkm-bootstrap-vault-base to preview a create-only AI-native vault scaffold; do not apply it until I approve. |
| [`soia-pkm-bootstrap-vault-ima`](./soia-pkm-bootstrap-vault-ima/) | 将本地 Markdown vault 单向接入腾讯 ima 知识库 | Use soia-pkm-bootstrap-vault-ima: 将这个 Markdown vault 的指定目录同步到腾讯 ima 知识库并验证检索 |
| [`soia-pkm-bootstrap-vault-obsidian`](./soia-pkm-bootstrap-vault-obsidian/) | 先预览再安全合并 Bases、CSS 和可选 link format | Use $soia-pkm-bootstrap-vault-obsidian to preview a safe Obsidian configuration merge; preserve all existing settings and wait for my approval before applying. |
| [`soia-pkm-clip-douyin`](./soia-pkm-clip-douyin/) | 归档单条抖音视频到 Obsidian vault：Playwright 拦截签名 API 拿元数据，MP4 存本地 Downloads，vault 只留轻量笔记。 | Use soia-pkm-clip-douyin: 归档我刚发的这条抖音视频链接到 vault |
| [`soia-pkm-clip-drive`](./soia-pkm-clip-drive/) | 把云盘/本地的存量资料（PDF/Word/文档）批量导入 Obsidian vault。提取文本、生成资料笔记，归入资料库或文章摘抄，再交给 organize 整理 | Use soia-pkm-clip-drive: 把云盘/本地的存量资料（PDF/Word/文档）批量导入 Obsidian vault。提取文本、生成资料笔记，归入资料库或文章摘抄，再交给 organize 整理 |
| [`soia-pkm-clip-github-repo`](./soia-pkm-clip-github-repo/) | 把 GitHub 开源项目仓库一键归档到 Obsidian vault 的「开源项目图书馆」——clone 上游代码（不进 vault）+ 生成/更新项目卡（分类/语言/访问链接/最近提交自动填，用途/状态/stars/我的笔记留人工）+ 起调研笔记骨架 + 双向链接；也支持批量重跑刷新全部项目卡的自动字段。当用户说「... | Use soia-pkm-clip-github-repo: 把 GitHub 开源项目仓库一键归档到 Obsidian vault 的「开源项目图书馆」——clone 上游代码（不进 vault）+ 生成/更新项目卡（分类/语言/访问链接/最近提交自动填，用途/状态/stars/我的笔记留人工）+ 起调研笔记骨架 + 双向链接；也支持批量重跑刷新全部项目卡的自动字段。当用户说「... |
| [`soia-pkm-clip-rednote`](./soia-pkm-clip-rednote/) | 归档小红书（rednote）单篇笔记到 Obsidian vault。基于 stdlib 解析 __INITIAL_STATE__，零第三方依赖；视频/图片下载到本地 Downloads，vault 内只留轻量 Markdown 笔记 | Use soia-pkm-clip-rednote: 归档小红书（rednote）单篇笔记到 Obsidian vault。基于 stdlib 解析 __INITIAL_STATE__，零第三方依赖；视频/图片下载到本地 Downloads，vault 内只留轻量 Markdown 笔记 |
| [`soia-pkm-clip-web`](./soia-pkm-clip-web/) | 把任意网页/博客文章一键归档到 Obsidian vault。用正文抽取（readability/trafilatura）提取标题/正文/作者，按 clip 家族统一规范落地。当用户说「归档并转 PDF」「归档并导出 PDF」「archive and export PDF」时，归档后在 Obsidian vault 内... | Use soia-pkm-clip-web: 把任意网页/博客文章一键归档到 Obsidian vault。用正文抽取（readability/trafilatura）提取标题/正文/作者，按 clip 家族统一规范落地。当用户说「归档并转 PDF」「归档并导出 PDF」「archive and export PDF」时，归档后在 Obsidian vault 内... |
| [`soia-pkm-clip-wechat-account`](./soia-pkm-clip-wechat-account/) | 批量归档用户自己管理的微信公众号已发文章到 Obsidian vault。支持官方 API、公众号后台接口、登录态 Cookie 三条路线，并按 url 去重 | Use soia-pkm-clip-wechat-account: 批量归档用户自己管理的微信公众号已发文章到 Obsidian vault。支持官方 API、公众号后台接口、登录态 Cookie 三条路线，并按 url 去重 |
| [`soia-pkm-clip-wechat-article`](./soia-pkm-clip-wechat-article/) | 归档单篇微信公众号文章到 Obsidian vault：抓取静态 HTML，提取标题、作者、正文、发布时间和配图，按 clip 家族规范落地；需要 PDF 时优先用 Obsidian 导出 | Use soia-pkm-clip-wechat-article: 归档单篇微信公众号文章到 Obsidian vault：抓取静态 HTML，提取标题、作者、正文、发布时间和配图，按 clip 家族规范落地；需要 PDF 时优先用 Obsidian 导出 |
| [`soia-pkm-clip-x`](./soia-pkm-clip-x/) | 归档 X/Twitter 推文、thread、Article 到 Obsidian vault。基于 fxtwitter API，单条零配置；可选同步 Telegram 收藏。需要 PDF 时优先用 Obsidian 导出 | Use soia-pkm-clip-x: 归档 X/Twitter 推文、thread、Article 到 Obsidian vault。基于 fxtwitter API，单条零配置；可选同步 Telegram 收藏。需要 PDF 时优先用 Obsidian 导出 |
| [`soia-pkm-distill-article-opinion`](./soia-pkm-distill-article-opinion/) | 把 Obsidian vault 里收藏的文章「炼」成你自己的观点。读原文 → 苏格拉底式一次抛一个问题 → 你口述回答 → AI 把你的回答整理成「我的看法」段（内容是你的，AI 只帮落文字，绝不替你想、替你写），写完给你回执。也支持主题聚合：把一个 MOC 下多篇文章的观点提炼成一篇综述 | Use soia-pkm-distill-article-opinion: 把 Obsidian vault 里收藏的文章「炼」成你自己的观点。读原文 → 苏格拉底式一次抛一个问题 → 你口述回答 → AI 把你的回答整理成「我的看法」段（内容是你的，AI 只帮落文字，绝不替你想、替你写），写完给你回执。也支持主题聚合：把一个 MOC 下多篇文章的观点提炼成一篇综述 |
| [`soia-pkm-extract-vault-knowledge`](./soia-pkm-extract-vault-knowledge/) | 安全提炼可复用知识，同时保留原始证据、来源链接和审计边界 | Use $soia-pkm-extract-vault-knowledge to extract reusable knowledge from these vault sources without moving or rewriting the evidence. |
| [`soia-pkm-interpret-article-analysis`](./soia-pkm-interpret-article-analysis/) | 为 vault 长文或论文生成独立 AI 解读，帮助判断是否值得深挖，且不改原文或代写用户观点 |  |
| [`soia-pkm-library-book-catalog`](./soia-pkm-library-book-catalog/) | 纯本地、幂等地补建待读记录并生成图书馆、阅读记录和按类型总览，不依赖微信读书。 | Use soia-pkm-library-book-catalog: 补建待读记录、重新生成图书馆总览或整理本地书库；只读取和写入 vault，不需要微信读书配置。 |
| [`soia-pkm-library-weread-sync`](./soia-pkm-library-weread-sync/) | 同步微信读书已读书目与划线，并通过微信读书 API 补单本书详情；需要 weread-skills 和 WEREAD_API_KEY。 | Use soia-pkm-library-weread-sync: 同步微信读书书架、已读书目或划线，或补一下指定书的详情；执行前检查 weread-skills + WEREAD_API_KEY。 |
| [`soia-pkm-log-agent-sessions`](./soia-pkm-log-agent-sessions/) | 安全接入最小化 AI 会话改动快照，不保存完整对话 | Use $soia-pkm-log-agent-sessions to preview a safe session-log integration for this vault; do not change my agent config until I approve. |
| [`soia-pkm-maintain-vault-health`](./soia-pkm-maintain-vault-health/) | 只读检查 vault 健康，并按授权重建地图或周报 | Use $soia-pkm-maintain-vault-health to audit this vault without changing notes, then summarize structural risks. |
| [`soia-pkm-manage-vault-lifecycle`](./soia-pkm-manage-vault-lifecycle/) | 先生成 manifest，再安全分流工作台、证据、知识与归档 | Use $soia-pkm-manage-vault-lifecycle to plan this vault reorganization without deleting or moving anything until I confirm. |
| [`soia-pkm-organize-article-moc`](./soia-pkm-organize-article-moc/) | 整理 Obsidian 文章库——补 frontmatter（topics/captured_at/author）、按主题双链归类、建/更新两级 MOC、按月份归位、补双链。底层调 rebuild_moc.py / backfill 等脚本，上层用 LLM 判断分类。用于激活存量收藏、规整新归档 | Use soia-pkm-organize-article-moc: 整理 Obsidian 文章库——补 frontmatter（topics/captured_at/author）、按主题双链归类、建/更新两级 MOC、按月份归位、补双链。底层调 rebuild_moc.py / backfill 等脚本，上层用 LLM 判断分类。用于激活存量收藏、规整新归档 |
| [`soia-pkm-query-vault`](./soia-pkm-query-vault/) | 只读搜索 vault、需求与代码，并区分当前、稳定、证据与历史来源 | Use $soia-pkm-query-vault to search my vault for this question, requirement, or code symbol with cited paths, without changing any files. |
| [`soia-pkm-reading-plan`](./soia-pkm-reading-plan/) | 场景化阅读计划生成器。把一批书（来自文章书单、观点映射或主题）组织成带表格、按真实字数排期的可执行阅读计划。可选用 weread-skills 增强字数/评分/书架核实，缺少时降级估算；可选参考 huashu-weread-advisor 方法论但不依赖它。 | Use soia-pkm-reading-plan: 场景化阅读计划生成器。把一批书组织成带表格、按真实字数排期的可执行阅读计划。可选用 weread-skills 增强字数/评分/书架核实，缺少时降级估算；可选参考 huashu-weread-advisor 方法论但不依赖它。 |
| [`soia-pkm-transform-article-notebooklm`](./soia-pkm-transform-article-notebooklm/) | 用 NotebookLM 将文章转换为学习材料 |  |
| [`soia-pkm-transform-article-ppt`](./soia-pkm-transform-article-ppt/) | 生成可编辑 PPTX，支持固定模板保真与机密本地隔离 | Use $soia-pkm-transform-article-ppt to turn this source into an editable PPTX with source tracing, fixed-template fidelity when requested, confidential local isolation, dual-lens review, and host-render validation. |
| [`soia-pkm-transform-article-visual`](./soia-pkm-transform-article-visual/) | 把文章转换为长图、信息图、海报、封面、插画等视觉产物。HTML/CSS 截图为本地默认方案，可选 Open Design 或 Codex 图生成 |  |
| [`soia-pkm-transform-obsidian-pdf`](./soia-pkm-transform-obsidian-pdf/) | 用 Obsidian 原生导出把 vault 内 Markdown 笔记导出为 PDF。vault 外文章降级 pandoc/weasyprint |  |
| [`soia-pkm-translate-article-zh`](./soia-pkm-translate-article-zh/) | 三模式翻译技能（quick 直译 / normal 先分析术语受众再译 / refined 审校润色出版级），把长文机械分块保证术语一致，产出独立译文文件，不覆盖原文。 |  |

## Registry Export

Generate v7 SOIA registry manifests from the same sources when needed:

```bash
python3 scripts/generate_skill_catalog.py --registry-out <soia-repo>/runtime/registry/skills
```
