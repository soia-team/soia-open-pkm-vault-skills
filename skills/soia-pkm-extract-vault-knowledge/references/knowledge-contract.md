# 长期知识合同

## 最小 frontmatter

    ---
    tags: [资料库, 长期知识, <主题>]
    title: <稳定标题>
    type: guide
    knowledge_state: stable
    sensitivity: internal
    created: YYYY-MM-DD
    updated: YYYY-MM-DD
    source: "[[来源笔记]]"
    ---

枚举：

- type：concept | guide | reference | checklist | pattern
- knowledge_state：draft | stable | needs_review | deprecated
- sensitivity：public | internal | private | restricted

单一来源使用 `source`；多来源使用 YAML 列表 `sources`，每项都用完整 vault 相对路径 wikilink，避免同名歧义。`draft` 模板可暂时留空 `source`，但进入 `stable` 前必须补真实来源。review_after、superseded_by 可选。不要使用工作台的 status、priority、project 或 next_action。

## 来源到知识的判定

| 来源内容 | 处理 |
|---|---|
| 时间线、执行回执、事故调查 | 原件留证据区，只提炼方法与防线 |
| 当前状态、待办、负责人 | 留工作台；知识稿删除状态 |
| 文章、图书、项目精读 | 原件留专项区，知识稿引用来源 |
| 历史导入笔记 | 默认是来源语料，不因位于 20 就视为精选知识 |
| 账号、连接串、客户/家庭信息 | 不复制值；只提炼安全做法并标敏感级别 |

## 写前计划

每一项至少列：

1. source 与 SHA-256；
2. target，且目标不存在；
3. 已有同名/同主题候选；
4. 保留的稳定结论与舍弃的时态内容；
5. sensitivity 与脱敏方式；
6. 预期来源 wikilink。

## 验证

- 来源仍存在、内容 hash 未漂移；
- 目标 frontmatter 可解析；
- tags 首项为 资料库，并含 长期知识；
- source 指向真实文件；
- 无开放 checkbox、当前 owner/priority/next action；
- 不出现真实密码、token、cookie、私有绝对路径或身份信息。
