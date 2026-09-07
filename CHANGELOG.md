# Changelog

本文件由 soia-meta-skill-release 在每次正式发版时自动更新，与 GitHub Release 同源；
更早的版本演进见 git 提交历史与 GitHub Releases。

## v1.12.2 — 2026-09-07

Clarify instruction autonomy and preserve explicit approval gates

## 维护
- docs: clarify scoped autonomy and preserve approval gates (#81)
- chore(release): open next train after v1.12.1 (#80)

## v1.12.1 — 2026-09-01

新增深度 PDF 入口解析与安全下载，修复 X 正文短链展开和译文去重

## 新增
- feat(pkm): add deep PDF URL archiving and expand X links (#78)

## 维护
- chore(release): open next train after v1.12.0 (#77)

## v1.12.0 — 2026-09-01

公众号归档去重归一化与显式拦截识别、知识库地图 --full 逐条列出、clip-web 工具链与译文规范

## 修复
- fix(pkm): 公众号归档去重归一化 + 显式拦截识别；feat: 地图 --full 逐条显示 (#75)
- fix(pkm): cover writing structure and assets (#74)

## 维护
- chore(release): open next train after v1.11.1 (#73)

## v1.11.1 — 2026-08-21

为 Obsidian Bases 补齐可验证的目录边界，并同步初始化、书库与馆藏技能规范。

## 修复
- fix(pkm): scope Bases to vault directories (#71)

## 维护
- chore(release): open next train after v1.11.0 (#70)

## v1.11.0 — 2026-08-21

新增可在 Obsidian 内直接播放的播客归档，并为 MOC 单篇增量与全量重建增加安全门禁。

## 新增
- feat(pkm): archive playable podcasts and guard MOC rebuilds (#67)

## 维护
- chore(release): target pkm vault 1.11.0 (#68)
- chore(release): open next train after release

## v1.10.0 — 2026-08-06

bootstrap/lifecycle 规则对齐、归档证据生命周期、config 归位 assets、安装章节三宿主覆盖

## 新增
- feat(pkm): enforce five-stage knowledge intake contract (#57)
- feat(pkm): chain single-article capture into organize (#56)

## 修复
- fix(pkm): align bootstrap and lifecycle rules (#58)
- fix(metadata): real timestamps from git history (was 00:00:00) (#54)

## 维护
- chore(release): feat 在列,版本列车提为 next-minor
- chore(skills): config.example.yml 归位到 assets/ (#64)
- chore(skills): 补上安装章节改动遗漏的版本 bump (#63)
- docs(skills): 安装章节补齐三个一等宿主 (#62)
- docs(pkm): codify archive evidence lifecycle
- docs(agents): branch off main; releases fast-forward dev onto main (#61)
- docs(pkm): harden vault organization and search contracts (#55)
- chore(release): switch dev train to patch level (#53)
- chore(release): reopen version train (missed after last release) (#52)

## v1.9.0 — 2026-08-03

lint_vault 校验加固

## 新增
- feat(pkm): land governance continuation (query search, clip-x-profile, contracts) (#43)

## 修复
- fix(maintain-vault-health): lint_vault 校验加固 (#48)

## 维护
- docs(changelog): seed with current release baseline (#47)
- chore(release): open next train after v1.8.0 (#46)
- release: finalize v1.8.0 (drop -SNAPSHOT) (#44)
- docs(agents): dev-branch integration workflow (#42)
- chore(release): open dev branch — audit on dev, version train 1.7.0-SNAPSHOT

## v1.8.0 — 2026-08-02

vault 治理收官：检索改进、生命周期契约与新技能 clip-x-profile。
