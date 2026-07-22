# SOIA Open Skills Catalog

> Generated from `skills/*/SKILL.md` and optional `agents/openai.yaml`.
> Do not edit by hand. Run `python3 scripts/generate_skill_catalog.py`.
> Discoverable by `npx skills add soia-team/soia-open-pkm-vault-skills -l`: 15 skills.

## Source Fields

- `SKILL.md` is the canonical cross-agent instruction file. Capabilities, dependencies, setup, workflow steps, logs, and completion summaries must live there.
- `agents/openai.yaml` is optional UI/catalog metadata for OpenAI/Codex-style surfaces and SOIA registry display: `display_name`, `short_description`, and `default_prompt`.
- Claude Code and generic skills.sh-compatible agents must be assumed to consume `SKILL.md`; do not put required workflow steps only in `agents/openai.yaml`.
- Legacy `metadata.json` files are not used to generate this catalog.

## PKM

| Skill | Description | Default Prompt |
|---|---|---|
| [`soia-pkm-bootstrap-vault-base`](./soia-pkm-bootstrap-vault-base/) | 初始化知识库中立的 Markdown vault：PARA、AGENTS、模板、多 AI 入口和 PKM 闭环 | Use soia-pkm-bootstrap-vault-base: 初始化通用 Markdown 知识库骨架并接入多 AI 与 PKM 闭环 |
| [`soia-pkm-bootstrap-vault-ima`](./soia-pkm-bootstrap-vault-ima/) | 将本地 Markdown vault 单向接入腾讯 ima 知识库 | Use soia-pkm-bootstrap-vault-ima: 将这个 Markdown vault 的指定目录同步到腾讯 ima 知识库并验证检索 |
| [`soia-pkm-bootstrap-vault-obsidian`](./soia-pkm-bootstrap-vault-obsidian/) | 配置 Obsidian 消费端：启用 Bases、CSS snippets 和可选插件 | Use soia-pkm-bootstrap-vault-obsidian: 配置这个 Markdown vault 的 Obsidian、Bases 和 CSS |
| [`soia-pkm-distill-article-opinion`](./soia-pkm-distill-article-opinion/) | 把 Obsidian vault 里收藏的文章「炼」成你自己的观点。读原文 → 苏格拉底式一次抛一个问题 → 你口述回答 → AI 把你的回答整理成「我的看法」段（内容是你的，AI 只帮落文字，绝不替你想、替你写），写完给你回执。也支持主题聚合：把一个 MOC 下多篇文章的观点提炼成一篇综述 | Use soia-pkm-distill-article-opinion: 把 Obsidian vault 里收藏的文章「炼」成你自己的观点。读原文 → 苏格拉底式一次抛一个问题 → 你口述回答 → AI 把你的回答整理成「我的看法」段（内容是你的，AI 只帮落文字，绝不替你想、替你写），写完给你回执。也支持主题聚合：把一个 MOC 下多篇文章的观点提炼成一篇综述 |
| [`soia-pkm-interpret-article-analysis`](./soia-pkm-interpret-article-analysis/) | 对 vault 里 clip 进来的长文/论文，AI 给出解读：内容总览/核心要点/关键启发/批判视角/延伸阅读五段式，产出独立的“原文件名-AI解读.md”，不碰原文的“我的看法”段。distill 苏格拉底提问炼用户观点，interpret 是 AI 解读，帮你判断值不值得深挖。默认快读，说「精读」升级逐节展开 |  |
| [`soia-pkm-library-book-catalog`](./soia-pkm-library-book-catalog/) | 纯本地、幂等地补建待读记录并生成图书馆、阅读记录和按类型总览，不依赖微信读书。 | Use soia-pkm-library-book-catalog: 补建待读记录、重新生成图书馆总览或整理本地书库；只读取和写入 vault，不需要微信读书配置。 |
| [`soia-pkm-library-weread-sync`](./soia-pkm-library-weread-sync/) | 同步微信读书已读书目与划线，并通过微信读书 API 补单本书详情；需要 weread-skills 和 WEREAD_API_KEY。 | Use soia-pkm-library-weread-sync: 同步微信读书书架、已读书目或划线，或补一下指定书的详情；执行前检查 weread-skills + WEREAD_API_KEY。 |
| [`soia-pkm-maintain`](./soia-pkm-maintain/) | Obsidian vault 维护技能（支撑类）——三个工作流：①周维护（lint 四类体检 + 周简报）②全库地图重生成 ③AI 会话日志接入（Claude Code / Codex 双平台）。底层机械脚本纯 Python stdlib / bash，参数化支持任意 vault 路径，不硬编码具体库 | Use soia-pkm-maintain: Obsidian vault 维护技能（支撑类）——三个工作流：①周维护（lint 四类体检 + 周简报）②全库地图重生成 ③AI 会话日志接入（Claude Code / Codex 双平台）。底层机械脚本纯 Python stdlib / bash，参数化支持任意 vault 路径，不硬编码具体库 |
| [`soia-pkm-organize-article-moc`](./soia-pkm-organize-article-moc/) | 整理 Obsidian 文章库——补 frontmatter（topics/captured_at/author）、按主题双链归类、建/更新两级 MOC、按月份归位、补双链。底层调 rebuild_moc.py / backfill 等脚本，上层用 LLM 判断分类。用于激活存量收藏、规整新归档 | Use soia-pkm-organize-article-moc: 整理 Obsidian 文章库——补 frontmatter（topics/captured_at/author）、按主题双链归类、建/更新两级 MOC、按月份归位、补双链。底层调 rebuild_moc.py / backfill 等脚本，上层用 LLM 判断分类。用于激活存量收藏、规整新归档 |
| [`soia-pkm-reading-plan`](./soia-pkm-reading-plan/) | 场景化阅读计划生成器。把一批书（来自文章书单、观点映射或主题）组织成带表格、按真实字数排期的可执行阅读计划。可选用 weread-skills 增强字数/评分/书架核实，缺少时降级估算；可选参考 huashu-weread-advisor 方法论但不依赖它。 | Use soia-pkm-reading-plan: 场景化阅读计划生成器。把一批书组织成带表格、按真实字数排期的可执行阅读计划。可选用 weread-skills 增强字数/评分/书架核实，缺少时降级估算；可选参考 huashu-weread-advisor 方法论但不依赖它。 |
| [`soia-pkm-transform-article-notebooklm`](./soia-pkm-transform-article-notebooklm/) | 用 NotebookLM 把文章转换为试卷、闪卡、脑图、播客、学习笔记等学习类产物，降级为本地 Markdown |  |
| [`soia-pkm-transform-article-ppt`](./soia-pkm-transform-article-ppt/) | 生成可编辑 PPTX、图片素材、信息图和 NotebookLM 对照版 | Use $soia-pkm-transform-article-ppt to turn this article into an editable PPTX media bundle with visual assets and full QA. |
| [`soia-pkm-transform-article-visual`](./soia-pkm-transform-article-visual/) | 把文章转换为长图、信息图、海报、封面、插画等视觉产物。HTML/CSS 截图为本地默认方案，可选 Open Design 或 Codex 图生成 |  |
| [`soia-pkm-transform-obsidian-pdf`](./soia-pkm-transform-obsidian-pdf/) | 用 Obsidian 原生导出把 vault 内 Markdown 笔记导出为 PDF。vault 外文章降级 pandoc/weasyprint |  |
| [`soia-pkm-translate-article-zh`](./soia-pkm-translate-article-zh/) | 三模式翻译技能（quick 直译 / normal 先分析术语受众再译 / refined 审校润色出版级），把长文机械分块保证术语一致，产出独立译文文件，不覆盖原文。 |  |

## Registry Export

Generate v7 SOIA registry manifests from the same sources when needed:

```bash
python3 scripts/generate_skill_catalog.py --registry-out <soia-repo>/runtime/registry/skills
```
