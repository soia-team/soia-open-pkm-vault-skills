---
name: soia-pkm-clip-web
description: 归档网页、博客文章或公开播客节目到 Obsidian vault；可同时保留 shownotes 与本地音频。触发：「归档这个网页」「clip 这个链接」「存这篇博客或播客」
version: 1.1.1
created_at: 2026-07-02 17:57:11
updated_at: 2026-09-01 12:00:00
created_by: claude opus 4.6
updated_by: codex-gpt-5
---

# soia-pkm-clip-web

`clip` 家族的**通用网页成员**：把博客 / 网页文章沉淀进 vault。

## 客户可读说明

### 这个技能可以做什么

把网页/博客文章归档到 Obsidian vault；网页公开 `PodcastEpisode` 元数据时，也能同时保存 shownotes 与本地音频。文章继续用 readability/trafilatura 抽正文，播客用 JSON-LD 解析，二者都按 clip 家族统一规范落地。当用户说「归档并转 PDF」时，归档后在 Obsidian vault 内优先调用 Obsidian 自带 PDF。

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 完成本技能覆盖的工作 | 读取用户请求、必要上下文和本技能正文流程，执行最小可靠步骤 | 客户会看到 Obsidian/vault 文件变更、终端日志、生成产物路径和最终回执。 |
| 缺少依赖、权限、配置或 key | 停止需要外部状态的动作，明确指出缺什么 | 安装命令、申请地址、配置路径或需要客户确认的问题 |
| 执行完成 | 汇总成功、跳过、失败、文件变更和验证结果 | 一段可复制进工单/日志的完成回执 |

### 客户如何使用

1. 用自然语言说明目标，并提供必要输入：文件、URL、repo、workspace、proposal、vault 或平台账号状态。
2. 能 dry-run 或预览的动作先给预览；涉及删除、覆盖、发送、发布、写远端状态时先征求客户确认。

### 依赖与安装

安装（推荐：装整个领域插件，一次装好本仓全部技能）：

```bash
claude plugin marketplace add soia-team/soia-open-skills
```

```bash
claude plugin install soia-pkm-vault@soia
```

只要这一个技能时，可用 npx 路线。注意技能会落进共享真源 `~/.agents/skills`；若同时装了插件，同一技能会出现两份索引且各自漂移，建议二选一：

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s soia-pkm-clip-web -y
```

配置约定：

```text
~/.config/soia-skills/soia-pkm-clip-web/config.yml
SOIA_PKM_CLIP_WEB_CONFIG_FILE=<custom-config-path>
```

- 如果本技能不需要私有配置，可以不创建 `config.yml`。
- 如果需要 API key、cookie、session、provider home 或本机路径，只能放进私有 `config.yml`、进程环境或 provider 自己的登录态里，不能写进仓库、vault 正文或日志。
- 第三方 skill 只能声明依赖和安装方式，不直接修改第三方 skill 文件。

**WorkBuddy** 的装载单位是角色化专家而不是插件，`npx skills add -a '*'` 覆盖不到它，需要单独安装，见 [docs/install/workbuddy.md](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)。

### 日志与完成回执

每次执行都要让客户看见过程和结果。最低回执格式：

```markdown
完成：<一句话说明本次完成了什么>。

日志摘要：
- started: <检查到的输入/配置/依赖，不打印秘密值>
- processed: <数量或范围>
- created/updated: <数量或路径>
- skipped/failed: <数量和原因>

文件变化：
- <绝对路径或“未改动文件”>

验证：
- <运行过的检查、命令或人工核对点>

