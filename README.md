# SOIA 知识库技能库

[English](README.en.md) · 中文

把散落各处的文章、书、云盘资料收进一个本地 Markdown 知识库，再把它们变成能用的东西——观点、笔记、PPT、长图、PDF。

## 这是什么

`soia-open-pkm-vault-skills` 覆盖个人知识库的完整生命周期。所有技能围绕同一个本地 Markdown vault 协作，形成一条闭环：

```text
采集（网页 / 公众号 / X / 小红书 / 抖音 / GitHub / 云盘 / 微信读书）
    ↓
整理（元数据规范化、主题双链、两级 MOC、书库编目）
    ↓
提炼（AI 解读、苏格拉底式观点提炼、翻译）
    ↓
转换（PPT / 长图 / 信息图 / PDF / 试卷闪卡播客）
    ↓
维护（健康检查、全库地图、阅读计划）
```

知识库是纯本地 Markdown，不锁定任何平台；Obsidian、腾讯 ima 只是可选的消费端。

### 适合什么场景

- 「把这个网页/公众号文章/推文存进我的知识库。」
- 「我云盘里几百个 PDF，导进来整理一下。」
- 「这篇长文值不值得细读？先给我一份解读。」
- 「我读完了但说不出观点，帮我问出来。」
- 「把这篇转成 PPT / 长图 / 试卷。」
- 「同步我的微信读书划线到书库。」
- 「知识库有点乱了，做一次体检和整理。」

### 不负责什么

