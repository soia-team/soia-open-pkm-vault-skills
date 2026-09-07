# AGENTS.md - soia-open-pkm-vault-skills

Rules for all AI agents editing this repository.

## 规则适用与任务完成

- 宿主实际加载的全局规则、父目录规则与本文件共同适用；本文件补充本仓事实和边界，不把共享贡献手册的旧示例当作新的授权。遇到无法按层级消解的实质冲突，指出具体条款，仅暂停受影响动作。
- 解释、诊断或审阅只读取相关规则与证据，不自动授权修复、安装或发布；明确要求实施且范围已清楚时，完成修改、适度验证和结果交付，不只返回计划。
- 已批准范围内的常规补丁、相关只读检查和验证连续推进；只在缺少会实质改变结果的信息、重叠改动无法安全保留，或下一步超出授权时询问。已确认且目标与影响未变的计划不重复确认。
- 未提交改动属于原作者；不清理、不混入提交、不覆盖。无关脏文件不阻断可隔离工作，真实重叠只暂停冲突部分。
- 不因仓名或“完整交付”默认启动多模型、子 Agent、全生态扫描、全量安装或产品治理流程；仅在用户要求、适用项目角色规则或任务风险明确需要时采用对应流程。
- 提交、远端写入、合并、部署、发布、发送消息、权限变更、凭据操作及重要数据删除仍遵守各自授权门；本地修改完成不代表这些后续动作已获授权。
- 交付说明实际改动、验证结果、未验证项及阻塞。要求实施的任务应做到授权边界内可验证的完成；区分本次已请求但待批的剩余步骤与未请求的后续动作；未请求的发布/安装不属于本次未完成工作。

## Repository Purpose

`soia-open-pkm-vault-skills` publishes reusable `soia-pkm-*` skills for the pkm domain. Every committed skill must be safe for users who do not share the maintainer's machine, accounts, private data, or internal workspace.

## Safety Rules

- No real API keys, tokens, cookies, session strings, passwords, account ids,
  private `config.yml`, or `.env` files.
- No maintainer-specific absolute paths such as `/Users/<name>/...`.
- No private family, home, health, finance, or learner profile context.
- Put user-specific behavior behind CLI args, env vars, or skill-specific
  user-owned config files outside this repo:
  `~/.config/soia-skills/<skill-name>/config.yml` (v2). Do not introduce a new
  repository/domain nesting layout contrary to the parent workspace decision.
  Existing alternative paths require an explicit migration decision; this rule
  does not authorize moving, deleting or rewriting user configuration.
- Repository examples must use placeholders such as `<path>`, `<repo>`, and
  `<YOUR_KEY>`.

## Validation

日常验证按影响面选择：纯指令/文档修订先检查 diff、链接与条款一致性；脚本或技能行为变化运行受影响测试。涉及技能行为、脚本、依赖或公共工具的提交前执行以下完整门禁；纯指令/说明文档提交不机械套用全仓测试，但 CI/正式发布明确要求的检查不得省略：

```bash
# 仅缺依赖且环境安装已获授权时执行；已有依赖不重复安装
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/generate_skill_catalog.py --check
python3 scripts/audit_skills.py
git diff --check
```

修改技能时可补充运行兼容的 quick validator；仅其不支持本仓必需的版本、时间、作者等 frontmatter 时，记录不兼容并以本仓 audit 判定，不删除字段迁就工具。其他真实校验错误仍须处理。纯 AGENTS.md 修订不触发技能行为测试。辅助命令：

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/<skill-name>
```

只有本次明确包含安装验收时才执行安装；最终验收使用已发布的远端来源，不把本地调试副本冒充正式版。先确认 project/global、Agent 和 skill/domain/all，再按已确认计划执行。以下先列只读发现命令；全局全量命令仅供客户明确选择该范围后的安装，不是默认检查步骤：

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -l --full-depth
# 仅在全局 + 全量技能 + 全部 Agent 范围已明确批准后使用
npx skills add soia-team/soia-open-pkm-vault-skills -g --all
```

## 维护本仓技能

技能契约、调试安装、新增/改名/拆分/删除的完整流程，以及插件市场发布步骤，统一见
元仓的 [CONTRIBUTING.md](https://github.com/soia-team/soia-open-skills/blob/main/CONTRIBUTING.md)。
本文件只保留本仓特有的用途、边界与验证命令。

## Git Workflow

- **Branch off `main`** (the latest formal release), then open the PR against
  `dev` and wait for the `audit` check. Verify the expected `main` → `dev`
  ancestry and actual merge conflicts; ancestry alone is not proof of a clean merge. Branch off `dev` only when your change
  genuinely builds on unreleased work, and say so in the PR body.
- `main` never receives PRs. It moves only by **fast-forward from `dev`** during
  a formal release driven by `soia-meta-skill-release`, so `main` and `dev` then
  point at the same commit. 普通开发不直接 push `main` 或 `dev`；唯一例外是已获本次发布授权、通过 CI 且祖先关系校验成立后，由发布流程快进 `dev` → `main`。
- Plugin manifests on `dev` carry a `-SNAPSHOT` version naming the next release
  target. Do not change manifest versions in feature PRs; versions move only
  during a release.
