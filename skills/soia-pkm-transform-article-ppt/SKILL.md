---
name: soia-pkm-transform-article-ppt
description: 把文章、提纲或主题转换为以可编辑 PPTX 为正式母版的演示媒体包，并支持外置固定模板与机密内容本地隔离。触发：「做 PPT」「生成 PPTX」「转成课件」「按公司模板做周报」
version: 2.3.2
created_at: 2026-07-16 10:58:46
updated_at: 2026-08-05 14:40:00
created_by: claude opus 4.6
updated_by: claude-opus-5
dependencies:
  optional: [soia-dev-open-design-ops, soia-dev-officecli-ops]
---

# soia-pkm-transform-article-ppt

把一份 source 转换为可讲、可改、可复验的 PPT 媒体包。默认正式母版是**可编辑 `.pptx`**；视觉素材、信息图和 NotebookLM deck 用来增强理解与展示，不替代内容可编辑性。

## 客户可读说明

### 这个技能可以做什么

| 产物 | 默认角色 | 交付要求 |
|---|---|---|
| 可编辑 PPTX | 正式母版 | 文字、结构和主要图形可修改；完整覆盖 source 主线 |
| 封面图 / 插画 / 背景 | PPT 视觉素材 | 无密集中文；由 imagegen 或等价图片能力生成 |
| 信息图 / 长图 | 独立传播素材，可选 | 中文文字由 HTML/CSS 或 PPT 排版，图片模型只供视觉部件 |
| NotebookLM PPTX | 视觉对照版，可选 | source-grounded；明确标注通常是一页一张图、不易编辑 |
| 预览与 QA | 验收证据 | 全部页面渲染、montage、溢出检查、人工逐页复核 |
| 规划与审稿合同 | 质量证据 | Claim Ledger、内容/设计计划、Contract Card、Signature Proof、双 Lens 审稿和宿主验收 |
| `media-manifest.json` | 生成清单 | 记录 source、provider、预期文件和实际验证，不写登录凭据 |

用户只说「PPT」时，默认交付 `.pptx`。只有用户明确要求兼容旧版 PowerPoint 时才额外转换 `.ppt`，并验证转换结果；不要把 `PPT` 口语请求误解为必须输出旧二进制格式。

### 客户如何使用

提供一种输入即可：文章路径、URL、Markdown、提纲、数据表或主题。最好补充受众、用途、页数、风格和是否需要 NotebookLM。

```text
把 <article.md> 做成给小白讲的 16 页 PPT，生成 3 张无字插画素材
把这个 URL 归档后做成可编辑 PPTX，并用 NotebookLM 再做一版对比
把这篇技术文章做成分享课件，同时给一张 1080x1600 的重点简图
把这篇复杂技术文章做成 16 页中文 PPTX，thorough 审稿，并用 PowerPoint 做最终中文验收
```

provider 未指定且当前是交互会话时，只问一个选择题：

```text
需要可编辑本地版、NotebookLM 视觉版，还是两版对比？
```

用户没有回答或任务不可等待时，默认 `local_editable`；用户说「都试一下」「更漂亮」「做课件并对比」时优先 `hybrid`。

### 依赖与安装

```bash
claude plugin marketplace add soia-team/soia-open-skills
```

```bash
claude plugin install soia-pkm-vault@soia
```

只要这一个技能时，可用 npx 路线。注意技能会落进共享真源 `~/.agents/skills`；若同时装了插件，同一技能会出现两份索引且各自漂移，建议二选一：

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s soia-pkm-transform-article-ppt -y
```

- `local_editable`：优先使用宿主原生 presentations / PowerPoint 能力；Codex 环境优先使用其 Presentations runtime，而不是把 `python-pptx` 写成唯一默认实现。
- `imagegen`：宿主提供图片生成能力时直接调用；不可用时使用用户素材、图标或纯排版，不伪称生成了图片。
- `notebooklm`：需要 NotebookLM CLI 与登录态，见 [references/provider-notebooklm.md](references/provider-notebooklm.md)。
- `open_design`：可选增强；选中后硬依赖 `soia-dev-open-design-ops`，见 [references/provider-open-design.md](references/provider-open-design.md)。
- `officecli`：可选 Office 文件操作与复验层；适合检查、精确修改和验证已有 PPTX，不替代设计生成，见 [references/provider-officecli.md](references/provider-officecli.md)。

私有配置放在：

```text
~/.config/soia-skills/soia-open-pkm-vault-skills/soia-pkm/soia-pkm-transform-article-ppt/config.yml
```

配置文件选择顺序是 `--config` > `SOIA_PKM_ARTICLE_PPT_CONFIG_FILE` > 上述默认路径；字段值按“显式 CLI > 私有 config > 内置默认”解析。配置示例见 `assets/config.example.yml`。

**WorkBuddy** 的装载单位是角色化专家而不是插件，`npx skills add -a '*'` 覆盖不到它，需要单独安装，见 [docs/install/workbuddy.md](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)。

### 日志与完成回执

```markdown
完成：<一句话说明正式母版与辅助版本>。

