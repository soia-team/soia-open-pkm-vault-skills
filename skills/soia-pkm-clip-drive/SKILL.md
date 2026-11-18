---
name: soia-pkm-clip-drive
description: 把云盘/本地文档或受控 PDF URL 导入 Obsidian vault，提取可搜索正文并接入整理。Triggers：「导入云盘资料」「下载这些 PDF」「clip 这个文档」「OCR 这批图片」
version: 1.1.1
created_at: 2026-07-02 17:57:11
updated_at: 2026-11-18 10:40:00
created_by: claude opus 4.6
updated_by: gemini-4-hydrogen
---

# soia-pkm-clip-drive

`clip` 家族的**本地与云盘文档成员**：提取 PDF、Office（DOC/DOCX/PPT/XLS）及受控 PDF URL 的正文和元数据进入 vault（原件留 `_附件/`），图片须经显式 OCR 后方标正文可检索。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 导入本地/云盘 PDF、Word、PPT、表格 | 计算 SHA-256、提取可搜索文本并生成带来源元数据的资料/摘抄笔记 | `<vault-resources-dir>/<主题>/` 或文章区 Markdown 与哈希回执 |
| 归档并深度提取受控 PDF URL | `archive_pdf.py --deep --extract` 校验魔数/哈希，发现 arXiv/HTML 论文 PDF 并抽文本 | 原 PDF、`-extracted.txt` 与逐条状态 |
| 处理图片或扫描版 PDF | 严格区分文件名命中与正文命中；仅显式运行 OCR 后标 `ocr` 正文状态 | 提取限制说明或带来源/工具标签的正文笔记 |

### 客户如何使用

- 「把这个文件夹里的 PDF 和 Word 批量提取成知识库笔记，先列清单确认。」
- 「把这个论文链接列表通过 `archive_pdf.py --deep --extract` 归档进知识库。」

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-clip-drive`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。依赖 Python 3 stdlib；按格式可选 `pypdf`/`pdfplumber`、`pdftotext`、`python-docx`；配置 `~/.config/soia-skills/soia-pkm-clip-drive/config.yml` 或 `$SOIA_PKM_CLIP_DRIVE_CONFIG_FILE`。

### 私密信息与中间数据

仅读取用户指定的本地路径或受控 URL，提取临时文本放系统临时目录并于结束后清理，不向外部服务上传私有文档。

### 日志与完成回执

**先落盘后汇报**，并按五段入库合同分别报告 `captured`、`organized`、`moc_synced`、`map_synced`、`base_verified`（详见生命周期 `references/knowledge-intake-five-stage-contract.md`，写 20 区另报地图统计与 `.base` 校验，缺失来源标`未核实`）。

## 提取、URL 归档与索引收口

1. **提取与查询交接**：提取稿必须保留 `source`、`original_path`、`source_sha256`、`extraction_method`（OCR 须标工具与人工核对状态），交 `soia-pkm-query-vault` 检索引导，不直接把二进制当文本读取。
2. **受控 PDF URL 下载 (`archive_pdf.py`)**：
   ```bash
   python3 scripts/archive_pdf.py --url-file <urls> --output-dir <vault-att> --text-dir <vault-txt> --deep --extract --dry-run --json
   ```
   支持 `URL<TAB>filename`，校验 HTTP(S)、体积、%PDF- 魔数与 SHA-256；默认拒绝覆盖（`--force` 才替）；`arXiv abs`/DOI 页面与已验魔数的真实 PDF 分开标注，不包装失败项。
3. **落盘与必经整理**：写入 `20_资料库/` 的目标语义目录**须带唯一编号**，不确定分类停在 Inbox 交生命周期；入文章库调 `rebuild_moc.py --article <path>` 增量更新，凡写 20 区须重建全库地图并用 `vault_index_verify.py` 验证 `.base`。

## 验证与前向测试

```bash
python3 -m unittest discover -s tests -p 'test_archive_pdf.py'
python3 skills/soia-pkm-clip-drive/scripts/archive_pdf.py --help
```

`tests/test_archive_pdf.py` 以本地 HTTP server 前向核验 PDF 魔数、SHA-256、dry-run、arXiv/`citation_pdf_url` 发现及失败隔离。
