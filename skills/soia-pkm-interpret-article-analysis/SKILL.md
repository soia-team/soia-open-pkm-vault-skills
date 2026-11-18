---
name: soia-pkm-interpret-article-analysis
description: 为 vault 长文或论文生成独立 AI 解读，帮助判断是否值得深挖，且不改原文或代写用户观点。触发：「解读这篇」「精读这篇」「值得细读吗」
version: 2.0.3
created_at: 2026-07-10 09:10:23
updated_at: 2026-11-18 10:15:00
created_by: claude opus 4.6
updated_by: gemini-4-hydrogen
---

# soia-pkm-interpret-article-analysis

SOIA 个人知识管理的**解读环节（选读决策辅助）**：针对 vault 内长文或论文产出独立 AI 解读，帮用户在投入深挖（`distill`）前快速判断价值；绝不改动原文件或代写用户观点。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 快速判断长文/论文是否值得精读 | 快读：生成五段式（每段 2–3 句）结构化解读 | 同目录 `<原文件名>-AI解读.md`，双链回原文 |
| 精读并逐节核查论证链 | 精读：逐节展开论点与证据对应检查，标出跃迁与未明前提 | 深度五段式解读，含明确「原文未明确/需核对」标记 |
| 批量解读（>3 篇） | 先列出待解读清单及主题确认范围，再逐篇落盘并汇总回执 | 清单确认 + 逐篇解读文件与合并回执 |

### 客户如何使用

- 「解读这篇《xxx》，帮我先快速判断值不值得深挖。」
- 「精读这篇论文并逐节核查论证链与边界前提。」
- 「把这个 MOC 下的 5 篇文章列出清单，等我挑出几篇后再解读。」

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-interpret-article-analysis`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。纯文本/LLM 工作流，无脚本或 API 依赖；可选配置放 `~/.config/soia-skills/soia-pkm-interpret-article-analysis/config.yml` 或 `$SOIA_PKM_INTERPRET_ARTICLE_ANALYSIS_CONFIG_FILE`。

### 私密信息与中间数据

仅读取用户指定的本地文章，不改写原文、不向外部上传私有笔记、不接触凭据或账号信息。

### 日志与完成回执

**先落盘后汇报**：汇报定位路径、采用深度（快读/精读）、批量确认情况、「原文未明确/需核对」条数及位置，明确声明原文件（含 `## 我的看法`）未被改动，并给出值不值得切至 `soia-pkm-distill-article-opinion` 的建议。

## 解读边界与规范

1. **与 `soia-pkm-distill-article-opinion` 严格分界**：本技能主语是 **AI**，一次性产出独立 `<原文件名>-AI解读.md`，**严禁**写入或修改原文件的 `## 我的看法`；若用户要求提炼个人立场或讲述个人观点，提示改切 `distill`。也不承担外文翻译（`soia-pkm-translate-article-zh`）、PPT/视觉转化（`soia-pkm-transform-*`）或外部检索验证。
2. **输入与批量确认**：读原文件 `## 原文`（仅摘要时先明示低置信度），绝不读或改 `## 我的看法`。1 篇直出；2–3 篇简述后执行；**>3 篇须先报清单确认范围**。若同名解读已存在，先征求覆盖确认。
3. **两档深度与五段结构**：
   - **快读**（默认）：各段 2–3 句。**精读**（「精读」「深度解读」「逐节核查」）：在批判视角前先核查每节「核心论点 / 支撑证据及出处 / 是否逻辑跳跃 / 未交代前提」，结论融进「批判视角」。
   - **产出模板**：frontmatter 仅写 `interpreted_from` / `interpret_depth (quick|deep)` / `interpreted_at`；正文固定 `# AI 解读：《标题》` → 引用 `> 原文：[[<原文件名>]]` / 深度 / 时间 → `## 内容总览` → `## 核心要点`（4–8 条带出处） → `## 关键启发`（≥3 条：是什么 → 为什么重要 → 怎么用） → `## 批判视角`（≥1 条漏洞/边界/「原文未明确/需核对」，绝不编造） → `## 延伸阅读`（2–4 条带 vault 双链）。
