# 多媒体搜索方案与选型（2026-08-02 评估）

## 结论：不要让 `query_vault.py` 单独承担附件搜索

本技能拆成三个角色，避免“脚本声称能搜 PDF/图片，但实际上只搜到文件名”的问题：

1. **Obsidian 交互层**：Omnisearch + Text Extractor 负责 PDF、Office、图片的即时全文搜索。
2. **AI 接入层**：优先通过 `obsidian-mcp-server` 的 `omnisearch` 能力调用同一个索引；没有插件或本地服务时，退回本技能的确定性 Markdown/代码搜索。
3. **证据层**：需要回答附件正文时，按需提取到临时运行目录，返回原文件路径、SHA-256、页码/时间位置、提取方式和命中类型；不覆盖原件，也不把隐式索引写进 vault。

语义搜索只做召回增强，不替代精确搜索、原始附件和来源证据。

## 方案比较

| 方案 | 适合 | 优点 | 限制 |
|---|---|---|---|
| Omnisearch + Text Extractor | Obsidian 内快速找 PDF、Office、图片 | BM25、文件类型过滤、附件索引成熟 | 插件缓存不是证据源；中文需额外验证，索引刷新需可观测 |
| obsidian-mcp-server | AI/Agent 调用 Obsidian 搜索 | 可暴露 Omnisearch 的 BM25、`path:`/`ext:`、PDF/OCR 命中 | 依赖 Obsidian、Local REST API 和本地 HTTP；必须只绑定 loopback 并保护 token |
| pdfmd / OCRmyPDF + Tesseract | PDF 正文、扫描 PDF、图片 | 可自动识别扫描页、保留页码并离线处理 | 需要本机依赖；OCR 误识别和表格布局必须抽样复核 |
| QMD | Markdown 和已提取文本的本地语义召回 | 本地 embedding，语义失败可回退 BM25 | 需要 Bun/模型；不应直接索引未提取的二进制或替代证据 |
| Smart Connections / Open Connections | Obsidian 内的相关笔记发现 | 本地 embedding、使用门槛低 | 语义结果不是精确搜索；不适合作为唯一的文件定位后端 |

## 统一结果合同

每次附件正文查询都要返回以下字段；提取稿仅放在本次运行的临时状态目录，除非用户另行授权持久化：

```yaml
source: <vault-relative-attachment-path>
source_sha256: <sha256>
media_type: pdf | docx | image | audio | video | office
extraction_method: omnisearch | pdftotext | pypdf | python-docx | soffice | tesseract | whisper
hit_kinds: [filename_path, extracted_content, ocr_content, transcript_content]
location: page/slide/sheet/time-range
ocr: true | false
review_status: unreviewed | sampled | verified | stale
```

查询前重新计算哈希；哈希变化时拒绝把旧提取稿当作最新正文。结果必须返回 `source`、`source_sha256`、`extraction_method`、`location` 和 `hit_kind`。

## 分阶段落地

1. **MVP**：安装并验证 Omnisearch + Text Extractor；AI 通过 MCP 的 `omnisearch` 查文件名、路径、PDF/Office/图片正文。
2. **正文证据**：对命中的 PDF/DOCX/图片按需用 `pdfmd`、`pdftotext`、`python-docx`、Tesseract 提取，临时保存并返回哈希和页码。
3. **第三阶段**：补齐 PPTX/XLSX、音频/视频转写；统一页码、工作表和时间戳定位。
4. **可选语义层**：只对 Markdown/已提取文本接入 QMD 或 Smart Connections；采用“关键词/BM25 → 语义召回 → 原文证据复核”，禁止只凭向量结果回答。

## 安全与边界

- 默认本地处理，不上传附件；`private/restricted` 不进入公共索引。
- OCR、转写和视觉描述都不是事实证明；答案要标注工具、置信度和人工核对状态。
- 不把插件缓存、向量库或临时 OCR 文件当作 vault 正文；临时状态可删除并可由哈希重建。
- MCP 服务只监听 `127.0.0.1`，不暴露到局域网；未配置 Local REST API/Omnisearch 时，明确报告“仅本地脚本能力”。
