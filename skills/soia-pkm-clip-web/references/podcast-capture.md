# 播客网页归档

当网页公开 `PodcastEpisode` JSON-LD，且客户要求保留音频时，使用本模式。它保存来源页提供的 shownotes；除非另行执行 ASR，否则不得把 shownotes 写成“逐字稿”。

## 命令

```bash
python3 scripts/archive_podcast.py <episode-url> \
  --vault <vault-path> \
  --articles-dir <articles-subdir>
```

- 默认下载公开音频；只核查或只收 shownotes 时加 `--metadata-only`。
- 本机有 `aria2c` 时默认用 8 路 Range 下载，缺少时自动回退 Python 标准库单连接；可用 `--download-engine urllib|aria2c` 固定后端。
- 媒体已经完整下载、但笔记尚未写入时，重跑会复核本地 bytes/SHA-256 后复用成品，不重复拉取。
- 二进制媒体默认写入 `<vault>/_attachments/podcasts/<episode-id>/audio.m4a`。笔记必须生成 `## 🎧 收听本地音频` 与 Obsidian 原生 `![[相对路径/audio.m4a]]` 嵌入；只列本机绝对路径不算可播放交付。
- 大音频由 vault 所在仓库自行决定同步策略。超过 Git 托管单文件限制时应使用本地 exclude、Git LFS 或独立媒体备份，并在回执中说明；不得为了便于提交而删除本地音频。
- 输入 URL 的 query/fragment 不写入笔记。媒体 URL 若带 query/fragment，也只持久化去参数后的地址；实际下载仍使用运行时原值。
- 下载先写 `.part`，完成大小校验后原子替换；音频失败时不写笔记，避免“正文成功”掩盖客户要求的媒体失败。
- 脚本拒绝本机、RFC1918 内网、链路本地和普通保留地址，不携带 cookie、token 或其他登录态。本机透明代理使用的 RFC 2544 `198.18.0.0/15` fake-IP 是受限例外，便于在 TUN/fake-IP 网络下抓公开网页。

## 内容与媒体门禁

1. `content_complete` 只代表来源页 shownotes 已完整捕获。
2. 来源页没有逐字稿时写 `transcript_status: not_provided_by_source`；不得推断音频已转写。
3. 下载后复核 MIME、实际 bytes、SHA-256，并用 `ffprobe`、`file` 或等价工具从另一条路径验证容器和时长。
4. `url` 使用页面 canonical URL；不得保存分享追踪参数。
5. 归档后按 `soia-pkm-organize-article-moc` 的单篇合同补摘要/topics，只增量同步受影响的文章 MOC，并完成 map/Base 验证；不得为单篇归档调用会先清空整个 `_MOC` 的全量重建流程。

## Frontmatter 增量字段

普通文章字段之外，播客条目使用：

```yaml
type: podcast
podcast: <series-name>
podcast_url: <canonical-series-url>
episode_id: <stable-id>
duration_iso: <ISO-8601-duration>
duration_seconds: <integer-or-empty>
media_local_path: <absolute-local-path-or-empty>
media_vault_path: <vault-relative-path-or-empty>
audio_embedded: true
media_fetched: true
media_sha256: <sha256-or-empty>
media_bytes: <integer>
media_mime_type: <mime>
media_download_engine: <aria2c-or-urllib>
media_source_url: <query-free-url>
content_complete: true
transcript_status: not_provided_by_source
```
