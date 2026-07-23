# SOIA 知识库技能库

覆盖 Markdown vault 初始化、整理、阅读、提炼、翻译与内容转换的可复用 AI 技能集合。

## 技能目录

| 技能名 | 一句话简介 |
|---|---|
| `soia-pkm-bootstrap-vault-base` | 初始化平台中立的 Markdown vault 骨架、多 AI 入口与知识管理闭环。 |
| `soia-pkm-bootstrap-vault-ima` | 将本地 Markdown vault 接入腾讯 ima，并配置目录监控同步与检索验证。 |
| `soia-pkm-bootstrap-vault-obsidian` | 配置 Obsidian 作为本地 Markdown 知识库的消费端。 |
| `soia-pkm-distill-article-opinion` | 通过苏格拉底式逐问提炼用户对 vault 文章的个人观点。 |
| `soia-pkm-interpret-article-analysis` | 为 vault 长文或论文生成独立 AI 解读，不修改原文或代写用户观点。 |
| `soia-pkm-library-book-catalog` | 纯本地、幂等地维护 Obsidian 书库、阅读记录与分类总览。 |
| `soia-pkm-library-weread-sync` | 将微信读书已读书目、划线与书籍详情同步到 Obsidian 书库。 |
| `soia-pkm-maintain` | 维护 Obsidian vault 健康状态、全库地图与 AI 会话日志。 |
| `soia-pkm-organize-article-moc` | 按元数据、主题双链、月份和两级 MOC 规范整理 Obsidian 文章库。 |
| `soia-pkm-reading-plan` | 将书单、主题或观点组织成按字数排期的可执行阅读计划。 |
| `soia-pkm-transform-article-notebooklm` | 使用 NotebookLM 将文章转换为试卷、闪卡、脑图、播客和学习笔记。 |
| `soia-pkm-transform-article-ppt` | 将文章、提纲或主题转换为以可编辑 PPTX 为母版的演示媒体包。 |
| `soia-pkm-transform-article-visual` | 将文章转换为长图、信息图、海报、封面或插画等视觉产物。 |
| `soia-pkm-transform-obsidian-pdf` | 使用 Obsidian 原生导出将 vault 内 Markdown 笔记转换为 PDF。 |
| `soia-pkm-translate-article-zh` | 将外文文章翻译为术语一致且不覆盖原文的独立中文稿。 |

## 安装

将 `<技能>` 替换为上表中的技能名：

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s <技能> -y
```

例如安装知识库维护技能：

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s soia-pkm-maintain -y
```

## 生态导航

规范真源与全生态目录见 [soia-team/soia-open-skills](https://github.com/soia-team/soia-open-skills)。

## License

MIT License，详见 [LICENSE](./LICENSE)。
