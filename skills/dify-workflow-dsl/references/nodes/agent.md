# Agent（`agent`）

`agent` 在 DSL 里有三种互不兼容的形态：旧版插件策略 Agent 节点、0.7.0 的 Agent v2 节点、以及 0.7.0 的顶层 Agent App（`app.mode: agent`）。三者都叫 agent，字段却完全不同，不能混写。

## 用途

- **legacy 插件策略 Agent**：由 `langgenius/agent` 一类策略插件驱动的节点，把模型 + 指令 + 工具集交给插件自己跑 ReAct / FunctionCalling 循环，0.6.0 与 0.7.0 都存在。
- **Agent v2 节点**：0.7.0 的工作流内 Agent 节点，节点只描述"这次要做什么"（`agent_job`），Agent 本体（提示词、模型、技能）抽到顶层 `agent_packages`，可跨工作区搬运。
- **顶层 Agent App**：`app.mode: agent` 的独立应用，没有 `workflow.graph`，整个应用等于一个 `agent_packages` 条目加一个 `package_ref`。

## 何时用 / 何时不要用

**何时用**

- 任务需要"模型自主决定调哪些工具、循环几次"，步骤无法预先编排。
- 需要可复用的 Agent 资产：多个节点引用同一个 `package_ref`（v2），或导出成独立 Agent 应用。

**何时不要用**

- 步骤固定、只需一次模型调用 → 用 `llm.md`；要严格结构 → `llm` + `parameter-extractor`。
- 只调一个确定的工具 → 用 `tool.md`；需要确定性重试 / 分支 → `if-else` + `loop`。
- 目标工作区是 1.15.x（DSL 0.6.0）→ 只能写 legacy 形态，v2 与 Agent App 会导入失败。

## 字段表

### 一、legacy 插件策略 Agent（0.6.0 / 0.7.0）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `type` | `string` | 是 | `agent`。 |
| `title` | `string` | 是 | 节点标题。 |
| `agent_strategy_provider_name` | `string` | 是 | 策略插件提供方，如 `langgenius/agent/agent`。 |
| `agent_strategy_name` | `string` | 是 | 策略名，如 `function_calling`、`react`。 |
| `agent_strategy_label` | `string` | 否 | UI 展示名，如 `FunctionCalling`。 |
| `agent_parameters` | `object` | 是 | 键值对，每项 `{type: constant \| variable, value: ...}`；常用键 `model` / `query` / `instruction` / `tools`。 |
| `output_schema` | `object \| null` | 否 | 结构化输出约束，不约束时为 `null`。 |

其他策略键（最大迭代轮数、记忆配置等）随策略插件而异，**以目标工作区导出的 DSL 为准**；`dependencies` 必须带上该插件，否则导入报缺失插件。

### 二、Agent v2 节点（DSL 0.7.0）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `version` | `string` | 是 | 固定 `"2"`；缺失或为 `"1"` 时按 legacy 解析。 |
| `agent_node_kind` | `string` | 是 | 当前为 `dify_agent`。 |
| `agent_binding.binding_type` | `string` | 是 | `inline_agent` 表示引用本文件内的包；其他绑定类型以导出为准。 |
| `agent_binding.package_ref` | `string` | 是 | 指向顶层 `agent_packages` 的键名，如 `researcher`。 |
| `agent_job.schema_version` | `number` | 是 | 当前为 `1`。 |
| `agent_job.mode` | `string` | 是 | 任务投递方式，示例为 `tell_agent_what_to_do`；其他取值以导出为准。 |
| `agent_job.workflow_prompt` | `string` | 是 | 本次任务的自然语言说明，支持 `{{#node.var#}}`。 |
| `agent_job.previous_node_output_refs` | `array` | 否 | 上游上下文，每项 `{selector: [node, var]}`。 |
| `agent_job.declared_outputs` | `array` | 否 | 声明输出，每项 `{name, type, description, required}`；**为空数组时运行期输出为 `text` / `files` / `json`**。 |
| `agent_job.human_contacts` | `array` | 否 | 人工联系人；导出时被清洗为空。 |
| `agent_job.metadata` | `object` | 否 | 附加元数据，通常 `{}`。 |

