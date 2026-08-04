# AGENTS.md - soia-open-pkm-vault-skills

Rules for all AI agents editing this repository.

## Repository Purpose

`soia-open-pkm-vault-skills` publishes reusable `soia-pkm-*` skills for the pkm domain. Every committed skill must be safe for users who do not share the maintainer's machine, accounts, private data, or internal workspace.

## Safety Rules

- No real API keys, tokens, cookies, session strings, passwords, account ids,
  private `config.yml`, or `.env` files.
- No maintainer-specific absolute paths such as `/Users/<name>/...`.
- No private family, home, health, finance, or learner profile context.
- Put user-specific behavior behind CLI args, env vars, or skill-specific
  user-owned config files outside this repo. Existing skills may retain
  `~/.config/soia-skills/<skill-name>/config.yml`; newly isolated configs may use
  `~/.config/soia-skills/<repository>/<domain>/<skill-name>/config.yml` when the
  skill documents and implements that path.
- Repository examples must use placeholders such as `<path>`, `<repo>`, and
  `<YOUR_KEY>`.

## Validation

Before committing skill changes, run:

```bash
python3 -m pip install -r requirements-dev.txt  # once per machine; the audit uses PyYAML
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/generate_skill_catalog.py --check
python3 scripts/audit_skills.py
git diff --check
```

For changed skills, also run a skill validator when one is available. On Codex
machines, this helper is commonly available:

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/<skill-name>
```

Final installation acceptance must use the pushed remote repo, not a local
checkout copied into an agent target:

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -l --full-depth
npx skills add soia-team/soia-open-pkm-vault-skills -g --all
```

## 维护本仓技能

技能契约、调试安装、新增/改名/拆分/删除的完整流程，以及插件市场发布步骤，统一见
元仓的 [CONTRIBUTING.md](https://github.com/soia-team/soia-open-skills/blob/main/CONTRIBUTING.md)。
本文件只保留本仓特有的用途、边界与验证命令。

## Git Workflow

- **Branch off `main`** (the latest formal release), then open the PR against
  `dev` and wait for the `audit` check. `main` is always an ancestor of `dev`,
  so such a branch always merges cleanly. Branch off `dev` only when your change
  genuinely builds on unreleased work, and say so in the PR body.
- `main` never receives PRs. It moves only by **fast-forward from `dev`** during
  a formal release driven by `soia-meta-skill-release`, so `main` and `dev` then
  point at the same commit. Never push directly to `main` or `dev`.
- Plugin manifests on `dev` carry a `-SNAPSHOT` version naming the next release
  target. Do not change manifest versions in feature PRs; versions move only
  during a release.
