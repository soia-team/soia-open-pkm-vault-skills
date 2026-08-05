---
name: soia-pkm-clip-drive
description: 把云盘/本地的存量资料（PDF/Word/表格/演示文稿/文档）批量导入 Obsidian vault。提取文本、生成资料笔记，归入资料库或文章摘抄，再交给 organize 整理；图片正文需显式 OCR。Triggers：「导入云盘资料」「把这批 PDF 导进来」「clip 这个文档」「整理云盘」「OCR 这批图片」
version: 1.0.2
created_at: 2026-07-02 17:57:11
updated_at: 2026-08-02 15:20:00
created_by: claude opus 4.6
updated_by: gpt-5
---

# soia-pkm-clip-drive

`clip` 家族的**云盘成员**：把网盘 / 本地的存量资料（PDF、DOCX 等）导入 vault。区别于抓网页，它处理**本地 / 云盘文件**。

## 客户可读说明

### 这个技能可以做什么

把云盘/本地的存量资料（PDF/Word/表格/演示文稿/文档）批量导入 Obsidian vault。提取文本、生成资料笔记，归入资料库或文章摘抄，再交给 organize 整理。图片不能仅凭文件名当作正文，需用户明确要求并具备 OCR 后端。

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
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s soia-pkm-clip-drive -y
```

配置约定：

```text
~/.config/soia-skills/soia-pkm-clip-drive/config.yml
SOIA_PKM_CLIP_DRIVE_CONFIG_FILE=<custom-config-path>
```

- 如果本技能不需要私有配置，可以不创建 `config.yml`。
- 如果需要 API key、cookie、session、provider home 或本机路径，只能放进私有 `config.yml`、进程环境或 provider 自己的登录态里，不能写进仓库、vault 正文或日志。
- 第三方 skill 只能声明依赖和安装方式，不直接修改第三方 skill 文件。

**WorkBuddy** 的装载单位是角色化专家而不是插件，`npx skills add -a '*'` 覆盖不到它，需要单独安装，见 [docs/install/workbuddy.md](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)。

### 日志与完成回执

捕获只是五段入库合同的 `captured` 阶段；单文件默认继续交给 `soia-pkm-manage-vault-lifecycle` 完成 `organized → MOC/导航 → map → Base`，并在回执中逐项给出 `pass` 或 `not_applicable`。合同详见生命周期技能的 `references/knowledge-intake-five-stage-contract.md`。

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

## 处理

- 输入：文件路径 / 目录（PDF、DOC/DOCX、PPT/PPTX、XLS/XLSX、TXT、Markdown；图片需显式 OCR）
- 提取：PDF 用 `pypdf`/`pdfplumber` 或等价工具，DOCX 用 `python-docx` 或等价工具，Office 旧格式先转换；原文件留到 `_附件/`。图片 OCR 结果必须标记 `ocr`、工具和人工核对状态。
- 输出给查询技能：提取稿保留 `source`、`original_path`、`source_sha256`、`extraction_method`；然后由 `soia-pkm-query-vault` 搜索提取稿，不直接解析二进制正文。
- 大批量：目录批处理，每个文件 → 一篇笔记。
- 提取与落地当前由 agent 按本节流程手工执行（专用批量导入脚本待补充到本 skill 的 `scripts/`）。

## 落地

- 资料 / 参考类 → `<vault-resources-dir>/<主题>/`；文章类 → `<vault-articles-dir>/`（由配置或 CLI 参数决定）。落到 `20_资料库/` 时，目标语义目录必须带唯一编号，不能把新资料直接堆在根目录；不确定分类先停在 Inbox 或交生命周期技能生成 manifest。
- frontmatter：`tags:[资料]` 或 `[文章摘抄]`、`source: 云盘/pdf`、`original_path`、`captured_at`、`topics:[]`。
- 导入后**必走 `organize`**：云盘资料通常量大又杂，靠 organize 分类 / 建 MOC / 去重。只要新建了 20 区文件，必须按 `soia-pkm-maintain-vault-health/references/index-sync-contract.md` 重建 `OB知识库地图.md`，并用 `vault_index_verify.py` 验证相关 Base；附件正文提取不等于索引已更新。

## 闭环位置

`★clip-drive(收) → organize（云盘资料尤其依赖整理） → distill → …`。


---

## 完成后回执

**交付顺序**：先把文件落盘，再输出下面的回执，不得反过来；不确定的元数据（如原文档来源信息缺失）在回执里显式标注"未核实"，不编造。

回执包含：

1. **做了什么** — 一句话总结完成的工作。
2. **文件变更** — 列出新建 / 修改 / 移动的文件（完整路径）；未改动文件则说明"未改动文件"。
3. **下一步** — 可选的后续建议（如衔接的下一个 skill）。
4. **索引同步** — 若写入 20 区，列出地图 `updated`、文件/目录统计、Base 根路径验证；没有 Base 时明确记录未配置。