- source: <路径或 URL>
- provider: local_editable | notebooklm | hybrid | open_design
- office_execution: host | officecli | host+officecli
- editable_pptx: <路径、页数、是否可编辑>
- notebooklm_pptx: <路径、页数、是否为图片页；未生成则省略>
- visual_assets: <数量与路径>
- infographic: <路径与尺寸；未生成则省略>
- manifest: <路径>
- planning: <内容计划、设计计划和 Contract Card 路径>
- review: <standard/thorough、content/design Lens 轮次与结论>
- signature_proof: <页码与预览路径；明确跳过则写原因>
- host_validation: <PowerPoint/Keynote/LibreOffice、渲染页数与 CJK 结果>

验证：
- PPTX 实际打开并渲染全部页面
- 预览页数与 PPTX 页数一致
- 无空白页、越界、重叠、乱码和占位符
- source 时间、作者、数字与声明已核对
- 人工逐页检查已完成
- Claim Ledger、双 Lens 审稿和宿主验收已完成

限制：<未验证事实、provider 降级或编辑性限制>
```

## 硬边界

1. **正式母版默认可编辑。** NotebookLM 常把每页做成整张图片；除非实测确认，否则不得称为可编辑 PPTX。
2. **图片模型不排密集中文。** imagegen 用于封面、插画、背景和视觉隐喻；标题、术语、数字、表格和来源由 PPT/HTML 后期排版。
3. **每页只有一个主判断。** 页面可以密集，但必须有明确视觉焦点和阅读顺序。
4. **不伪造元数据。** source 页只使用 source 中核实的作者、链接和发布时间；不写猜测的模型名、生成时间、notebook id、artifact id、下载路径或占位符。
5. **外部事实与原文观点分开。** 时间敏感预测、性能数字和企业案例若未独立核实，必须标成「原文观点/未验证」。
6. **文件存在不等于完成。** 没有全量渲染和人工视觉复核，不得交付为完成。
7. prompt、素材和中间 manifest 只落到用户指定输出目录；登录态、cookie、账号信息永不进入输出或回执。
8. **规划证据不能事后伪造。** Claim Ledger、设计计划、Signature Proof 和 critic 结果必须来自真实执行；不得只修改 JSON 让验证变绿。
9. **中文 deck 不把 LibreOffice 当唯一真相。** 最终优先在 PowerPoint/Keynote 打开和渲染；只能用 LibreOffice 时必须实际检查并记录 CJK 字形与换行。
10. **机密内容默认本地闭环。** `confidential` 必须 `network=deny`，中间证据写入私有 state，最终交付写入独立绝对目录；模板、state 和交付目录都不得位于 Git checkout。
11. **私有模板只引用、不复制。** 严格跟随模板时先核对 alias 与 SHA-256；manifest 不记录模板绝对路径，公开 fixture 只能使用虚构组织和数据。

## 工作流

### 1. 建立内容合同

读取完整 source，提取：`main_verdict`、受众任务、章节、概念、案例链、关键判断、易混点、风险与待核实事实。URL 先归档或保存稳定 source；只有主题时先形成内容提纲。

运行规划脚本生成可审计清单：

```bash
python3 scripts/media_bundle.py plan \
  --article <article.md> \
  --out-dir <output-dir> \
  --provider hybrid \
  --image-count 3 \
  --purpose "<用途>" \
  --delivery-context "<现场讲解、自读或混合>" \
  --language "zh-Hans" \
  --review-mode standard \
  --main-verdict "<一句主判断>"