- 不托管你的知识库。所有内容留在你自己的本地目录，本仓只提供操作技能。
- 不替你写观点。解读类技能输出的是「供你判断的材料」，观点提炼是逐问引导你说出来，不代笔。
- 不保存任何凭据。微信读书、X、阿里云盘等登录态由各自官方流程持有，不进仓库、不进 vault 正文、不进日志。
- 不做环境安装。Obsidian、Playwright 等依赖的安装交给 [soia-open-env-skills](https://github.com/soia-team/soia-open-env-skills)。
- 不碰公司内部资料与治理流程，那些在私有仓。

## 从哪里开始

第一次用，按这个顺序：

| 目标 | 先调用 | 完成标准 |
|---|---|---|
| 从零建知识库 | `soia-pkm-bootstrap-vault-base` | 目录骨架、多 AI 入口与 PKM 闭环就位 |
| 接 Obsidian 用 | `soia-pkm-bootstrap-vault-obsidian` | Bases 启用、配置与样式检查通过 |
| 存第一篇内容 | `soia-pkm-clip-web` | vault 里出现规范化的 Markdown 与元数据 |
| 内容多了要整理 | `soia-pkm-organize-article-moc` | 主题双链与两级 MOC 建立 |
| 定期体检 | `soia-pkm-maintain` | 死链、标签漂移、孤立笔记有报告 |

带 🟡 的技能需要先完成对应平台的登录或申请 API key，技能会在执行前明确告诉你缺什么。

## 技能清单

> **开箱可用**：✅ 装完即可使用 · 🟡 还需申请 API key 或完成第三方登录

| 技能 | 一句话职责 | 开箱可用 |
|---|---|---|
| `soia-pkm-alipan-curator` | 规划并整理阿里云盘资源，产出可复核的馆藏索引与学习规划。 | 🟡 |
| `soia-pkm-alipan-drive-ops` | 执行阿里云盘登录、浏览与文件操作，并为资源整理提供底层能力。 | 🟡 |
| `soia-pkm-baidu-netdisk-ops` | 百度网盘原子操作与只读 JSONL 扫描适配。 | 🟡 |
| `soia-pkm-bootstrap-vault-base` | 初始化平台中立的 Markdown vault 骨架与 PKM 闭环。 | ✅ |
| `soia-pkm-bootstrap-vault-ima` | 把已有 vault 接入腾讯 ima，配置目录监控同步并验证检索。 | 🟡 |
| `soia-pkm-bootstrap-vault-obsidian` | 把已有 vault 配置为 Obsidian 消费端。 | ✅ |
| `soia-pkm-clip-douyin` | 归档单条抖音视频到 Obsidian vault，并保留本地媒体索引。 | ✅ |
| `soia-pkm-clip-drive` | 把云盘/本地的存量资料（PDF/Word/文档）批量导入 Obsidian vault。 | ✅ |
| `soia-pkm-clip-github-repo` | 将 GitHub 开源仓库归档为 Obsidian vault 的项目卡和调研笔记。 | ✅ |
| `soia-pkm-clip-rednote` | 将单篇小红书图文或视频笔记归档到 Obsidian vault。 | ✅ |
| `soia-pkm-clip-web` | 归档网页或博客文章到 Obsidian vault，并按统一规范落地。 | ✅ |
| `soia-pkm-clip-wechat-account` | 批量归档用户自己管理的微信公众号已发文章到 Obsidian vault。 | 🟡 |
| `soia-pkm-clip-wechat-article` | 归档单篇微信公众号文章，含标题、作者、正文与配图。 | ✅ |
| `soia-pkm-clip-x` | 归档 X 推文、thread 或 Article 到 vault。 | 🟡 |
| `soia-pkm-distill-article-opinion` | 苏格拉底式逐问，把你的回答整理成你自己的观点。 | ✅ |
| `soia-pkm-interpret-article-analysis` | 为长文生成独立 AI 解读，帮你判断值不值得细读。 | ✅ |
| `soia-pkm-library-book-catalog` | 纯本地幂等地维护书库、阅读记录与分类总览。 | ✅ |
| `soia-pkm-library-weread-sync` | 同步微信读书已读书目与划线到书库。 | 🟡 |
| `soia-pkm-maintain` | 维护 Obsidian vault 的健康状态、全库地图与 AI 会话日志。 | ✅ |
| `soia-pkm-organize-article-moc` | 将 Obsidian 文章库按元数据、主题双链、月份和两级 MOC 规范化整理。 | ✅ |
| `soia-pkm-reading-plan` | 把书单、主题或观点映射组织成按字数排期的可执行阅读计划，并落为 Obsidian 笔记。 | ✅ |
| `soia-pkm-transform-article-notebooklm` | 用 NotebookLM 将文章转换为学习材料。 | 🟡 |
| `soia-pkm-transform-article-ppt` | 把文章、提纲或主题转换为以可编辑 PPTX 为正式母版的演示媒体包。 | ✅ |
| `soia-pkm-transform-article-visual` | 把文章转换为长图、信息图、海报、封面、插画等视觉产物。 | ✅ |
| `soia-pkm-transform-obsidian-pdf` | 用 Obsidian 原生导出把 vault 内 Markdown 笔记导出为 PDF。 | ✅ |
| `soia-pkm-translate-article-zh` | 按 quick/normal/refined 三档翻译外文文章，不覆盖原文。 | ✅ |

## 安装

推荐装整个领域插件，一次装好本仓全部技能：

```bash
claude plugin marketplace add soia-team/soia-open-skills
```

```bash
claude plugin install soia-pkm-vault@soia
```

Codex 用户：

```bash
codex plugin marketplace add soia-team/soia-open-skills
codex plugin add soia-pkm-vault@soia
```

只要单个技能时可用 npx 路线。注意技能会落进共享真源 `~/.agents/skills`；
若同时装了插件，同一技能会出现两份索引且各自漂移，建议二选一：

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s <技能名> -y
```

## 生态导航

规范真源、全生态技能目录与安装指南见 [soia-team/soia-open-skills](https://github.com/soia-team/soia-open-skills)。
维护本仓技能的完整流程见 [CONTRIBUTING.md](https://github.com/soia-team/soia-open-skills/blob/main/CONTRIBUTING.md)。

## License

MIT License — see [LICENSE](./LICENSE).
