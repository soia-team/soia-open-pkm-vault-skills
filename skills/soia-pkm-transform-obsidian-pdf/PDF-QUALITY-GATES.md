# PDF Quality Gates

本文件只负责判断 Markdown/vault 文章是否导出了合格 PDF；它不是视觉长图或 PPT 的质量门。

## 必检项

```bash
pdfinfo <output.pdf>
pdftoppm -f 1 -l 1 -png -r 144 <output.pdf> /tmp/pdf-preview
```

- 文件存在且大于 10KB。
- `pdfinfo` 可读，Pages ≥ 1。
- vault 内文章使用 `obsidian-native` 时，Creator 必须包含 `Chromium`，或 Producer 必须包含 `Skia/PDF`。
- 如果 Creator/Producer 显示 `wkhtmltopdf`、`Qt`、`pandoc` 或其他浏览器打印工具，provider 必须标记为 `pandoc` / `weasyprint` / `browser-fallback`，不能冒充 Obsidian 原生导出。
- 首页和至少一页正文预览：中文正常、图片存在、没有全黑页、裁切、严重溢出或图片小到无法辨认。
- 页数要与原文容量大致匹配；不能把全文误压成几页摘要。

## 回执要求

必须列出 source、真实 provider、PDF 路径、页数、文件大小、Creator/Producer，以及首页和正文页的视觉检查结果。
