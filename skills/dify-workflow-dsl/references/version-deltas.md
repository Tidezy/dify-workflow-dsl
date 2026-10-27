# 版本差异：DSL 0.6.0 ↔ 0.7.0

## 版本对照

| Dify 服务端 | DSL `version` | 应用模式 | 关键能力 |
|---|---|---|---|
| 1.16.x 及以上 | `"0.7.0"` | `workflow` / `advanced-chat` / `agent` | 顶层 Agent App、Agent v2 可移植节点、Human Input、Loop 容器、节点 wrapper 扩展字段 |
| 1.15.x | `"0.6.0"` | `workflow` / `advanced-chat` | Loop、Variable Assigner v2、legacy 插件策略 Agent；无 Agent App、无 Agent v2 包、Human Input 支持情况按具体小版本 |
| 1.10.x ~ 1.14.x | `"0.6.0"` | `workflow` / `advanced-chat` | 同上，但部分节点字段随小版本演进而非全部可用 |
| 1.3.x ~ 1.9.x | `"0.4.0"` ~ `"0.5.x"` | `workflow` / `advanced-chat` | 有 Iteration，无 Loop |
| 1.0.x ~ 1.2.x | `"0.2.0"` ~ `"0.3.x"` | `workflow` / `advanced-chat` | 基础形态 |
| 0.6.x ~ 0.14.x | `"0.1.0"` ~ `"0.1.5"` | `workflow` / `advanced-chat` | 早期形态 |

> 默认策略：**新建文件写 `"0.7.0"`**（Dify 1.16.x）。需要向下兼容 1.15.x 时写 `"0.6.0"`。
> 编辑已有文件时**保留原版本**，除非用户明确要求迁移。

## 只改版本字符串是错的

把 `"0.6.0"` 改成 `"0.7.0"` 不会让文件变成 0.7.0。反过来更危险：声明 0.7.0 却在用 0.7.0 专属结构，或声明 0.6.0 却写了 `agent` 模式的顶层段，都会在导入时被拒。判断依据是**结构**，不是字符串。

## 0.7.0 新增：顶层 Agent App

`app.mode: agent` 的应用**没有 `workflow` 段**，取而代之是 `agent` + `agent_packages`：

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
- `soul.model.credential_ref` 导出时位 `null`，导入后需在工作区重新绑定凭据。
- `omitted_assets` 记录导出时被剔除的技能/文件/上传物，非空时导入后需人工补回。

## 0.7.0 新增：Agent v2 可移植节点

在 `workflow` / `advanced-chat` 图里使用 Agent 有两种节点，结构完全不同：

| | legacy 插件策略 Agent | Agent v2 |
|---|---|---|
| 识别字段 | `agent_strategy_provider_name` + `agent_parameters` | `version: "2"` + `agent_node_kind: dify_agent` |
| 包定义 | 无 | 顶层 `agent_packages`，`agent_binding.package_ref` 指向它 |
| 输出 | 由 `output_schema` 决定 | `agent_job.declared_outputs`，为空时运行期只有 `text`/`files`/`json` |

`version` 必须是字符串 `"2"`，写成数字 `2` 会导致节点不被识别为 v2。

## 0.7.0 新增：节点 wrapper 扩展字段

0.6.0 的节点 wrapper 只有 `id` / `type` / `data` / `position`（容器另加 `width`/`height`）。0.7.0 的导出会带上画布布局字段：

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

## 0.7.0 新增：Human Input

0.6.0 没有人工介入节点。0.7.0 的 `human-input` 引入三个特有概念：

- **动作即分支**：`user_actions[].id` 直接作为出边 `sourceHandle`，不写 `source`。
- **超时分支**：句柄是 `__timeout`，`timeout_unit` 仅 `hour` / `day`。
- **特殊输出**：`__action_id`、`__action_value`、`__rendered_content` 三个内置输出，加上 `inputs[].output_variable_name` 声明的自定义输出。

## 0.7.0 新增：Loop 与 assigner v2

- `loop` 容器在 0.6.0 已存在但导出形态在 0.7.0 稳定：`loop_variables` + `break_conditions` + `start_node_id`，子节点标 `isInLoop` / `loop_id`。
- `assigner` 在 0.7.0 出现 `version: "2"`：源选择器存放位置不同。
  - v1：`items[].variable_selector` + `items[].value_selector`
  - v2：`items[].value` 里放选择器本身（`input_type: variable` 时）
  两种形态同一节点类型，**按目标工作区导出的形态写**，不要混。

## 0.7.0 行为差异（影响设计，不影响字段）

| 项 | 0.6.0 | 0.7.0 |
|---|---|---|
| 触发器导出 | 保留部分配置 | `trigger-schedule` 配置被重置、`trigger-webhook` 的 URL 被清空、`trigger-plugin` 的 `subscription_id` 被清空 |
| Agent 导出 | 保留策略字段 | 额外清洗 `credential_ref`、`human_contacts`、`omitted_assets` |
| 结构化输出 | `llm.structured_output_enabled` 等散字段 | 更倾向让 `parameter-extractor` 或 Agent v2 的 `declared_outputs` 承担 |

## 迁移检查清单

从 0.6.0 迁到 0.7.0 时逐项确认：

1. `version` 是否为字符串 `"0.7.0"`；
2. 是否真的需要 Agent App（`mode: agent`）——只有独立可对话的 Agent 才该用；嵌在流程里的用 Agent v2 节点；
3. `agent_job.declared_outputs` 是否补齐了业务字段，否则下游只能拿到 `text`；
4. `llm` 节点每个 `prompt_template` 条目是否有独立 `id`；
5. `human-input` 的动作 id 是否 ≤20 字符、是否与出边 handle 一一对应；
6. 触发器相关字段是否需要重新配置；
7. 跑一遍 `python scripts/validate_dsl.py --strict --target-version 0.7.0 <file>`。

## 相关

- `dsl-format.md` — 顶层结构与字段规范
- `edge-and-layout.md` — 边、handle、布局
- `nodes/agent.md` — 三种 Agent 形态的完整写法
- `nodes/human-input.md` — 人工节点
