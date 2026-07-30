# Media Bundle Contract

普通任务把输出组织成一个媒体包。路径可由用户覆盖；默认使用 source 文件名作为 `<stem>`。

```text
<output-dir>/
├── <stem>-editable.pptx
├── <stem>-notebooklm.pptx          # provider=notebooklm/hybrid 时
├── <stem>-infographic.png          # 请求信息图时
├── assets/
│   └── imagegen/
├── prompts/
│   ├── ppt-local.txt
│   ├── image-01.txt
│   └── ppt-notebooklm.txt          # 使用 NotebookLM 时
├── planning/
│   ├── content-plan.json           # 内容主线与 Claim Ledger
│   ├── design-plan.json            # 设计语言、节奏与 Signature Move
│   └── contract-card.json          # 生成与审稿共享合同
├── previews/
│   ├── editable/slide-*.png
│   └── notebooklm/slide-*.png      # 使用 NotebookLM 时
├── qa/
│   ├── editable-montage.png
│   ├── notebooklm-montage.png      # 使用 NotebookLM 时
│   ├── signature-proof.json
│   ├── critic-content.json
│   ├── critic-design.json
│   └── host-validation.json
├── media-manifest.json
└── media-validation.json
```

`media-manifest.json` 是该媒体包的单一清单，至少包含：

- source 路径、标题、作者、URL、发布时间、章节和概念。
- `main_verdict`、受众、provider、页数和图片数量。
- 每个预期产物的路径、是否必需、编辑性语义。
- 规划时间。时间由运行环境实际读取，不手写未来时间。
- 内容/设计计划、Contract Card、Signature Proof、双 Lens 审稿和宿主验收的预期路径。
- 模板 mode、alias、SHA-256 与隐私合同；不记录严格模板的源文件路径。

新规划写入 manifest schema v3，并要求非空 `request.main_verdict`。v3 增加模板、隐私、存储根和 artifact base 合同；验证器继续兼容 schema v2 的既有质量合同。schema v1 只允许非严格读取并标记为 `legacy`，严格交付校验会拒绝 v1，因此旧包不能通过修改版本号绕过规划、双 Lens 与宿主质量合同。

manifest 不存账号、cookie、token、NotebookLM 下载 URL、用户邮箱或模型身份。Notebook/source/artifact id 仅在确有调试需要时写入用户私有运行日志，不进入幻灯片。

## 命名语义

- `editable`：以可编辑文本、形状、表格和连接线为主。插画可以是位图。
- `notebooklm`：NotebookLM 原生视觉结果。默认按 flattened/image-only 理解，除非检查证实可编辑。
- `infographic`：完成中文排版后的最终图，不是 imagegen 原始素材。
- `assets/imagegen`：无密集文字的视觉部件，不能直接冒充完整信息图。

## Prompt 落盘

每个真正调用的生成路径都要保存 prompt。未调用的 provider 不创建空 prompt。prompt 中不得放登录凭据；包含敏感 source 时由用户决定输出目录是否进入版本控制。

## 规划与 QA 产物

`plan` 会创建七份 JSON 模板，但不覆盖已有文件。它们是可审计中间产物和验收证据，不应出现在幻灯片正文中。字段、状态流和严格验证规则见 [planning-and-review-contracts.md](planning-and-review-contracts.md)。

## Confidential 分层

`privacy.classification=confidential` 时不使用“同包交付”：

- `state_root/runs/<run-id>/`：prompt、规划、预览、QA、manifest 和 validation。
- `output_root/`：最终 PPTX 与用户明确要求的正式交付。
- 最终产物 entry 标记 `base: delivery`；中间证据使用 `base: state`。

两个根目录都必须是绝对路径、互不重叠且位于 Git checkout 之外。完整合同见 [template-and-privacy-contract.md](template-and-privacy-contract.md)。
