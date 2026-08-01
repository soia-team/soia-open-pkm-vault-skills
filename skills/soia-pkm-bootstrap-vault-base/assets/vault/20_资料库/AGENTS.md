# 20_资料库 · AGENTS.md

只保存去掉当前任务状态后仍可长期复用、能够独立阅读且带来源的精选知识。默认下钻：`10_主题知识/`、`20_规范与手册/`、`30_学习指南/`；历史导入或来源语料即使暂存于 20，也不自动视为稳定知识。

## Frontmatter

长期知识必填：`tags` 首项 `资料库` 且包含 `长期知识`、`title`、`type`、`knowledge_state`、`sensitivity`、`created`、`updated`、`source`。

- `type`: `concept | guide | reference | checklist | pattern`
- `knowledge_state`: `draft | stable | needs_review | deprecated`
- `sensitivity`: `public | internal | private | restricted`
- `source`: 指向保留原件的 wikilink；多来源可增加 `sources`

不写工作台的 `status`、`priority`、`project`、owner 或 next actions。冻结报告、时间线和当前执行状态不搬进 20；保留原件并提炼新知识。任何云端同步必须使用明确子目录 allowlist，且拒绝 `private/restricted`。
