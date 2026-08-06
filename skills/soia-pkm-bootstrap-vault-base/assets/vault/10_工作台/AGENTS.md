# 10_工作台 · AGENTS.md

固定结构：`00_Inbox/` 临时捕获，`10_总控/` 唯一总入口，`20_活跃项目/<项目>/` 当前项目控制面。已有 vault 可通过自定义 config 保留自己的 Inbox 命名。

工作台 Markdown 必填：`tags` 首项 `工作台`、`title`、`type`、`status`、`project`、`priority`、`created`、`updated`。

- `type`: `dashboard | project | handoff | execution | requirements | deliverable`
- `status`: `inbox | backlog | active | waiting_user | blocked | review | done`
- `priority`: `P0 | P1 | P2`

`done` 只作短暂迁移态；冻结证据→30，稳定知识→20，历史→90。未经授权不删除 Inbox。
