# 目标版本基线：Dify 1.17.1 / DSL 0.7.0

本技能只生成 **DSL `0.7.0`**。目标实例是 Dify **1.17.1**（服务端 `CURRENT_APP_DSL_VERSION = "0.7.0"`，运行时 graphon `0.7.0`）。

## 版本映射

| Dify 服务端 | DSL `version` | 说明 |
|---|---|---|
| 1.16.x / 1.17.x / 1.18.x | `"0.7.0"` | 与 1.17.1 同结构，本技能生成的文件直接适用 |
| 1.15.x 及更早 | `"0.6.0"` 及更早 | 结构不同，本技能不覆盖 |

Dify 1.16 之后 DSL 版本没有再动：1.16.x、1.17.x、1.18.x 的导出都是 `0.7.0`，节点字段以 graphon 0.7.0 的实体定义为准。

## 导入旧版本会发生什么

Dify 1.17.1 的导入判定（`api/services/dsl_version.py`）只比较版本号：

| 导入文件版本 | 判定 | 后果 |
|---|---|---|
| `0.7.0` | `completed` | 正常导入 |
| `0.6.0` | `completed-with-warnings` | 能导入，但**结构差异不会被自动补齐**——缺失的节点字段仍然缺失，要到运行期才暴露 |
| 高于 `0.7.0` 或主版本更大 | `pending` | 拒绝导入 |

所以「改版本号就能升级」是错的：改字符串不会让文件长出 0.7.0 才有的结构。

## 0.7.0 特有的结构

这些结构在更早的 DSL 里没有。写进当前版本是安全的，直接搬到旧版本会失败。

### 顶层 Agent App

`app.mode: agent` 的应用**没有 `workflow` 段**，取而代之 `agent` + `agent_packages`：

```yaml
version: "0.7.0"
kind: app
app:
  name: "研究助理"
  mode: agent
  icon: "🧠"
  icon_type: emoji
  icon_background: "#F3E8FF"
  use_icon_as_answer_icon: false
agent:
  package_ref: main_agent
agent_packages:
  main_agent:
    schema_version: 1
    metadata:
      name: "研究助理"
      description: "回答研究问题并标明信息边界"
      role: research_assistant
    soul:
      schema_version: 1
      prompt:
        system_prompt: "优先给结论，明确证据不足的部分。"
      model:
        plugin_id: langgenius/openai
        model_provider: langgenius/openai/openai
        model: gpt-4.1-mini
        credential_ref: null
        model_settings:
          temperature: 0.2
    omitted_assets: []
```

要点：

- `agent.package_ref` 必须等于 `agent_packages` 下的某个键。
- `soul.model.credential_ref` 导出时为 `null`，导入后需在工作区重新绑定凭据。
- `omitted_assets` 记录导出时被剔除的技能/文件/上传物，非空时导入后需人工补回。

### Agent v2 节点

在 `workflow` / `advanced-chat` 图里使用 Agent 有两种节点，结构完全不同：

| | legacy 插件策略 Agent | Agent v2 |
|---|---|---|
| 识别字段 | `agent_strategy_provider_name` + `agent_parameters` | `version: "2"` + `agent_node_kind: dify_agent` |
| 包定义 | 无 | 顶层 `agent_packages`，`agent_binding.package_ref` 指向它 |
| 输出 | 由 `output_schema` 决定 | `agent_job.declared_outputs`，为空时运行期只有 `text`/`files`/`json` |

`version` 必须是字符串 `"2"`，写成数字 `2` 会导致节点不被识别为 v2。

### Human Input

`human-input` 引入三个特有概念：

- **动作即分支**：`user_actions[].id` 直接作为出边 `sourceHandle`，不写 `source`。
- **超时分支**：句柄是 `__timeout`，`timeout_unit` 仅 `hour` / `day`。
- **特殊输出**：`__action_id`、`__action_value`、`__rendered_content` 三个内置输出，加上 `inputs[].output_variable_name` 声明的自定义输出。

### Loop 与 assigner v2

- `loop` 容器：`loop_variables` + `break_conditions` + `start_node_id`，子节点标 `isInLoop` / `loop_id`。
- `assigner` 出现 `version: "2"`，源选择器存放位置不同。
  - v1：`items[].variable_selector` + `items[].value_selector`
  - v2：`items[].value` 里放选择器本身（`input_type: variable` 时）
  两种形态同一节点类型，**按目标工作区导出的形态写**，不要混。当前 1.17.1 导出的是 v2。

### 节点 wrapper 布局字段

0.7.0 的导出会带上画布布局字段：

```yaml
- id: node_id
  type: custom
  data: { ... }
  position: { x: 370, y: 260 }
  positionAbsolute: { x: 370, y: 260 }
  sourcePosition: right
  targetPosition: left
  width: 244
  height: 90
```

这些字段**可以省略**（导入不强制），但补上后画布打开即排版整齐。手写推荐补全；`positionAbsolute` 与 `position` 在顶层节点上取相同值，在容器子节点上 `positionAbsolute` 是父容器坐标 + 相对坐标。

## 遇到旧文件怎么办

- **编辑用户已有文件时保留原版本**，不要顺手升级，也不要用本技能的 0.7.0 结构去改旧版文件。
- 用户给的是 `0.6.0` 文件而目标是 1.17.1：能导入（`completed-with-warnings`），但要把缺的字段按本技能补齐，否则运行期才报。
- 目标实例比 1.17.1 更旧时，先确认它是否还是 DSL `0.7.0`；不是的话本技能不适用。

## 相关

- `dsl-format.md` — 顶层结构、节点 wrapper、变量与选择器、dependencies
- `edge-and-layout.md` — 边、分支句柄、坐标与容器布局
- `nodes/*.md` — 21 个节点的字段表与最小示例
