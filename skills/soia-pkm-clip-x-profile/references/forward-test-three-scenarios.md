# 三场景前向测试

真实抓取结果写入客户指定的临时 run bundle，不提交公共仓库。每个场景都要回执范围、provider、命中数、证据和失败边界。

## 场景一：账号月份总结 + 最新帖子

目标：分别总结 `https://x.com/dotey` 的 2026 年 7 月帖子和最新窗口，不把两个范围混成一个结果。

```bash
python3 scripts/profile_x.py https://x.com/dotey \
  --month 2026-07 --fetch-scope all --max-pages 40 \
  --output-mode summary --output <run-dir>/dotey-july

python3 scripts/profile_x.py https://x.com/dotey \
  --limit 20 --output-mode summary --output <run-dir>/dotey-latest
```

验收：两个 manifest 的条件、fetched、selected、分页边界不同且可解释；两个 `summary.md` 都有帖子链接、主题分布和“不是历史全量”的声明。

## 场景二：100 条窗口 → GPT2 → image → 位图效果

目标：采集 `xiaoxiaodong01` 最新 100 条，筛出 2026 年 7 月基线，分类，再只把 GPT2 命中项交给 image 技能。

```bash
python3 scripts/profile_x.py https://x.com/xiaoxiaodong01 \
  --limit 100 --month 2026-07 --fetch-scope latest-window \
  --only-gpt2 --output-mode image-prompts --output <run-dir>/xiaoxiaodong01
```

验收分两层：

1. 研究层：`manifest.yml` 同时有 `period_selected` 和最终 `selected`；`classification.yml` 覆盖月份基线；Prompt Deck 保留来源 URL、原始 ALT/正文、组合轴和七个 blocks。
2. 位图层：从 `prompts/*.md` 选 1 条代表性 Prompt 交给 imagegen，保存实际 PNG/JPG，使用 `view_image` 检查构图、比例、文字、来源事实和移动端可读性；不能把 Prompt 编译通过写成图片验收通过。

## 场景三：发现 GPT2 提示词和博主

目标：当用户没有给定账号而是问“X 上关于 GPT2 有哪些好提示词/好博主”时，先做发现，不伪装成账号 profile 抓取。

步骤：

1. 用 X 搜索或 Web 搜索寻找候选帖子/账号，记录查询词、候选 URL、作者、日期和入选理由。
2. 把候选账号交回本技能，按 `--query GPT2`、时间范围和 `--has-alt` 复核其公开窗口。
3. 输出候选比较摘要：作者/账号、提示词主题、是否有 ALT 原文、可复用结构、证据链接和局限；只有客户继续要求时，才将选中的帖子交给 image 技能。

验收：发现结果与 profile 复核结果分开；没有把单个账号的最新窗口写成“全网最佳”，没有为外部作者的提示词补造正文。
