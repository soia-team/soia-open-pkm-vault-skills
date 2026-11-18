---
name: soia-pkm-alipan-curator
description: 规划并整理阿里云盘资源，产出可复核的馆藏索引与学习规划。触发：「整理阿里云盘资源」「更新阿里云盘索引」「用网盘资源做学习计划」
dependencies:
  hard: [soia-pkm-alipan-drive-ops]
version: 1.6.6
created_at: 2026-07-02 23:02:39
updated_at: 2026-11-18 10:05:00
created_by: claude opus 4.6
updated_by: gemini-4-hydrogen
---

# soia-pkm-alipan-curator — 云盘资源顾问

阿里云盘顾问层：在强依赖原子层 `soia-pkm-alipan-drive-ops` 之上统筹 **盘点（inventory）/ 整理（organize）/ 馆藏索引（catalog）/ 学习规划（plan）**（与 `huashu-weread-advisor` / `weread-skills` 等第三方包仅设计类比，绝不依赖或调用）。

## 客户可读说明

### 这个技能可以做什么

| 客户想要 | 技能会做 | 客户能看到 |
|---|---|---|
| 盘点与规划整理阿里云盘资源 | 基于只读扫描生成分类、可配编号与结构合同计划（plan-first，确认后单写入执行） | 内容审计表、逐项迁移 manifest、结构与发布审计报告 |
| 更新 Obsidian 馆藏总览与检索索引 | 调用 `gen_catalog.py` 生成折叠树总览与分区全文检索清单 | 云盘馆藏总览 Markdown、分区全文检索清单与导出位置 |
| 生成增量 Excel 总索引与家长导航 | 调用 `gen_catalog_xlsx.py` / `gen_family_nav_xlsx.mjs` 按 SHA-256 增量构建工作簿 | 交付目录下的 Excel 总索引与校验回执 |
| 基于学情制定云盘学习计划 | 匹配已有书/视频资源（按字数或集数×时长排期），输出待确认计划 | 带映射表与周排期的学习计划 Markdown |

### 客户如何使用

- 「根据最新扫描 JSONL 更新 Obsidian 云盘馆藏总览和全文检索索引。」
- 「增量刷新阿里云盘 Excel 总索引到默认交付目录。」
- 「为阿里云盘某分区生成目录重组 dry-run 计划，先给我裁定模糊项后再执行。」

### 依赖与安装