```

路径与 manifest 契约见 [references/media-bundle-contract.md](references/media-bundle-contract.md)。
命令会同时创建不会覆盖已有内容的规划和 QA 模板；字段与状态流见 [references/planning-and-review-contracts.md](references/planning-and-review-contracts.md)。

### 2. 选择 provider 和交付范围

按「用户明确指定 > 私有配置 > 交互选择 > 默认 `local_editable`」决定。具体选择规则见 [references/provider-selection.md](references/provider-selection.md)。

固定企业模板或敏感材料先读取 [references/template-and-privacy-contract.md](references/template-and-privacy-contract.md)。模板模式与隐私级别分别决策；`confidential` 会覆盖普通 provider 偏好，只允许本地 allowlist 中的执行层。

`hybrid` 的职责固定：

- 本地版承担内容完整性、编辑性和正式交付。
- NotebookLM 版承担快速视觉叙事和对照实验。
- imagegen 只承担有明确页面用途的视觉素材。

### 3. 分离内容计划与设计计划

读取 [references/prompt-ppt.md](references/prompt-ppt.md) 和 [references/planning-and-review-contracts.md](references/planning-and-review-contracts.md)。先完成 `content-plan.json`：主判断、Claim Ledger、叙事弧和逐页内容；确认内容后再完成 `design-plan.json`：设计语言、语义色、页面轮廓、节奏和一个与内容结构绑定的 signature move。不要在内容计划阶段同时决定视觉，避免视觉偏好反向扭曲原意。

用 `contract-card.json` 固化 source、受众、用途、使用场景、语言、编辑性、review mode 和交付范围。任务低风险时默认 `standard`；公开演讲、正式教学母版、投标或高风险事实使用 `thorough`。两档都要求独立的 content/design Lens，区别只在复审上限和事实抽查深度。

### 4. 生成有用途的图片素材

需要视觉锚点时读取 [references/prompt-image-assets.md](references/prompt-image-assets.md)。通常生成 2-4 张：封面主视觉、核心机制图、关键案例/场景图。每张图必须绑定具体页码或信息图区域；不生成纯装饰库存图。

图片生成后先查看原图，再放进 PPT。若方向、对象关系、文字或数字错误，修改 prompt 重新生成；不要用遮盖层掩饰语义错误。

### 5. 先做 Signature Proof，再生成正式可编辑 PPTX

使用宿主 presentations 能力或 Open Design 生成。遵循当前宿主的演示文稿技能与 runtime 说明。PPTX 中的中文文本、流程箭头、表格、页码、来源应保持可编辑；位图只用于照片、插画、纹理和必要的复杂视觉。

OfficeCLI 不是默认创作 provider。已有母版、需要稳定元素路径精修、三项以上原子 batch、OpenXML schema 复验或内置截图时，可在生成后调用 `soia-dev-officecli-ops`。默认在副本上修改；不得用 OfficeCLI 绕过宿主 presentations 的硬性实现要求。

设计计划批准后，先制作 signature move 指定的核心页并渲染查看；通过后记录到 `qa/signature-proof.json`，再扩展全套。只有保守设计或 1–2 页极小任务可以明确跳过并写原因。

固定设计要求：

- 中长文默认 14-18 页；短文 8-12 页；用户指定时服从并记录压缩风险。
- 至少 4 种页面轮廓：封面、地图、流程、对比/矩阵、完整速查、案例、练习、来源等。
- 不连续使用同一套卡片网格；不把页面章节做成漂浮卡片。
- 标题表达判断，正文提供结构和证据；不写「背景介绍」「核心观点」这类空标题。
- 颜色承担语义，不用单一蓝紫或装饰渐变覆盖整套。

### 6. 可选生成 NotebookLM 对照版

读取 [references/provider-notebooklm.md](references/provider-notebooklm.md) 和 [references/prompt-notebooklm-ppt.md](references/prompt-notebooklm-ppt.md)。生成后必须按 artifact id 下载，防止同一 notebook 有多个 deck 时拿错版本。

NotebookLM 失败、排队或登录缺失不影响本地正式母版；但回执必须写明真实状态。若输出包含占位符、运行元数据、错误中文或 source 外事实，修改 prompt 后重新生成。

### 7. 生成可选信息图

需要「一张图讲清楚」时读取 [references/prompt-infographic.md](references/prompt-infographic.md)。先生成无字视觉部件，再用 HTML/CSS 或 PPT 排版中文，保持主判断、流程方向和术语层级一致。

### 8. 双 Lens 审稿与双层验收

全量渲染后分别做两次复核：content Lens 对照完整 source 和 Claim Ledger；design Lens 对照设计计划、Signature Proof 和全量预览。宿主支持独立 agent 时交给不同 agent；不支持时仍分两次独立检查。只有两个 Lens 都 `consent` 且 blocker/major 清零，才进入最终宿主验收。

最终优先用 PowerPoint 或 Keynote 打开和渲染正式母版，记录实际宿主、渲染页数和 CJK 检查结果。只能使用 LibreOffice 时，必须实际检查 CJK 字形与换行，并在宿主记录和交付回执中明确这一限制。

然后跑机械检查和人工视觉检查：

```bash
python3 scripts/media_bundle.py validate \
  --manifest <output-dir>/media-manifest.json \
  --visual-reviewed \
  --source-facts-reviewed \
  --strict \
  --json
