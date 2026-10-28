# dify-workflow-dsl 技能开发说明

从自然语言需求生成**可直接导入**的 Dify 工作流 DSL（YAML / JSON），覆盖 DSL `0.6.0`（Dify 1.15.x）与 `0.7.0`（Dify 1.16.x）。

这不是"写个大概像的 YAML"的提示词集合。它把三类最容易翻车的东西固化成可校验的规范：

1. **版本结构**——0.7.0 的 Agent App、Agent v2、Human Input 与 0.6.0 不是只差一个版本号；
2. **连线语义**——分支句柄（`cases[].id` / `classes[].id` / `user_actions[].id` / `__timeout`）逐字匹配；
3. **引用合法**——选择器根节点存在、模板里 `{{#node.field#}}` 的节点 id 不含连字符。

> 本文面向维护者。技能包只包含 `skills/dify-workflow-dsl/` 下的运行时资产；测试与本文档不随技能安装。

## 目录结构

```
skills/dify-workflow-dsl/   技能包（安装时整个目录复制）
  SKILL.md                  技能入口：版本策略、节点路由、硬规则、交付规范
  references/
    dsl-format.md           顶层结构、节点 wrapper、变量与选择器、dependencies
    edge-and-layout.md      边、分支句柄、坐标与容器布局
    version-deltas.md       0.6.0 ↔ 0.7.0 差异与迁移清单
    nodes/*.md              21 个节点的字段表、最小示例、导入失败原因
    templates/*.yml         4 个可直接改的骨架
  examples/*.dify.yml       5 个完整可导入样例
  scripts/validate_dsl.py   静态校验器（版本/节点/边/选择器/容器/可达性/依赖）

tests/                      校验器回归测试与正反夹具（开发期，不随技能安装）
docs/dify-workflow-dsl.md   本文件（维护者文档，不随技能安装）
```

## 快速开始

```bash
# 在 skills/dify-workflow-dsl/ 内校验一个 DSL 文件
python scripts/validate_dsl.py app.dify.yml

# 指定版本 + 严格模式
python scripts/validate_dsl.py --strict --target-version 0.7.0 app.dify.yml

# 在仓库根目录跑回归测试
python -m unittest discover -s tests -v
```

依赖：Python 3.9+、PyYAML。

## 校验器覆盖范围

| 类别 | 检查内容 |
|---|---|
| 版本 | `version` 为字符串、在支持列表内、与 `--target-version` 一致；`mode: agent` 仅 0.7.0 |
| 图 | 入口唯一性、`end`/`answer` 可达、孤岛节点、意外回边、死端 |
| 节点 | 类型枚举、字段必填项（llm / code / end / if-else / classifier / human-input / assigner / tool / iteration / loop / agent） |
| 边 | 端点存在、`targetHandle`、分支句柄与分支定义一致、`sourceType`/`targetType` 对齐 |
| 引用 | `*_selector` 根节点存在、`{{#...#}}` 节点 id 字符合法、引用未知节点 |
| 容器 | `parentId`、`zIndex`、`isInIteration`/`isInLoop`、`start_node_id` 指向辅助起点 |
| Agent | `agent_packages` 引用完整、`version: "2"`、`declared_outputs` 结构 |
| 依赖 | 插件节点是否缺 `dependencies`、`plugin_unique_identifier` 形态 |

WARN 与 ERROR 分开：`--strict` 把 WARN 也计为失败。少数 WARN 是有意为之——模板里的 `<dataset-id>` 占位符与 Agent 包里的 `credential_ref: null`，替换后即可通过。

## 安装

`skills/dify-workflow-dsl/` 是自包含的运行时技能包（顶层有 `SKILL.md`），把整个目录复制到目标工具的技能目录即可，或使用仓库根目录的 `install.sh` / `install.ps1`。`tests/` 与本文档在技能包之外，不会被安装。

```bash
cp -R skills/dify-workflow-dsl <目标工具的技能目录>/
```

复制后应存在 `<技能目录>/dify-workflow-dsl/SKILL.md`。目录内所有相对路径（`references/`、`examples/`、`scripts/`）都以技能目录为基准，整体搬移不影响引用；目录名保持为 `dify-workflow-dsl`，与 `SKILL.md` 里的 `name` 一致。

运行只依赖 Python 3.9+ 与 PyYAML，不需要技能目录之外的任何文件。

## 已知边界

- 只做静态校验，**不替代真实导入**。插件凭据、知识库 ID、触发器 URL 必须在目标工作区补齐。
- 插件的动态字段（`tool_parameters`、`event_parameters`）以目标工作区导出为准，本技能只能给出结构约束。
- 0.7.0 的 Agent 包内部资产（技能、上传文件、工作区联系人）导出时被清洗，`omitted_assets` 非空需人工补回。
- DSL 版本演进快，`version-deltas.md` 需随 Dify 版本更新；不确定时以目标实例导出的文件为准。

## 许可

MIT。示例与模板均为手写，字段取自 Dify 官方导出格式。
