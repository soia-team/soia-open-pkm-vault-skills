---
name: soia-pkm-clip-x-profile
description: 面向公开 X 账号的有限范围检索与研究：采集帖子窗口，按时间、关键词、主题、媒体、模型线索和内容条件筛选，输出账号概览、时间段总结、主题分析与可审计结果，并支持将明确选定的结果交给下游技能继续处理。
version: 0.3.0
created_at: 2026-08-02 12:00:00
updated_at: 2026-08-02 14:00:00
created_by: gpt-5.6-sol
updated_by: gpt-5.6-sol
---

# soia-pkm-clip-x-profile

## 客户可读说明

### 这个技能可以做什么

研究公开 X 账号的有限帖子窗口：先采集，再按范围和条件检索，最后输出摘要、分类清单或下游处理输入。已知账号用脚本；未知账号先做候选发现，再进入账号研究。

### 客户如何使用

先确认四项：账号/候选博主、时间或最新条数、关键词/主题/证据条件、产物类型。默认只做研究摘要，不自动生成图片；自然语言“最近一周/一个月”先换成明确的 CST 日期。

常用脚本入口：

```bash
python3 scripts/profile_x.py https://x.com/<handle> \
  --limit <N> --since <YYYY-MM-DD> --until <YYYY-MM-DD> \
  --query <term> --output-mode summary --output <run-dir>
```

重复 `--query` 默认 OR，需同时命中时加 `--query-mode all`；`--topic` 是别名。完整参数和输出字段见 [研究契约](references/research-contract.md)，可复用命令见 [查询配方](references/query-recipes.md)。

### 依赖与安装

- Python 3 标准库；网络模式访问 `api.fxtwitter.com`，离线模式使用 `--source-json`。
- 不读取 X Cookie、登录态或私密内容。
- image 不是默认依赖；只有明确选择 `image-prompts/all` 才进入下游 image 技能。

## 渐进式执行

1. **L0 范围**：确认账号/候选、窗口、筛选条件和产物；信息不足先回显假设。
2. **L1 采集**：有限分页，先 `--dry-run`，记录 fetched、分页和停止原因。
3. **L2 研究**：写 `summary.md`、`filtered.json`、`classification.yml`，保留帖子 URL、时间和证据。
4. **L3 下游**：客户明确需要时才写 `image-prompts.yml`/`prompts/`，再交给 `soia-media-generate-article-image` 做位图和视觉验收。

## 路由原则

- **账号总结**：只选 `summary`，不编译 Prompt。
- **时间/主题检索**：用 `--since/--until`、`--query/--topic`、`--category`、`--has-media/--has-alt` 组合。
- **模型/提示词研究**：先输出研究结果；只有明确下游转换时才用 `--output-mode image-prompts`。
- **未知博主发现**：先用 X 搜索或 Web 搜索找候选账号/帖子，记录来源和入选理由，再对候选账号运行本技能；本脚本不冒充全网搜索。

## 边界与交付

`latest-window` 不等于账号历史全量；`all` 也受 `--max-pages` 限制。Prompt Deck 不是位图验收，GPT2 只是来源模型线索，不是新 preset。输出目录、证据保留、失败回执和 image 导入字段见 [研究契约](references/research-contract.md) 与 `soia-open-media-content-skills/skills/soia-media-generate-article-image/references/prompt-x-profile-import.md`。

## 前向测试

三个真实场景和验收标准见 [三场景前向测试](references/forward-test-three-scenarios.md)；`xiaoxiaodong01` 只是其中一个回归样例，不是默认账号。

## 日志与完成回执

每页输出 `page / received / added / total`。回执必须包含账号/候选、范围、条件、fetched、selected、分类、GPT2/ALT、覆盖完整性、分页上限和产物路径；不得把“Prompt 已编译”写成“图片生成通过”。

## 私密信息与中间数据

run bundle 放在客户指定的临时或正式输出目录，不放入仓库、vault 根或 `~/.codex/generated_images`。公共仓库只提交脚本、契约和离线测试，不提交真实账号抓取结果、ALT、provider 缓存或生成图片。