```

详细标准见 [references/quality-gates.md](references/quality-gates.md)。任何一页失败都回到对应源文件、HTML 或 prompt 修复，再重新渲染；不能只改完成回执。

OfficeCLI 可用时，把它作为额外机械证据：运行 `validate`、`view issues`，并按需生成全量截图。它不能替代 `media_bundle.py` 的编辑性检查和人工逐页视觉复核。

### 9. 交付与回链

普通任务把正式母版、辅助版本、图片和 manifest 放在同一输出目录。`confidential` 任务把 prompt、规划、预览、QA 和 manifest 留在私有 state，仅把最终 PPTX 与用户明确要求的交付文件写入独立 final output。若 source 位于可写知识库且已有「关联/派生产物」区域，更新链接；不要在多个文件复制同一份产物清单。

## 按需读取

- 输出目录和 manifest：[references/media-bundle-contract.md](references/media-bundle-contract.md)
- provider 选择：[references/provider-selection.md](references/provider-selection.md)
- 可编辑 PPT 计划与提示词：[references/prompt-ppt.md](references/prompt-ppt.md)
- imagegen 素材：[references/prompt-image-assets.md](references/prompt-image-assets.md)
- 信息图：[references/prompt-infographic.md](references/prompt-infographic.md)
- NotebookLM：[references/provider-notebooklm.md](references/provider-notebooklm.md)、[references/prompt-notebooklm-ppt.md](references/prompt-notebooklm-ppt.md)
- Open Design：[references/provider-open-design.md](references/provider-open-design.md)、[references/prompt-open-design.md](references/prompt-open-design.md)
- OfficeCLI 操作与复验：[references/provider-officecli.md](references/provider-officecli.md)
- 质量门：[references/quality-gates.md](references/quality-gates.md)
- 规划、Signature Proof、双 Lens 审稿和宿主验收：[references/planning-and-review-contracts.md](references/planning-and-review-contracts.md)
- 外置模板、SHA-256、机密隔离和路径硬门：[references/template-and-privacy-contract.md](references/template-and-privacy-contract.md)
- 典型调用：[references/examples.md](references/examples.md)

## 私密信息与中间数据

- 私有配置只放 `~/.config/soia-skills/soia-open-pkm-vault-skills/soia-pkm/soia-pkm-transform-article-ppt/config.yml`，或使用 `SOIA_PKM_ARTICLE_PPT_CONFIG_FILE` 指向用户自有文件。
- NotebookLM、Office 或其他 provider 的凭据留在 provider 官方登录存储或系统钥匙串；不得写入 config、prompt、manifest、PPTX、预览和回执。
- 普通任务的 prompt、规划 JSON、QA JSON、预览和临时素材写入媒体包目录。`confidential` 任务必须写入私有 state，且不得纳入版本控制。
- 可重建的临时转换文件使用操作系统临时目录并在成功或失败后清理；不得把仓库 checkout 当运行缓存。
- 正式 PPTX、PDF、图片与用户明确要求保留的媒体包由用户控制保留期；删除或覆盖前必须确认目标。