默认项目单技能：`npx skills add soia-team/soia-open-pkm-vault-skills -a <agent> -s soia-pkm-alipan-curator`（`<agent>` 换成明确宿主；仅明确选择全局时加 `-g`）。整域需明确选择：`claude plugin marketplace add soia-team/soia-open-skills && claude plugin install soia-pkm-vault@soia`（Codex 用 `codex plugin add soia-pkm-vault@soia`）。**WorkBuddy** 使用[专家安装说明](https://github.com/soia-team/soia-open-skills/blob/main/docs/install/workbuddy.md)，不由 npx 代装。上述命令不构成安装或发布授权。强制依赖同仓 `soia-pkm-alipan-drive-ops` 完成云盘操作；配置放 `~/.config/soia-skills/soia-pkm-alipan-curator/config.yml` 或 `$SOIA_PKM_ALIPAN_CURATOR_CONFIG_FILE`。

### 私密信息与中间数据

云盘凭据留在原子层与系统凭据存储，本技能不读取或打印；运行包、移动计划、发布 manifest 与历史 debt 放 `${XDG_STATE_HOME:-$HOME/.local/state}/soia-pkm-alipan-curator/`，解析缓存放 `${XDG_CACHE_HOME:-$HOME/.cache}/soia-pkm-alipan-curator/`，临时样本放 OS 临时目录并清理。Excel/导航/学习计划属 C 类交付物，按「用户指定 > `ALIPAN_CURATOR_OUTPUT_DIR` > `~/Downloads/soia-pkm-alipan-curator/`」写入（禁写 vault `outputs/`、session 目录或相对 cwd），OB 馆藏 Markdown 属 D 类按用户 `--out` 写入 vault；日志仅输出脱敏角色/数量/哈希。

### 日志与完成回执

汇报扫描/迁移范围、manifest 与 SHA-256 核对、审计通过状态及导出位置；涉及结构写入时，在云端新索引上传并通过 `audit_catalog_publish.py --final` 前状态保持 `pending_catalog_publish`，禁止宣称完成。

## 四类子工作流

### 1. `inventory`（盘点）
递归扫至资源根或叶终态（除非用户显式设限），写核对清单（内容·类型·建议动作）到用户指定 `<vault>/<inventory-relative-path>`，等确认后进 `organize`。

### 2. `organize`（大型整理固定闭环）
读 [deep-reorg-playbook.md](references/deep-reorg-playbook.md)、[run-bundle.md](references/run-bundle.md)、[references/classification-methods.md](references/classification-methods.md) 与 [operations-troubleshooting.md](references/operations-troubleshooting.md)。

- **固定执行链**：`merge_classification_map.py` → `assign_resource_numbers.py`（仅编号确认后）→ `build_reclass_plan.py` → `build_structure_plan.py` → `preflight_reclass.py` → 非 final `audit_run_bundle.py` → dry-run (`apply_reclass.py` / `apply_reclass_bulk.py`，所有写操作 `--max-parallel 1` 单写者串行经 `run_with_env.py`) → 同写者 `--execute`（写前必走 `verify_preflight_gate`）→ fresh terminal scan → 刷新 OB/Excel → 上传云端索引 → `audit_structure.py --final` + `audit_catalog_publish.py --final` + `audit_run_bundle.py --final`。
- **删除与历史 Debt 隔离**：重分类/恢复器只接 `mkdir`/`mv`/`rename`（禁混 `delete`）；未来删除单独入 `cleanup_batches`（需 `approved` + 带时区 `authorized_at` + 终态零子项验证），已发生无原件授权的旧清理记 `run.files.cleanup_process_debt`（`legacy_process_debt` / `authorization_unproven_execution`），绝不倒填洗白。
- **结构与分类硬契约**：一层一轴，技术包/依赖目录整包保留，杂包必拆、广告先列候选等授权删，重名按 SHA1 查重；**不确定项可隔离复核**（移入用户指定复核目标，公共 skill 不写死路径）。**编号可配置且必须闭环**（扫描漏号为 0）；超长系列由 `plan_series_chunks.py` 分组并用 `flat_series_discovery` 全区二遍扫描防漏；**学习导航必须闭环**（`required_guides` + `guide_layers` 含非空 `file_pattern`/`min_bytes`）；云端关键产物与消费端地图由 `required_artifacts` 与 `resource_maps`（含最终 `file_id` 与直达 Markdown 链接）经 `audit_structure.py --final` 机械验收；写操作后用独立只读通道双层核对。

### 3. `catalog`（馆藏 Markdown / Excel / 家庭导航）
用法与发布同源版本门禁详见 [library-method.md](references/library-method.md)、[catalog-excel.md](references/catalog-excel.md) 与 [family-navigation-excel.md](references/family-navigation-excel.md)。

- `scripts/gen_catalog.py` 生成折叠树总览 + `--search-dir` 全文检索（单分区增刷用 `--merge-existing` + `--roots`，新分区需 `--allow-new-partition` 或 `materialize_catalog_snapshot.py`）。馆藏图书馆（库卡 + Bases `.base` 必用 `file.inFolder("<根>")` 联合 `file.hasTag("馆藏")`）见 `library-method.md`。
- `scripts/gen_catalog_xlsx.py`（总索引 + 分区明细，按 Markdown SHA-256 增量刷新，`--renderer {auto,artifact-tool,openpyxl}`，`--verify` + 可选 `--soffice`）与 `scripts/gen_family_nav_xlsx.mjs` 必须与 OB 总览共享一次生成的统一 release metadata；家庭导航上传后**显式询问**用户是否用 `check_family_nav_staleness.py register` 登记过期基准。

### 4. `plan`（学习计划）
仅使用用户当次提供的学情与已有馆藏索引（不读私有记忆/长期个人档案），按字数或集数×单集时长倒排周计划，按 [plan-template.md](references/plan-template.md) 落盘为匿名文件名（如 `YYYY-MM-DD-<学习者代号>-<主题>.md`），待用户确认后转正。

## 验证与前向测试

运行 `soia-open-pkm-vault-skills` 全量 `unittest` 与 `audit_skills.py --strict`（含 `test_curator_public_safety.py` 与运行包/结构/索引审计前向测试）；每次实操涉及写云盘或刷新索引，均须校验终态 JSONL 与所有消费端链接零报错。
