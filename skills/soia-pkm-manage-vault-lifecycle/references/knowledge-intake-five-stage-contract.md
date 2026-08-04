# 通用五段入库合同

任何进入或被整理的对象都走同一条可验收闭环，不按文件扩展名缩短流程：

`captured → organized → MOC/导航 → map → Base`

## 五段定义

| 阶段 | 必须证明的事实 | 最小证据 |
|---|---|---|
| `captured` | 对象已进入受控入口，来源可追溯 | source/URL、原路径、对象类型、哈希或不可计算原因 |
| `organized` | 已按目标区规则归位，且未丢正文、附件和元数据 | source→target manifest、大小/SHA-256、frontmatter/checkbox/status 守恒 |
| `MOC/导航` | 所属模块的 MOC、导航、目录或专题入口已更新 | 入口路径、变更摘要；不适用时写 `not_applicable` 与理由 |
| `map` | 路径/文件集合变化已反映到全库地图 | 地图生成命令、files/dirs 统计、verify 结果 |
| `Base` | 受影响 Base 的范围和字段过滤仍覆盖目标 | Base 路径、`file.inFolder` 验证；不适用时写 `not_applicable` 与理由 |

完成条件：五个状态均为 `pass` 或明确的 `not_applicable`，并能定位证据。`captured` 或 `organized` 单独成功不等于入库完成。

## 按对象路由

- 网页/微信文章：`clip-web`/`clip-wechat-article` → `organize-article-moc` → 文章 MOC → 地图 → 受影响 Base。
- PDF、Word、图片、音视频、云盘文件：先由对应 clip 技能捕获；用提取器/OCR/转写形成可检索证据（失败也要记录限制）→ 按目标区整理 → 附件目录/MOC → 地图 → 受影响 Base。
- 书卡与阅读记录：`library-book-catalog`/`library-weread-sync` → 书库或阅读记录导航/Base → 地图 → 受影响 Base；没有独立 MOC 时在回执中写 `not_applicable`。
- 日志和 Agent 会话：`log-agent-sessions` → 日期层与日志导航 → 地图 → 若无对应 Base 写 `not_applicable`。
- 草稿与发布物：按 `50_写作与发布` 生命周期 → 写作导航/发布清单 → 地图 → 无 Base 时写 `not_applicable`。
- 代码仓库与项目资料：`clip-github-repo` 或 `60_开源项目` → 项目入口/MOC → 地图 → 受影响 Base。

技能之间通过回执交接，不把“已调用上游技能”当作下游阶段已完成。批量任务先输出逐对象 manifest；缺失附件、未知状态、重复编号、未解析二进制和死链均进入 blocker，不得用自动生成的占位页掩盖。

## 标准回执

```yaml
object: <vault-relative-path-or-id>
captured: pass|fail
organized: pass|fail
moc: pass|not_applicable|fail
map: pass|not_applicable|fail
base: pass|not_applicable|fail
evidence:
  - <manifest-or-receipt-path>
blockers: []
```