### 三、顶层 Agent App（DSL 0.7.0）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `app.mode` | `string` | 是 | 固定 `agent`；此类文件没有 `workflow` 段。 |
| `agent.package_ref` | `string` | 是 | 指向 `agent_packages` 的键名。 |
| `agent_packages.<ref>.schema_version` | `number` | 是 | 当前为 `1`。 |
| `agent_packages.<ref>.metadata` | `object` | 是 | `name` / `description` / `role` / `icon_type` / `icon` / `icon_background`。 |
| `agent_packages.<ref>.soul` | `object` | 是 | `schema_version`（当前 `1`）、`prompt.system_prompt`、`model`。 |
| `agent_packages.<ref>.soul.model` | `object` | 是 | `plugin_id` / `model_provider` / `model` / `credential_ref` / `model_settings`；导出后 `credential_ref` 为 `null`。 |
| `agent_packages.<ref>.soul.app_features` | `object` | 否 | `opening_statement` / `suggested_questions`。 |
| `agent_packages.<ref>.omitted_assets` | `array` | 否 | 导出时被剔除的资产清单（上传文件、技能包等）。 |
| `dependencies` | `array` | 否 | 模型插件依赖；缺了导入后模型不可用。 |

导出会清洗凭据与工作区绑定：`credential_ref` 变 `null`、`human_contacts` 为空、`omitted_assets` 记录被移除的技能与文件。导入后必须在目标工作区重新选择模型凭据、重连联系人、补回技能，否则节点能导入却跑不起来。

## 最小可导入示例

### 示例 1：legacy 插件策略 Agent（片段，置于 `workflow.graph.nodes` 下）

```yaml
    nodes:
      - id: legacy_agent
        type: custom
        data:
          type: agent
          title: "Agent"
          agent_strategy_provider_name: langgenius/agent/agent
          agent_strategy_name: function_calling
          agent_strategy_label: FunctionCalling
          agent_parameters:
            model:
              type: constant
              value:
                provider: langgenius/tongyi/tongyi
                name: qwen3.5-flash
                mode: chat
                completion_params:
                  temperature: 0.3
            query: {type: constant, value: "{{#sys.query#}}"}
            instruction: {type: constant, value: "Answer with tool support when useful."}
            tools: {type: constant, value: []}
          output_schema: null
          selected: false
        position: {x: 370, y: 282}
```

出边用默认句柄：`sourceHandle: source`、`data: {sourceType: agent, targetType: end, ...}`。

### 示例 2：Agent v2 节点 + 顶层 `agent_packages`（完整文件）

```yaml
version: "0.7.0"
kind: app
app: {name: "Agent v2 研究工作流", mode: workflow, icon: "🔬", icon_type: emoji, use_icon_as_answer_icon: false}
agent_packages:
  researcher:
    schema_version: 1
    metadata:
      name: "研究 Agent"
      description: "根据工作流任务生成结构化研究报告"
      role: researcher
      icon_type: emoji
      icon: "🔬"
    soul:
      schema_version: 1
      prompt:
        system_prompt: "你是严谨的研究员。明确证据、推断和未知项，不虚构来源。"
      model:
        plugin_id: langgenius/openai
        model_provider: langgenius/openai/openai
        model: gpt-4.1-mini
        credential_ref: null
        model_settings: {temperature: 0.2}
    omitted_assets: []
dependencies:
  - type: marketplace
    current_identifier: null
    value:
      marketplace_plugin_unique_identifier: "langgenius/openai:0.2.6@e2665624a156f52160927bceac9e169bd7e5ae6b936ae82575e14c90af390e6e"
      version: null
workflow:
  features: {}
  graph:
    nodes:
      - id: agent_start
        type: custom
        data:
          type: start
          title: "输入研究任务"
          variables:
            - label: "研究任务"
              variable: task
              type: paragraph
              required: true
        position: {x: 40, y: 260}
      - id: research_agent
        type: custom
        data:
          type: agent
          title: "研究 Agent"
          version: "2"
          agent_node_kind: dify_agent
          agent_binding:
            binding_type: inline_agent
            package_ref: researcher
          agent_job:
            schema_version: 1
            mode: tell_agent_what_to_do
            workflow_prompt: "完成研究任务，输出带有结论、依据、风险和下一步的报告。"
            previous_node_output_refs:
              - selector: [agent_start, task]
            declared_outputs:
              - name: report             # 下游用 [research_agent, report]
                type: string
                description: "结构化研究报告"
                required: true
            human_contacts: []
            metadata: {}
        position: {x: 370, y: 260}
      - id: agent_end
        type: custom
        data:
          type: end
          title: "输出报告"
          outputs:
            - variable: report
              value_selector: [research_agent, report]
              value_type: string
        position: {x: 710, y: 260}
    edges:
      - id: agent_start-source-research_agent-target
        source: agent_start
        sourceHandle: source
        target: research_agent
        targetHandle: target
        type: custom
        data: {sourceType: start, targetType: agent, isInIteration: false, isInLoop: false}
      - id: research_agent-source-agent_end-target
        source: research_agent
        sourceHandle: source
        target: agent_end
        targetHandle: target
        type: custom
        data: {sourceType: agent, targetType: end, isInIteration: false, isInLoop: false}
```

