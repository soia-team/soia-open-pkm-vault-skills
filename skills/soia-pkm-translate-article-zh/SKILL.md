---
name: soia-pkm-translate-article-zh
description: 将外文文章按 quick、normal 或 refined 模式翻译成独立中文稿，保持术语一致且不覆盖原文。触发：「翻译这篇」「精翻」「继续润色」
version: 2.0.5
created_at: 2026-07-09 20:56:44
updated_at: 2026-11-18 10:25:00
created_by: claude opus 4.6
updated_by: gemini-4-hydrogen
---

# soia-pkm-translate-article-zh

SOIA 个人知识管理的**加工翻译环节**：把外文文章或 vault 归档稿按 `quick` / `normal` / `refined` 翻译为独立文件（不修改原文，长文自动机械分块并跨块统一术语）。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 快速看懂大意（`quick`） | 整篇直译，速度优先 | `<原文件名>-<语言>版.md` 直译全文 |
| 自然流畅的默认译文（`normal`，默认） | 先定文体/受众/术语表再整篇翻译（长文分块保持术语一致） | 通顺可归档的完整译文 |
| 出版级精翻（`refined`） | 分析 → 翻译 → 审校诊断 → 应用润色 | 诊断说明 + 最终润色全文 |

### 客户如何使用

给出文件路径（如 clip 归档笔记）或直接贴正文，说明目标语言/模式/受众（缺省用 CLI 参数 > 环境变量 > 私有 `config.yml` > 内置 `zh-CN / normal / general`；输入明确且无覆盖冲突时直接运行并回显默认值，回复「继续润色」可从 `normal` 升级进入 `refined` 审校）。

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-translate-article-zh`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。依赖 Python 3 stdlib（`chunk_markdown.py`）；`PyYAML` 为可选增强，不需任何外网翻译 API 或账号凭据。

### 私密信息与中间数据

偏好与明文 `glossary` 术语表仅存 `~/.config/soia-skills/soia-pkm-translate-article-zh/config.yml` 或 `$SOIA_PKM_TRANSLATE_ARTICLE_ZH_CONFIG_FILE`（模板 [assets/config.example.yml](assets/config.example.yml)）；分块临时文件放系统临时目录，绝不覆盖源文件或上传笔记。

### 日志与完成回执

**先落盘后汇报**：汇报采用模式、是否分块（块数与每块词数）、术语表命中数、`refined` 跨块审校结果、译文路径（标明原文件未改）与未翻译图片提醒（不擅改图片文字）。

## 翻译模式与分块规范

1. **三模式区分**：`quick`（「快翻」）不分块不做术语表（长文需提示质量限制）；`normal`（默认）先分析并维护跨任务内的会话术语表（继承 `config.yml` `glossary`）；`refined`（「精翻」/「继续润色」）追加 [精翻审校清单](references/refined-review-checklist.md) 核查跨块人名/术语/风格漂移。
2. **机械分块与双语归档特殊处理**：
   ```bash
   python3 scripts/chunk_markdown.py --file <path.md> [--threshold 4000 --max-words 5000] [--output-dir <tmp>] --json
   python3 scripts/chunk_markdown.py --selftest
   ```
   - 默认待译词数 **>4000** 触发分块（单块 ≤5000，保留完整代码块），全流程见 [分块工作流](references/chunk-workflow.md)。
   - **重要**：clip 归档笔记含「摘要/原文/中文译文/我的看法」，**必须先截取 `## 原文` 到下个 `##` 之间存临时文件后再计词/分块**（防把已有译文算进词数导致误切块）。
3. **落盘与 frontmatter 规范**：写同目录新文件（后缀映射 `zh-CN/zh/zh-Hans -> 中文版`，`en -> 英文版`，`ja -> 日文版`，`ko -> 韩文版`，其它 `<code >版`）；**同名已存在必须先征求覆盖确认**。完整保留原 frontmatter 并仅在末尾追加 `translated_from`、`translated_language`、`translated_at`（不动原 `title`）。

## 验证与前向测试

先用 fixture 或小样本前向验证分块边界、`## 原文` 截取、frontmatter 保留、术语一致性、非覆盖保护与空正文报错（`python3 scripts/chunk_markdown.py --selftest` + `audit_skills.py --strict`）。