问题与下一步：
- <缺 key / 缺依赖 / 需要客户确认 / 建议下一条命令；没有则写“无”>
```

### 私密信息与中间数据

- 分享 URL 只用于本次抓取；持久化前去掉 query/fragment，不把分享标识写进公开仓库、vault 或日志。
- 带 query 的媒体地址只在进程内用于下载，笔记仅保存去参数地址和已下载文件的路径/哈希。
- `.part` 属于临时下载文件；失败时清理，成功时原子替换为最终媒体文件。

## 抓取

- 输入：任意文章 URL（博客 / Substack / Medium / 新闻 / 知乎等）
- 正文抽取：`trafilatura` 或 `readability-lxml` 抽正文（去广告 / 导航），提取标题、作者、发布时间。两者不一定预装：`pip install` 常被 **PEP 668（externally-managed）** 拦截，按宿主规则用 `--break-system-packages` 或专用 `venv` 安装；宿主缺 `agent_browser`/无浏览器时，Cloudflare 类站点（如 Medium）可先用公开 reader 代理（如 `r.jina.ai`）取回 Markdown 作为回退，但要把该来源写进「抓取方式」并标注原站被防护。
- 抓不到正文 → `content_complete: false`，**绝不静默截断**。
- 普通文章仍由 agent 按本节流程执行；播客网页读取并执行 [播客网页归档](references/podcast-capture.md)，用 `scripts/archive_podcast.py` 确定性解析、下载和落地。
- 手机端可用 Obsidian Web Clipper 落到 `<vault-inbox-dir>/`，再由本 skill 迁入。

## 播客与音频

- 页面公开 `PodcastEpisode` JSON-LD 且客户要求音频时，优先使用专用脚本；不针对单个平台写死私有接口。
- shownotes 与逐字稿分开：页面 description 完整只能证明 `content_complete: true`，没有 transcript 时必须写 `transcript_status: not_provided_by_source`。
- 播客音频默认落 `<vault>/_attachments/podcasts/<episode-id>/`，vault 笔记记录可播放嵌入、vault 相对路径、bytes 与 SHA-256；大文件是否进入 Git 由 vault 的本地 exclude、Git LFS 或独立备份策略决定。
- 默认清除分享 query/fragment 后再持久化 canonical URL。带 query 的媒体 URL只在本次下载内存中使用，不写入 vault 或日志。
- 只想核查解析能力或只收 shownotes 时用 `--metadata-only`；客户明确要求音频时，音频下载失败不得把正文笔记包装成完整交付。

针对 JSON-LD、URL 去参数、时长解析、文件命名和 fake-IP/SSRF 门禁的 fixture 回归在 `tests/test_archive_podcast.py`；真实交付还必须用实际节目页和音频容器做端到端复核。

## 抓取质量强制复核

脚本退出码 0 不等于抓取成功——有些站点会把登录墙、导航壳或反爬拦截页当正常响应返回，脚本不会报错。**写入 vault 前必须亲读产物**，核对：标题是否匹配原页面（不是"登录""访问异常"这类站点通用标题）、正文是否为完整文章（不是导航栏/侧边栏堆砌，也不是清一色链接）、字数是否与原文体量大致相符。

失败信号清单（命中任一条即判定失败，不得直接交付）：
- 出现"登录""请先登录""verify you are human"等登录墙/验证关键词
- 正文明显过短（应为长文却只有几十字）
- 正文几乎全是链接、没有实质叙述文字

命中失败信号时换策略（换 `readability-lxml`/`trafilatura` 互为兜底、提示用户手动登录后重试、或如实标 `content_complete: false` 并提醒人工核对原文），而不是把拦截页当正文写进 vault。

## 落地（clip 家族统一规范）

- 路径：`<vault-articles-dir>/<年>/YYYY-MM-DD-<来源>-<作者>-<标题>.md`（来源如 博客 / Substack / Medium）
- frontmatter 同 clip 家族；正文 `## 摘要 / 原文 / 我的看法 / 关联`。
- **非中文正文（`language` 非 zh）**：在 `关联` 前补 `## 中文译文`，意译不直译、像人写的中文、专有名词/产品名/代码保留英文——这条是 clip-web 通用规则，不限于 X 通道。
- **文章 → 长期知识**：若该文提炼出可跨项目复用的概念/模式，可再走 `soia-pkm-extract-vault-knowledge` 沉淀到 20 区（新编号子目录 + 更新主题导航 + 重建地图/验证 Base），回执分开报告「归档」与「已沉淀长期知识」，不得把归档当成已提炼。
- 单篇归档默认不是终点：归档写入成功且正文质量复核通过后，自动把该文件交给 `soia-pkm-organize-article-moc` 做最小整理（摘要/topics、年月归位、**只增量同步受影响的 MOC** 与索引门禁）。单篇任务不得调用会先清空整个 `_MOC` 的全量重建流程。只有用户明确说“仅归档/不要整理”才停在 clip 结果；批量网页必须先列清单，再确认是否批量整理。
- 播客音频默认写入 vault 根的 `_attachments/podcasts/<episode-id>/`，归档笔记必须包含 `## 🎧 收听本地音频` 和 Obsidian 原生 `![[相对路径]]` 播放器。存在本地文件但笔记里只有绝对路径文本时，状态仍是 `audio_embedded: false`，不得宣称 Obsidian 内可听。

### 单篇归档完成门禁

归档回执必须拆开报告：`captured`（文件已落盘）、`organized`（单篇整理是否成功）、`moc_synced`、`map_synced`、`base_verified`。任一后置步骤失败，只能说“已归档、整理未完成”，并给出可重试的文件路径；不能把 clip 成功等同于知识库整理完成。

## 归档后导出 PDF

用户同时要求「转 PDF / 导出 PDF」时，先完成 Markdown 归档、摘要、topics 与月份归位，再读取并执行 **[references/obsidian-pdf-export.md](references/obsidian-pdf-export.md)**。只要目标文件位于 Obsidian vault 内，就优先调用 Obsidian 自带「导出 PDF」；外部 PDF 引擎只能作为明确降级方案。

## 闭环位置

`★clip-web(收) → organize → distill → compose → publish`。


---

## 完成后回执

**交付顺序**：先把文件落盘，再输出下面的回执，不得反过来；不确定的元数据（如作者、发布时间解析失败）在回执里显式标注"未核实"，不编造。

回执包含：

1. **做了什么** — 一句话总结完成的工作。
2. **文件变更** — 列出新建 / 修改 / 移动的文件（完整路径）；未改动文件则说明"未改动文件"。
3. **下一步** — 可选的后续建议（如衔接的下一个 skill）。