### 示例 3：顶层 Agent App（完整文件，无 `workflow` 段）

```yaml
version: "0.7.0"
kind: app
app: {name: "独立研究 Agent", mode: agent, icon: "🧠", icon_type: emoji, use_icon_as_answer_icon: false}
agent:
  package_ref: standalone_agent
agent_packages:
  standalone_agent:
    schema_version: 1
    metadata:
      name: "独立研究 Agent"
      description: "回答研究问题并标明信息边界"
      role: research_assistant
      icon_type: emoji
      icon: "🧠"
    soul:
      schema_version: 1
      prompt:
        system_prompt: "你是研究助理。优先给出结论，明确证据不足和需要核实的内容。"
      model:
        plugin_id: langgenius/openai
        model_provider: langgenius/openai/openai
        model: gpt-4.1-mini
        credential_ref: null
        model_settings: {temperature: 0.2}
      app_features:
        opening_statement: "请告诉我你的研究问题。"
        suggested_questions: ["比较两个方案的关键差异"]
    omitted_assets: []
dependencies: []   # 实际导出会带上模型插件依赖，写法同示例 2
```

## 数据流

- **legacy**：`agent_parameters.query`（常为 `{{#sys.query#}}`）与 `instruction` 进入插件，插件内部完成多轮"模型 → 工具 → 模型"，最终写回节点输出（通常是 `text`）；配了 `output_schema` 则按 schema 出结构化字段。
- **v2**：`agent_job.workflow_prompt` 是一次性任务说明，`previous_node_output_refs` 决定注入哪些上游变量。`declared_outputs` 非空时下游按声明的 `name` 取值；为空时运行期只剩 `text` / `files` / `json`，不能假设有业务字段名。
- **Agent App**：没有图，输入走对话、输出即应用回答；`soul.prompt` 与 `soul.model` 决定行为，`app_features` 只影响开场白与推荐问题。
- 三种形态都不会把工具调用细节暴露成可引用变量，排查要靠运行日志。

## 常见导入失败原因

- **v2 节点缺顶层包**：`agent_binding.package_ref: researcher`，但 `agent_packages` 里没有 `researcher` 键，导入报引用失效。
- **`version` 写错**：写成数字 `2` 而非字符串 `"2"`，或同时残留 `agent_strategy_name`，节点按 legacy 解析导致字段丢失。
- **`app.mode: agent` 却保留 `workflow` 段**（或反之），应用类型与内容不匹配，导入后打开是空白。
- **`declared_outputs` 为空但下游按业务字段取值**：运行期只有 `text` / `files` / `json`，取到空值。
- **`credential_ref` 指向导出方凭据、`dependencies` 缺模型插件**：跨工作区导入后模型不可用，须重新绑定凭据并补装插件。
