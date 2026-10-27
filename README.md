# dify-workflow-dsl

Dify 工作流 DSL 的技能仓库。产物是**可直接导入 Dify 的 YAML/JSON**，覆盖 DSL `0.6.0`（Dify 1.15.x）与 `0.7.0`（Dify 1.16.x）。

仓库采用通行布局：`skills/<技能名>/SKILL.md`，根目录带 `.claude-plugin/` 清单与安装脚本，可直接被 WorkBuddy、Claude Code、OpenClaw 等工具识别。

## 技能列表

| 技能 | 作用 | 入口 |
|---|---|---|
| `dify-workflow-dsl` | 自然语言 → 可导入 DSL；含方案选型、导入排查、21 个节点规范、4 个模板、5 个完整样例、静态校验器 | [`skills/dify-workflow-dsl/`](skills/dify-workflow-dsl/SKILL.md) |

技能内部细节（校验器覆盖范围、已知边界、目录说明）见 [技能自述](skills/dify-workflow-dsl/README.md)，此处不重复。

## 安装

### 脚本安装（推荐）

```bash
./install.sh                  # 默认 ~/.workbuddy/skills
./install.sh --workbuddy      # WorkBuddy，用户级、全工程可用
./install.sh --agents         # ~/.agents/skills
./install.sh --claude         # ~/.claude/skills
./install.sh --codebuddy      # ~/.codebuddy/skills
./install.sh --dest <目录>     # 自定义，例如 <项目>/.workbuddy/skills 只对本工程生效
./install.sh --only dify-workflow-dsl --dry-run
```

Windows 用 `.\install.ps1`，参数同名（`-Workbuddy` / `-Agents` / `-Claude` / `-Dest` / `-Only` / `-DryRun` / `-Backup`）。

覆盖同名技能前加 `--backup`（`-Backup`）会先备份为 `<name>.bak.<时间戳>`。

### Claude Code 插件市场

仓库根含 `.claude-plugin/marketplace.json`，可直接添加为本地市场：

```bash
/plugin marketplace add D:\Code\Personal\dify-workflow-dsl
```

### 手动

把 `skills/dify-workflow-dsl/` 整个目录复制到目标工具的技能目录，保证目录内 `SKILL.md` 在顶层。

## 开发约定

- 技能是自包含的：`SKILL.md` 里的相对路径都以技能目录为基准，移动目录不影响引用；技能目录内不应出现指向仓库其他位置的引用。
- 改动后必须跑通三条命令（在技能目录内）：

```bash
python scripts/validate_dsl.py --strict --target-version 0.7.0 examples/*.yml
python scripts/validate_dsl.py references/templates/*.yml   # 模板含 <dataset-id> 占位符，只跑非严格
python -m unittest discover -s tests -v
```

- 新增 Dify 节点或版本时，同步更新三处：`references/nodes/<node>.md`、`SKILL.md` 的节点路由表、`references/version-deltas.md`。
- 说明文字用中文，字段名与 YAML 关键字保持英文原样。

## 许可

MIT（示例与模板为手写，字段取自 Dify 官方导出格式）。
