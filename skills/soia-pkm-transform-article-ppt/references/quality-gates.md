# Quality Gates

验收分为机械门和人工门。两层都通过才算完成。

## 机械门

运行：

```bash
python3 scripts/media_bundle.py validate \
  --manifest <output-dir>/media-manifest.json \
  --visual-reviewed \
  --source-facts-reviewed \
  --strict \
  --json
```

脚本检查：

- 必需产物和 prompt 是否存在。
- PPTX 是否为合法 OOXML、实际页数是否达到计划下限。
- `local_editable` 正式母版是否包含足够比例的可编辑文字/形状页，而不是整套全幅截图。
- 预览目录和素材目录是否仍位于媒体包内部。
- 预览 PNG 数是否与 slide 数一致，逐张 PNG 是否具备完整 chunk、正确 CRC、IDAT/IEND，且至少为 320×180；仅有 PNG 头的占位文件不算渲染证据。
- OOXML 可提取文字中是否出现 placeholder、内部路径、NotebookLM 运行字段。
- `hybrid` 是否同时拥有正式母版和 NotebookLM 版。
- 是否显式完成视觉复核和 source 事实复核。
- 内容计划、Claim Ledger、设计计划和 Contract Card 是否批准且字段完整。
- Signature Proof 的动作、页码和预览是否与 Design Plan 精确对应，或有允许跳过的明确原因。
- content/design 双 Lens 是否都 consent，且没有未解决 blocker/major。
- 正式母版是否经过真实宿主全量渲染；含 CJK 时中文检查是否通过。

脚本不能识别位图内所有错别字和占位符，所以即使通过也不能替代人工检查。

## 人工视觉门

### 全局

- 第一眼能看到整套主判断和受众用途。
- 页面节奏有变化，但网格、页边距、字体和页码稳定。
- 至少 4 种页面轮廓；没有连续 3 页同构卡片。
- 不以单一蓝紫、渐变或大面积装饰背景支撑整套视觉。

### 每页

- 只有一个主判断，2 秒内能找到视觉焦点。
- 中文和英文术语断行自然，无孤立标点、截断和遮挡。
- 表格、流程、箭头和图片方向与语义一致。
- 图片清晰、未拉伸、未裁掉主体，不包含错误文字、数字、logo 或水印。
- 动态内容不会改变固定板式尺寸或推挤相邻元素。

### 内容

- 主体章节和概念覆盖率达到计划要求；概念教程默认至少 80%。
- 完整术语索引可读；宁可拆页，不缩成小字。
- 来源页的作者、链接和发布时间来自 source。
- source 观点、推断和未验证事实有清楚标记。
- 不出现模型名、生成时间、内部 id、下载路径和占位符。

## NotebookLM 特别门

- 下载必须按本次 artifact id 选择。
- 至少查看封面、地图、最密集页、索引页和来源页原图。
- 若一页一张图，回执明确不可编辑；不把 `.pptx` 扩展名等同于可编辑。
- 位图内出现错误时重新生成，不用白框覆盖后声称修复。

## Imagegen 特别门

- 每张素材都有 `used_on` 和 `semantic_job`。
- 查看原图并检查方向、主体、数量和留白。
- 最终中文、数字、表格和来源由 PPT/HTML 排版。
- 素材没有实际进入 deck/infographic 时，从交付清单移除，避免库存堆积。

## OfficeCLI 可选复验门

- `officecli validate <deck.pptx> --json` 无 schema error。
- `officecli view <deck.pptx> issues --json` 的 error 已清零，warning 已处理或解释。
- 修复使用生成文件的副本；不原地覆盖正式母版。
- `validate` 通过只代表 OOXML 结构成立，不能替代编辑性检测、事实核对或人工逐页视觉检查。

## 规划、审稿与宿主门

具体 JSON 字段和工作方式见 [planning-and-review-contracts.md](planning-and-review-contracts.md)。尤其注意：

- 不得在构建结束后反填一份与实际过程不符的 Claim Ledger 或审稿结论。
- Signature Proof 必须指向真实存在并被查看过的预览页。
- 优先使用 PowerPoint/Keynote；只能使用 LibreOffice 时，必须明确记录宿主限制并实际检查 CJK 字形、换行和全量宿主预览。
- 验证脚本通过不等于内容和设计正确；它只证明要求的证据存在且结构自洽。

## 修复循环

1. 定位失败页和失败类型。
2. 回到 slide plan、源 HTML/PPT 代码或图片 prompt 修改。
3. 重新生成受影响产物。
4. 重新渲染全部页面，防止局部修复引入全局漂移。
5. 再跑机械门和人工门。
