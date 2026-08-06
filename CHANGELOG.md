# Changelog

本文件由 soia-meta-skill-release 在每次正式发版时自动更新，与 GitHub Release 同源；
更早的版本演进见 git 提交历史与 GitHub Releases。

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
