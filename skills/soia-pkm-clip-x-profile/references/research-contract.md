# 研究契约

只在需要精确参数、边界或输出字段时读取；首次触发技能只读 `SKILL.md`。

## 参数

```text
profile                 X 主页 URL 或 handle
--limit N               最新窗口大小，1–100
--month YYYY-MM         CST 月份
--since DATE            CST 起始日期，包含当天
--until DATE            CST 结束日期，包含当天
--fetch-scope latest-window|all
--query TERM            标题、正文、ALT 子串检索，可重复
--query-mode any|all    多关键词 OR/AND
--category FAMILY       image 现有 family，可重复
--has-media             只保留含媒体帖子
--has-alt               只保留有图片 ALT 的帖子
--only-gpt2             只保留公开证据提到 GPT2/GPT-image2 的帖子
--output-mode summary|classification|image-prompts|all
```

`--month` 不能与 `--since/--until` 同时使用。`--until` 的日期边界包含当天；相对时间由调用方先换成日期并写入回执。`--fetch-scope all` 必须有明确日期起点或合理 `--max-pages`。

## 数据源和覆盖

网络模式使用 FxTwitter v2：

```text
GET https://api.fxtwitter.com/2/profile/<handle>/statuses
  ?count=100&cursor=<bottom-cursor>&with_replies=0&groupthreads=0
```

Profile metadata 另取 `/2/profile/<handle>`。每页记录 provider 游标、HTTP 状态、实际新增数和停止原因。`latest-window` 是最新 N 条再筛选；`all` 只声明“本次 provider 窗口内覆盖”，不声明账号历史全量。

## 输出

所有模式都写核心研究文件：

```text
profile.yml          账号事实和 provider profile
latest-window.json   实际抓取窗口
filtered.json        叠加时间/关键词/主题/证据条件后的结果
month-filter.json    旧消费者兼容别名
classification.yml   时间段基线分类、GPT2/ALT 证据和筛选覆盖
summary.md           可读研究摘要
manifest.yml         请求、条件、覆盖、停止原因和产物
```

仅 `image-prompts`/`all` 生成：

```text
image-prompts.yml    image 技能导入索引
prompts/*.md         每条完整 Prompt Deck
```

`classification.yml` 的 `period_selected` 是时间段基线，`filtered.json` 的 `selected` 是叠加全部条件后的最终集；两者可能不同。

## 证据和分类

- 检索字段：标题、正文、图片 ALT；原始 URL、发布时间和状态 ID 必须保留。
- 轻量分类只用于主题/视觉 family 索引，不取代人工判断。
- 无 ALT 时只能说“没有 provider 返回 ALT”，不能补写“已获取完整提示词”。
- GPT2 只映射为 `model_adapter=external_gpt_image_label`；非 GPT2 可保持 `auto`。

## image 路由

只有客户明确选择 `--output-mode image-prompts/all` 或明确说交给 image 技能时，才编译 Prompt Deck。每条必须保留来源证据、筛选条件、组合轴和七个 blocks；不创建账号/月份/来源专属 preset。位图生成和 `view_image` 验收由 `soia-media-generate-article-image` 继续完成。

## 失败和隐私

网络失败、provider 缺字段、页数触顶、无命中和缺 ALT 都要在回执中单独列出。只读公开数据和客户 fixture，不读取 Cookie/登录态；真实 run bundle 不进入公共仓库、vault 根或 `~/.codex/generated_images`。
