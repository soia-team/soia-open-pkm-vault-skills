# 回归测试：@xiaoxiaodong01

这是通用账号研究技能的一个回归样例，不是技能的默认账号、默认月份或唯一用途。真实结果落在客户指定的 run bundle；不要把抓取的 `profile.yml`、帖子正文、ALT 或图片缓存提交进公共仓库。

## 首个历史验收点：GPT2 → image Prompt Deck

```bash
python3 scripts/profile_x.py \
  https://x.com/<handle> \
  --limit 100 \
  --month 2026-07 \
  --month-scope latest-window \
  --only-gpt2 \
  --output-mode image-prompts \
  --output <run-dir>
```

预期不是固定条数，而是 manifest 中可解释的实际值：最新窗口 fetched、月份 selected、GPT2 detected/converted、ALT evidence、分页和停止原因。

## 通用回归矩阵

### 1. 账号最近内容摘要

```bash
python3 scripts/profile_x.py https://x.com/<handle> \
  --limit 20 --output-mode summary --output <run-dir>
```

检查 `summary.md` 是否有账号、窗口、主题分布、帖子链接和覆盖边界；不得生成 `image-prompts.yml`。

### 2. 时间段主题总结

```bash
python3 scripts/profile_x.py https://x.com/<handle> \
  --since 2026-07-25 --until 2026-07-31 \
  --query <topic> --query-mode any \
  --output-mode summary --output <run-dir>
```

检查日期边界、关键词条件和命中清单都被写入 `manifest.yml` 与 `summary.md`。

### 3. 主题组合条件

```bash
python3 scripts/profile_x.py https://x.com/<handle> \
  --query <term-a> --query <term-b> --query-mode all \
  --has-media --output-mode classification --output <run-dir>
```

检查只有同时命中两个条件且带媒体的帖子进入 `filtered.json`。

### 4. 明确下游 image 路由

仅在客户要求“把这些帖子转换成 image 技能”时，增加 `--output-mode image-prompts`；image 技能接手后仍须独立完成位图和视觉验收。

## 验收边界

1. `latest-window` 是有限窗口，不等同于账号历史全量；目标月份全量需明确使用 `--month-scope all` 并记录 `--max-pages`。
2. `classification.yml` 的 family 只能来自 image 技能已有组合轴；GPT2 只能作为模型线索。
3. 研究摘要可以没有 Prompt Deck；Prompt Deck 必须有来源 URL、原始提示词证据、组合轴和七个 blocks。
4. “Prompt 已编译”与“位图生成/视觉验收通过”必须分开回执。
