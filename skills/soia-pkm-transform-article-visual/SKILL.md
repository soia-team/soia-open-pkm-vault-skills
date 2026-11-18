---
name: soia-pkm-transform-article-visual
description: 把文章转换为长图、信息图、海报、封面、插画等视觉产物。HTML/CSS 截图为本地默认方案，可选 Open Design 或 Codex 图生成。Triggers：「生成长图」「做成信息图」「转成海报」「生成封面」「做成图片」「export visual」「make infographic」
version: 1.2.4
created_at: 2026-07-16 10:58:46
updated_at: 2026-11-18 10:45:00
created_by: claude opus 4.6
updated_by: gemini-4-hydrogen
---

# soia-pkm-transform-article-visual

将 Markdown / vault 文章（或 URL 先经 clip 归档）转换为长图、信息图、概念图、海报、封面或插画，默认本地 HTML/CSS 无头浏览器截图。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 文章转长图/信息图/概念图/海报/封面 | 按 `visual_dense` 重组核心概念，写 prompt 落盘并用选定 provider 生成高清图 | PNG/JPEG 路径、分辨率与 `view_image` 验收结果 |
| 切换生成引擎（`local` / `open-design` / `codex-image`） | 优先客户指定，按硬依赖就绪情况执行并在报告中写明真实 provider | prompt 路径与真实渲染通道记录 |

### 客户如何使用

说明来源（vault 路径/URL 先 clip）和目标类型（`long_image` 默认 / `infographic` / `concept_map` / `poster` / `cover` / `illustration`），可选指定 provider 与参考图（仅提取版式语法，不抄内容）。

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-transform-article-visual`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。`local` 路径走浏览器截图（zero extra deps）；可选 [open-design](references/provider-open-design.md)（原子操作真源见 `soia-dev-open-design-ops`）或 [codex-image](references/prompt-codex-image.md) 显式选择缺依赖即停止不谎报；配置 `~/.config/soia-skills/soia-pkm-transform-article-visual/config.yml` 或 `$SOIA_PKM_TRANSFORM_ARTICLE_VISUAL_CONFIG_FILE`。

### 私密信息与中间数据

中间 HTML 放系统临时目录并于截图后清理，不读取或记录凭据；Prompt 必须落 `outputs/transform/<YYYY>/<stem>/prompts/`，终稿落同级目录。

### 日志与完成回执

汇报 `source`、`visual_type`、真实 `provider`（如发生降级须明写）、Prompt 与图片路径、像素尺寸及 `view_image` 验收结果。

## 工作流与质量边界

1. 读 [prompt-infographic.md](references/prompt-infographic.md) / [design-prompts.md](references/design-prompts.md) / [prompt-codex-image.md](references/prompt-codex-image.md) 编译并落盘 Prompt，跑机械质量门（[quality-gates.md](references/quality-gates.md)）后生成 PNG，最后必须用 `view_image` 验证 **>50KB、宽 ≥750px、中文可读无截断无乱码**。
2. **修字红线**：位图出现乱码、溢出或重叠时**必须改 Prompt 重新生成**，严禁用 PIL/Canvas/ImageMagick 描字覆盖。
