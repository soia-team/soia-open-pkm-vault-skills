# Template and Privacy Contract

固定模板能力与隐私级别是两个独立维度：`template.mode` 决定如何继承版式，`privacy.classification` 决定 provider、路径和中间产物边界。不要用一个 `private_template` 开关混合两类决策。

## 私有配置

配置文件放在用户目录，不复制模板字节：

```text
~/.config/soia-skills/soia-open-pkm-vault-skills/soia-pkm/soia-pkm-transform-article-ppt/config.yml
```

配置文件使用 config schema v2（不要与 manifest schema v3 混淆）：

```yaml
schema_version: 2

template:
  mode: strict_following
  alias: weekly_report
  path: <absolute-private-template-path>
  sha256: <64-character-sha256>
  allowed_fonts: [Aptos, Arial, Noto Sans SC]

privacy:
  classification: confidential
  network: deny
  provider_allowlist: [local_editable, officecli]
  persist_intermediates: private_state

paths:
  state_root: <absolute-private-state-root>
  output_root: <absolute-delivery-root>
```

- `template.path` 必须是绝对路径，并指向已有 PPTX。
- `template.alias` 使用不含组织信息的稳定标识。
- `template.sha256` 必须与文件字节一致；hash 不匹配立即停止。
- config 保存引用和字段策略，不保存模板副本、截图、Logo 或历史内容。
- 配置文件选择顺序：`--config` > `SOIA_PKM_ARTICLE_PPT_CONFIG_FILE` > 上述默认路径。
- 字段值优先级：显式 CLI > 私有 config > 内置默认值。
- 验证时省略 `--template-file` 也可以从 config 解析路径，但 config 的 alias 与 SHA-256 必须同时匹配 manifest；任一漂移即失败。

## Confidential 硬门

`privacy.classification=confidential` 时必须同时满足：

- `network=deny`；拒绝 NotebookLM、Open Design、imagegen 和其他联网 provider。
- provider allowlist 至少覆盖本次执行能力，通常是 `local_editable` 与可选的 `officecli`。
- `--out-dir`、`state_root` 和 `output_root` 都是绝对路径。
- `--out-dir` 位于 `state_root` 内；`state_root` 与 `output_root` 不得重叠。
- template、state 和 output 都不位于任何 Git checkout。
- manifest 的 `template` 只记录 `mode`、alias、SHA-256、验证状态和允许字体，不记录模板路径。

`media_bundle.py plan` 会在创建输出目录前执行这些检查。任一硬门失败都不应留下新媒体包。

## 规划示例

先在本地计算模板 SHA-256，再规划一次独立 run：

```bash
python3 scripts/media_bundle.py plan \
  --article <absolute-private-source.md> \
  --out-dir <absolute-private-state-root>/runs/<run-id> \
  --provider local_editable \
  --image-count 0 \
  --main-verdict "<一句主判断>" \
  --template-mode strict_following \
  --template-alias weekly_report \
  --template-file <absolute-private-template.pptx> \
  --template-sha256 <64-character-sha256> \
  --allowed-font Aptos \
  --allowed-font "Noto Sans SC" \
  --privacy-classification confidential \
  --network deny \
  --provider-allowlist local_editable,officecli \
  --persist-intermediates private_state \
  --state-root <absolute-private-state-root> \
  --output-root <absolute-delivery-root>
```

生成后的路径分工：

```text
<absolute-private-state-root>/runs/<run-id>/
├── prompts/
├── planning/
├── previews/
├── qa/
├── media-manifest.json
└── media-validation.json

<absolute-delivery-root>/
└── <stem>-editable.pptx
```

最终 PPTX 的 manifest entry 使用 `base: delivery`；其他证据默认使用 `base: state`。

严格模板的最终验证必须再次解析模板路径，防止规划后模板字节被替换。可以显式传入：

```bash
python3 scripts/media_bundle.py validate \
  --manifest <absolute-private-state-root>/runs/<run-id>/media-manifest.json \
  --template-file <absolute-private-template.pptx> \
  --visual-reviewed \
  --source-facts-reviewed \
  --strict \
  --json
```

也可以省略 `--template-file`，由已绑定的私有 config 解析。该路径只在本次进程中用于重算 SHA-256 和读取 OOXML 结构，不写入 manifest 或 validation report。

## 严格模板 QA

`template.mode=strict_following` 会增加 `qa/template-fidelity.json`。QA 文件只声明本次 deck 的预期，不接受自报的“结构已通过”布尔值：

```json
{
  "status": "passed",
  "template_alias": "weekly_report",
  "template_sha256": "<64-character-sha256>",
  "allowed_fonts": ["Aptos", "Noto Sans SC"],
  "expected_editable_charts": 1,
  "expected_native_tables": 2,
  "table_pagination_required": true,
  "table_page_groups": [[4, 5]],
  "notes": "长表拆为连续两页"
}
```

验证器直接读取模板与正式 PPTX 的 OOXML：比较 slide size 和 master/layout 摘要，计算实际字体集合，核对 slide relationship 绑定的 chart part、原生表格和分页页组，并扫描越界元素与孤立连接线。任何一项不符都失败；全量渲染和人工逐页检查仍是独立硬门。

公开 CI 使用 `tests/fixtures/article-ppt/acme-weekly-report.md` 或等价的虚构数据。不得把真实模板、元素映射、预览或 golden PPTX 放进仓库。

## 收尾检查

1. 全量渲染并完成人工逐页复核。
2. 通过 `--template-file` 或 alias + SHA-256 完全匹配的私有 config 跑 strict validation，确认模板 OOXML 结构、template-fidelity、双 Lens 和宿主验收同时通过。
3. 比较开源仓运行前后的 `git status --short`；出现模板、PPTX、预览、manifest 或私有路径即失败。
4. 只交付 final output 中用户明确要求的文件；按保留策略清理可重建 state。
