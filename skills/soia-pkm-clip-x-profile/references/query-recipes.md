# X 账号研究查询配方

只在用户明确需要某种研究产物时读取本文件。日期示例使用 CST；请将自然语言的“最近一周/最近一个月”先换算成明确日期再运行。

## 研究而非生图

```bash
# 最近 30 条账号概览
python3 scripts/profile_x.py https://x.com/<handle> \
  --limit 30 --output-mode summary --output <run-dir>

# 指定一周内关于主题的帖子
python3 scripts/profile_x.py https://x.com/<handle> \
  --since 2026-07-25 --until 2026-07-31 \
  --topic <topic> --output-mode summary --output <run-dir>

# 同时满足多个关键词，并且必须有图片
python3 scripts/profile_x.py https://x.com/<handle> \
  --query <term-a> --query <term-b> --query-mode all \
  --has-media --output-mode classification --output <run-dir>
```

## 模型/提示词研究

```bash
# 先研究最近一个月的 GPT2 线索，不生成图片 Prompt
python3 scripts/profile_x.py https://x.com/<handle> \
  --since 2026-07-01 --until 2026-07-31 \
  --query GPT2 --only-gpt2 --output-mode summary --output <run-dir>

# 用户明确要求把同一命中集交给 image 技能
python3 scripts/profile_x.py https://x.com/<handle> \
  --since 2026-07-01 --until 2026-07-31 \
  --query GPT2 --only-gpt2 --has-alt \
  --output-mode image-prompts --output <run-dir>
```

`--only-gpt2` 是筛选条件，不是 preset；没有 `--output-mode image-prompts/all` 时，输出仍然是研究结果。

## 覆盖策略

- `latest-window`：只取最新 `--limit` 条，再应用时间/关键词条件；适合“最近 100 条”。
- `all`：按分页继续到 `--since` 或 `--month` 起点之前；必须设置合理的 `--max-pages`，manifest 会记录是否触顶。
- provider 只能返回账号公开可见状态；删除、锁定、登录态内容和缺失 ALT 不应被补写。
