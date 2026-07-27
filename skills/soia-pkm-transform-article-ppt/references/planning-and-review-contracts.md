# Planning and Review Contracts

本页定义正式母版在生成前后的轻量质量合同。它吸收内容追踪、设计独特性、双 Lens 审稿和真实宿主验收的做法，但不依赖第三方虚拟环境、渲染器或组件库。

## 1. 先生成合同模板

```bash
python3 scripts/media_bundle.py plan \
  --article <article.md> \
  --out-dir <output-dir> \
  --provider local_editable \
  --audience "<受众>" \
  --purpose "<告知、教学、决策或行动>" \
  --delivery-context "<现场讲解、自读或混合>" \
  --language "zh-Hans" \
  --review-mode standard \
  --slide-count 16 \
  --image-count 0 \
  --main-verdict "<一句主判断>"
```

命令除 `media-manifest.json` 外，还会创建七份 JSON 模板。已存在的模板不会被覆盖；`media-manifest.json` 会按新参数重建。重跑后若 `main_verdict` 等合同已经变化，必须同步更新批准过的计划，严格验证会拒绝 manifest 与旧计划并存的分裂状态。

## 2. 内容计划与 Claim Ledger

编辑 `planning/content-plan.json`：

- `status`：内容主线确认后改为 `approved`。
- `main_verdict`：整套只服务一个主要判断。
- `claim_ledger`：逐条记录会进入页面的数字、日期、名称、引语、归因和关键结论。
- `narrative_arc`：说明判断展开顺序。
- `slide_plan`：每页至少写标题、页面任务和 source anchor；总数不得低于计划页数减 2。
- `open_questions`：仍未解决的问题，不得伪装成事实。

Claim Ledger 每行使用：

```json
{
  "claim": "Cache 命中会跳过重复计算",
  "source_anchor": "## Prompt Cache",
  "status": "source-confirmed"
}
```

`status` 只能是：

- `source-confirmed`：原文直接支持；必须有 `source_anchor`。
- `inference`：由原文推导；必须有 `source_anchor`，页面需标明推断性质。
- `unverified`：尚未证实；必须增加 `treatment: label | exclude | verify`。

## 3. 设计计划与 Signature Proof

编辑 `planning/design-plan.json`：

- `design_language`：说明整套视觉语言，不写空泛的“简洁高级”。
- `boldness`：通常用 `balanced+`；保守场景可用 `conservative`。
- `signature_move`：一个与内容结构绑定的记忆动作，不是渐变、大数字或装饰图。
- `signature_slides`：该动作承担结构作用的页码。
- `semantic_colors`：颜色角色映射，例如主线、证据、风险、行动。
- `slide_shapes`：8 页以上至少使用 4 种页面轮廓。
- `rhythm_map`：记录页面密度、背景和情绪节奏。

先生成并渲染至少一张 signature slide，再填写 `qa/signature-proof.json`：

```json
{
  "status": "passed",
  "signature_move": "把缓存边界画成一道可穿越的门",
  "slides": [5],
  "preview_paths": ["previews/editable/slide-05.png"],
  "reason": ""
}
```

`signature_move` 必须与 Design Plan 完全一致；`slides` 必须逐一对应主交付 deck 的 `preview_dir` 中的 `slide-N.png`，而且预览必须是结构完整、CRC 正确、尺寸合理的 PNG。不能引用素材目录或另一套 deck 的同名图片代替渲染证据。只有 `boldness=conservative` 或 1–2 页极小任务可以 `status=skipped`，并写明 `reason`。

## 4. Contract Card

`planning/contract-card.json` 是生成者和审稿者共享的最小合同，必须声明：

- source、受众、用途、使用场景与语言；
- 正式母版的编辑性；
- review mode；
- 本次真实交付范围。

内容或设计改变后同步更新 Contract Card，避免审稿者按旧目标评判新文件。

## 5. 双 Lens 审稿

分别填写：

- `qa/critic-content.json`：检查 source fidelity、Claim Ledger、主判断、结构、遗漏和误导。
- `qa/critic-design.json`：检查焦点、节奏、层级、可读性、页面多样性和 signature move 是否真正落地。

审稿可以由独立 agent 完成；宿主没有多 agent 能力时，必须分两次独立复核并保留两个 Lens 的结果。正式交付要求：

- 两份 `verdict` 都是 `consent`；
- 两份都记录 `reviewer`，并设置 `independent_of_builder: true`；
- `round >= 1`；
- `blockers` 与 `majors` 都为空；
- `advisories` 可以保留，但在回执中说明是否接受。

`standard` 是默认档，发现问题就修复并复审，最多建议两轮；重要公开演讲、投标、教学母版或高风险事实使用 `thorough`，最多建议三轮。任何档位都不能用轮数上限掩盖未解决的 blocker/major。

## 6. PowerPoint / Keynote 宿主验收

LibreOffice 适合自动化预检，但不能作为中文 PPTX 的唯一视觉真相。最终版本优先在 Microsoft PowerPoint 或 Apple Keynote 打开并渲染；只能使用 LibreOffice 时，必须额外检查 CJK 字形和换行。

填写 `qa/host-validation.json`：

```json
{
  "status": "passed",
  "host": "microsoft_powerpoint",
  "preview_dir": "previews/editable",
  "rendered_slide_count": 16,
  "cjk_checked": true,
  "cjk_passed": true,
  "notes": "逐页检查中文、字体替换、断行和图片裁切"
}
```

`host` 只能使用 `microsoft_powerpoint`、`apple_keynote` 或 `libreoffice`；`preview_dir` 必须与正式母版在 manifest 中声明的 `preview_dir` 完全一致，并指向由该宿主实际渲染的 `slide-*.png`，不能借 NotebookLM 辅助版或素材目录代替。预览必须能解码且至少为 320×180，数量、`rendered_slide_count` 与正式母版实际页数必须一致；source 或目标语言含 CJK 时，`cjk_checked` 和 `cjk_passed` 都必须为布尔值 `true`。只能使用 LibreOffice 时，`notes` 不得为空，并在交付回执中明确宿主限制。

## 7. 最终验证

```bash
python3 scripts/media_bundle.py validate \
  --manifest <output-dir>/media-manifest.json \
  --visual-reviewed \
  --source-facts-reviewed \
  --strict \
  --json
```

新建媒体包使用 manifest schema v2；验证器仅在非严格模式下读取 v1 历史媒体包并标记为 `legacy`，严格交付验收拒绝 v1。严格验证会同时检查 PPTX、预览、prompt、规划合同、Signature Proof、双 Lens 结论和宿主验收。修复后重新渲染全套页面并重跑验证，不得只修改 JSON 让门变绿。
