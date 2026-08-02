# Vault 索引同步合同

本合同适用于所有会向 vault 写入文件、目录或路径的 PKM 技能。`OB知识库地图.md` 是叶级文件/目录清单，`.base` 是查询定义；两者都不是可忽略的“附属产物”。

## 何时必须刷新

- 新建、删除、移动、改名任意文件或目录：动作完成后立即重建地图。
- 在 `20_资料库/` 新建或落地 Markdown、附件、MOC、导航或 `.base`：即使没有路径迁移，也要重建地图，因为叶级文件数量已经变化。
- 只改已有文件正文/frontmatter且文件路径未变：不必为统计刷新地图；如果改动了 MOC、导航或 Base 定义，仍需按对应技能的验证步骤复核。

## 20 区额外门禁

- `20_资料库/10_主题知识/`、`20_资料库/20_规范与手册/`、`20_资料库/30_学习指南/` 下的语义目录（含二级、三级模块）必须使用唯一数字前缀，例如 `10_AI安全`、`20_技术组件`。
- 年月日目录、明确的 `_resources`/`_image`/`images`/`attachments` 资源目录和隐藏插件状态目录可例外；不把普通语义名误判成资源目录。
- 发现未编号、重复编号或 legacy `10_融合分类` 时，停止批量写入，转 `soia-pkm-manage-vault-lifecycle` 生成 manifest。

## 收官命令与证据

```bash
python3 <health-skill>/scripts/gen_vault_map.py \
  --vault <vault-path>

python3 <lifecycle-skill>/scripts/vault_index_verify.py \
  --vault <vault-path> \
  --base '20_资料库/资料库.base' \
  --map '20_资料库/OB知识库地图.md'
```

若目标 vault 没有该 Base，回执必须明确记录“未配置 Base”，不能把跳过写成验证通过。回执至少记录地图 `updated`、文件/目录统计、Base 根路径存在性和脚本退出结果；不要只报告“命令成功”。

查询技能是只读例外：它不得刷新地图、修改 Base 或改变 vault。
